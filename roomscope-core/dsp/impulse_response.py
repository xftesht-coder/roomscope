"""ROOM·SCOPE — деконволюция IR (метод Farina)"""
import argparse
import os

import numpy as np
from scipy.fft import fft, ifft
import soundfile as sf
from dsp.swept_sine import generate_swept_sine
from dsp.validation import mono_signal
from scipy.signal import fftconvolve
from pathlib import Path

def generate_inverse_filter(sweep, sample_rate=48000.0, f_start=20.0, f_end=20000.0):
    sweep = mono_signal(sweep, "sweep")
    if not np.isfinite([sample_rate, f_start, f_end]).all() or not 0 < f_start < f_end < sample_rate / 2:
        raise ValueError("Invalid inverse-filter frequency range")
    t = np.arange(len(sweep)) / sample_rate
    inverse = sweep[::-1] * np.exp(-t * np.log(f_end / f_start) / (len(sweep) / sample_rate))
    reference_peak = fftconvolve(sweep, inverse)[len(sweep) - 1]
    if abs(reference_peak) < 1e-12:
        raise ValueError("Sweep has no usable energy")
    return inverse / reference_peak


def deconvolve(recorded, inverse_filter):
    recorded = mono_signal(recorded, "recording")
    inverse_filter = mono_signal(inverse_filter, "inverse filter")
    N = len(recorded) + len(inverse_filter) - 1
    N_fft = int(2 ** np.ceil(np.log2(N)))
    X = fft(recorded, n=N_fft)
    H_inv = fft(inverse_filter, n=N_fft)
    ir = np.real(ifft(X * H_inv))
    return ir[:N]

def calculate_ir_metrics(ir, sample_rate=48000.0):
    ir = mono_signal(ir, "IR")
    if not np.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError("Sample rate must be positive")
    peak_idx = int(np.argmax(np.abs(ir)))
    energy = np.cumsum(ir[peak_idx:][::-1] ** 2)[::-1]
    rt60 = None
    # Schroeder T20 fit, only when the measured tail spans -5 to -25 dB.
    if energy[0] > 0:
        decay = 10 * np.log10(np.maximum(energy / energy[0], 1e-15))
        selected = np.where((decay <= -5) & (decay >= -25))[0]
        if len(selected) >= 10 and decay[-1] <= -25:
            slope, _ = np.polyfit(selected / sample_rate, decay[selected], 1)
            if slope < 0:
                rt60 = round(float(-60 / slope), 6)
    return {"peak_time_sec": round(peak_idx / sample_rate, 6), "rt60_estimate_sec": rt60}


def save_ir(ir, filepath, sample_rate=48000.0):
    ir = mono_signal(ir, "IR")
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    sf.write(filepath, ir, int(sample_rate), subtype="FLOAT")
    print(f"IR saved: {filepath}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ROOM·SCOPE — деконволюция IR методом Farina. "
                    "Без --recording гоняет самотест (sweep против самого себя)."
    )
    parser.add_argument("--sweep", default="test_sweep.wav", help="файл сыгранного sweep (для --recording)")
    parser.add_argument("--recording", default=None, help="файл записи комнаты (из measurement.py); "
                         "если не указан — самотест на синтетическом sweep")
    parser.add_argument("--out", default="test_ir.wav", help="куда сохранить импульсный отклик")
    parser.add_argument("--f-start", type=float, default=20.0)
    parser.add_argument("--f-end", type=float, default=20000.0)
    args = parser.parse_args()

    print("=" * 60)
    print("ROOM·SCOPE — Деконволюция IR")
    print("=" * 60)

    if args.recording:
        if not os.path.exists(args.sweep):
            raise SystemExit(f"Не найден файл sweep: {args.sweep} (сначала запусти measurement.py)")
        sweep, sr = sf.read(args.sweep)
        recording, sr_rec = sf.read(args.recording)
        if sr_rec != sr:
            raise SystemExit(f"Частоты дискретизации не совпадают: sweep={sr} Hz, recording={sr_rec} Hz")
        print(f"Sweep: {args.sweep} ({len(sweep)} samples, {sr} Hz)")
        print(f"Recording: {args.recording} ({len(recording)} samples, {sr_rec} Hz)")
        inverse = generate_inverse_filter(sweep, sample_rate=sr, f_start=args.f_start, f_end=args.f_end)
        ir = deconvolve(recording, inverse)
        metrics = calculate_ir_metrics(ir, sample_rate=sr)
        for k, v in metrics.items():
            print(f"  {k}: {v}")
        save_ir(ir, args.out, sample_rate=sr)
    else:
        sweep = generate_swept_sine(f_start=args.f_start, f_end=args.f_end, duration=10, sample_rate=48000)
        inverse = generate_inverse_filter(sweep, sample_rate=48000, f_start=args.f_start, f_end=args.f_end)
        ir = deconvolve(sweep, inverse)
        metrics = calculate_ir_metrics(ir, sample_rate=48000)
        for k, v in metrics.items():
            print(f"  {k}: {v}")
        save_ir(ir, args.out, sample_rate=48000)

    print("✅ IR готов")
