"""ROOM·SCOPE — генерация логарифмического swept sine"""
import numpy as np
from scipy import signal
import soundfile as sf

def generate_swept_sine(f_start=20.0, f_end=20000.0, duration=10.0, sample_rate=48000.0, amplitude=0.9):
    params = [f_start, f_end, duration, sample_rate, amplitude]
    if not np.isfinite(params).all() or not (0 < f_start < f_end < sample_rate / 2):
        raise ValueError("Sweep frequencies must be positive, ordered and below Nyquist")
    if not (0 < duration <= 120) or sample_rate != int(sample_rate) or not (0 < amplitude <= 1):
        raise ValueError("Invalid duration, sample rate or amplitude")
    if int(sample_rate * duration) < 2:
        raise ValueError("Sweep must contain at least two samples")
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    sweep = signal.chirp(t, f0=f_start, f1=f_end, t1=duration, method="logarithmic")
    fade = min(max(1, int(0.01 * sample_rate)), len(t) // 2)
    sweep[:fade] *= np.linspace(0, 1, fade)
    sweep[-fade:] *= np.linspace(1, 0, fade)
    return sweep * amplitude

def save_to_wav(sweep, filepath, sample_rate=48000.0):
    sf.write(filepath, sweep, int(sample_rate), subtype="PCM_24")
    print(f"Saved: {filepath}")

if __name__ == "__main__":
    sweep = generate_swept_sine()
    save_to_wav(sweep, "test_sweep.wav")
