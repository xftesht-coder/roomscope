"""ROOM·SCOPE — Модуль реального измерения.

Проигрывает test sweep через колонки и одновременно пишет отклик комнаты
через микрофон (UMIK-1). Пока UMIK-1 едет — работает в синтетическом
режиме: "запись" эмулируется свёрткой sweep с модельным IR комнаты, чтобы
весь пайплайн (impulse_response → octave_smoothing → peq_calculator) можно
было гонять и проверять уже сейчас.

Переключение на реальное железо — правка одного поля в config.json:
  "mode": "synthetic" -> "real"
и, при необходимости, "input_device"/"output_device" на индекс UMIK-1
(смотри `python measurement.py --list-devices`).
"""
import argparse
import json
from pathlib import Path
from scipy.signal import fftconvolve

import numpy as np
import soundfile as sf

from dsp.swept_sine import generate_swept_sine, save_to_wav

DEFAULT_CONFIG = {
    "sample_rate": 48000,
    "f_start": 20.0,
    "f_end": 20000.0,
    "duration": 10.0,
    "amplitude": 0.1,
    "tail_duration": 1.0,
    "seed": 0,
    "channels_in": 1,
    "input_device": None,   # None = устройство по умолчанию; индекс UMIK-1 — после `--list-devices`
    "output_device": None,  # None = устройство по умолчанию (ваши колонки)
    "mode": "synthetic",    # "synthetic" | "real"
}


def load_config(path="config.json"):
    """Читает config.json, если он существует и не пуст; иначе — дефолты."""
    cfg = dict(DEFAULT_CONFIG)
    config_file = Path(path)
    if not config_file.is_file():
        raise ValueError(f"Configuration not found: {path}")
    user_cfg = json.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(user_cfg, dict) or set(user_cfg) - set(cfg):
        raise ValueError("Configuration contains unknown fields")
    cfg.update(user_cfg)
    for key in ("sample_rate", "f_start", "f_end", "duration", "amplitude", "tail_duration"):
        value = cfg[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError(f"{key} must be a finite number")
    if not 8000 <= cfg["sample_rate"] <= 192000 or cfg["sample_rate"] != int(cfg["sample_rate"]):
        raise ValueError("sample_rate must be an integer between 8000 and 192000")
    if not 0 < cfg["f_start"] < cfg["f_end"] < cfg["sample_rate"] / 2:
        raise ValueError("Sweep frequencies must be below Nyquist and ordered")
    if not 0 < cfg["duration"] <= 120 or not 0 < cfg["amplitude"] <= 1:
        raise ValueError("Invalid duration or amplitude")
    if isinstance(cfg["seed"], bool) or not isinstance(cfg["seed"], int) or cfg["seed"] < 0:
        raise ValueError("seed must be a non-negative integer")
    for key in ("input_device", "output_device"):
        if cfg[key] is not None and (isinstance(cfg[key], bool) or not isinstance(cfg[key], (int, str))):
            raise ValueError(f"{key} must be a device index or name")
    if cfg["mode"] not in ("real", "synthetic") or cfg["channels_in"] != 1:
        raise ValueError("Use mode real/synthetic and one microphone channel")
    if not isinstance(cfg["tail_duration"], (float, int)) or not 0.05 <= cfg["tail_duration"] <= 10:
        raise ValueError("tail_duration must be 0.05..10 seconds")
    return cfg


def list_input_devices():
    """Печатает входы и выходы, чтобы явно выбрать микрофон и колонки."""
    import sounddevice as sd
    devices = sd.query_devices()
    print("Audio devices (input / output):")
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0 or d["max_output_channels"] > 0:
            print(f"  [{i}] {d['name']}  (in={d['max_input_channels']}, "
                  f"out={d['max_output_channels']}, sr={d['default_samplerate']:.0f} Hz)")
    return devices


def record_real(sweep, cfg):
    """Играет sweep и одновременно пишет с микрофона (UMIK-1)."""
    import sounddevice as sd

    sr = int(cfg["sample_rate"])
    device = (cfg["input_device"], cfg["output_device"])
    sd.check_input_settings(device=device[0], channels=1, samplerate=sr)
    sd.check_output_settings(device=device[1], channels=1, samplerate=sr)

    label = f"устройство #{cfg['input_device']}" if cfg["input_device"] is not None else "устройство по умолчанию"
    print(f"Playing sweep and recording: {label}...")

    recording = sd.playrec(
        np.pad(sweep, (0, int(sr * cfg["tail_duration"]))).reshape(-1, 1),
        device=device,
        samplerate=sr,
        channels=cfg["channels_in"],
        blocking=True,
    )
    sd.wait()
    return recording[:, 0]


def record_synthetic(sweep, cfg):
    """Синтетический прогон без железа: эмулируем отклик модельной комнаты."""
    print("Synthetic room recording (no microphone)")
    sr = int(cfg["sample_rate"])

    # простая модельная комната: прямой звук + пара поздних отражений + шум пола
    ir_len = int(0.05 * sr)
    ir_model = np.zeros(ir_len)
    ir_model[0] = 1.0
    ir_model[int(0.008 * sr)] = 0.35
    ir_model[int(0.021 * sr)] = 0.20

    recording = fftconvolve(np.pad(sweep, (0, int(sr * cfg["tail_duration"]))), ir_model)[:len(sweep) + int(sr * cfg["tail_duration"])]
    recording = recording + np.random.default_rng(cfg["seed"]).normal(0, 0.00001, size=recording.shape)
    return recording.astype(np.float64)


def run_measurement(config_path="config.json", output_path="room_recording.wav", sweep_path="test_sweep.wav"):
    cfg = load_config(config_path)

    sweep = generate_swept_sine(
        f_start=cfg["f_start"],
        f_end=cfg["f_end"],
        duration=cfg["duration"],
        sample_rate=cfg["sample_rate"],
        amplitude=cfg["amplitude"],
    )
    Path(sweep_path).parent.mkdir(parents=True, exist_ok=True)
    save_to_wav(sweep, sweep_path, sample_rate=cfg["sample_rate"])

    if cfg["mode"] == "real":
        recording = record_real(sweep, cfg)
    else:
        recording = record_synthetic(sweep, cfg)

    if not np.isfinite(recording).all() or np.max(np.abs(recording)) < 1e-8:
        raise ValueError("Recording is silent or non-finite")
    if cfg["mode"] == "real" and np.max(np.abs(recording)) >= 0.999:
        raise ValueError("Recording clipped; reduce playback/input level and repeat")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, recording, int(cfg["sample_rate"]), subtype="FLOAT")

    print(f"Recording saved: {output_path} (mode: {cfg['mode']})")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ROOM·SCOPE — измерение комнаты (sweep + запись)")
    parser.add_argument("--config", default="config.json", help="путь к config.json")
    parser.add_argument("--sweep-out", default="test_sweep.wav")
    parser.add_argument("--out", default="room_recording.wav", help="куда сохранить запись")
    parser.add_argument("--list-devices", action="store_true", help="показать список аудиоустройств и выйти")
    args = parser.parse_args()

    if args.list_devices:
        list_input_devices()
    else:
        run_measurement(args.config, args.out, args.sweep_out)
