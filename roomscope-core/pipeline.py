"""One reproducible measurement -> IR -> response -> profile run."""
import argparse
import json
from pathlib import Path

import soundfile as sf
from measurement import load_config, run_measurement
from dsp.impulse_response import generate_inverse_filter, deconvolve, save_ir
from dsp.octave_smoothing import calculate_frequency_response
from dsp.peq_calculator import calculate_peq_filters, save_profile_json


def run(config, output, label):
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120:
        raise ValueError("Label must contain 1..120 characters")
    cfg = load_config(config)
    output = Path(output)
    # Refuse to overwrite a previous session: A/B needs its original measurement.
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    run_measurement(config, output / "recording.wav", output / "sweep.wav")
    sweep, sr = sf.read(output / "sweep.wav")
    recording, _ = sf.read(output / "recording.wav")
    inverse = generate_inverse_filter(sweep, sr, cfg["f_start"], cfg["f_end"])
    ir = deconvolve(recording, inverse)
    save_ir(ir, output / "ir.wav", sr)
    values, centers = calculate_frequency_response(ir, sr)
    # Only report complete analysis bands inside the sweep's usable frequency range.
    mask = (centers / 2**(1/6) >= cfg["f_start"]) & (centers * 2**(1/6) <= cfg["f_end"])
    centers, values = centers[mask], values[mask]
    filters = calculate_peq_filters(centers, values)
    save_profile_json(filters, centers, values, output / "profile.json", label, source=cfg["mode"])
    return output / "profile.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    parser.add_argument("--out", default="output/session")
    parser.add_argument("--label", default="Listening position")
    args = parser.parse_args()
    try:
        print(run(args.config, args.out, args.label))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Measurement failed: {error}\n")
