"""ROOM·SCOPE — 1/3 октавное сглаживание"""
import numpy as np
from scipy.fft import rfft, rfftfreq
from dsp.validation import mono_signal, response_arrays
import soundfile as sf
import matplotlib.pyplot as plt

def get_third_octave_centers(f_min=20.0, f_max=20000.0):
    base = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]
    return np.array([f for f in base if f_min <= f <= f_max])

def get_third_octave_edges(fc):
    ratio = 2 ** (1 / 6)
    return fc / ratio, fc * ratio

def third_octave_smoothing(mag_db, freqs):
    freqs, mag_db = response_arrays(freqs, mag_db)
    centers = get_third_octave_centers(max(20, freqs[0]), min(20000, freqs[-1]))
    smoothed = []

    for fc in centers:
        fl, fu = get_third_octave_edges(fc)
        mask = (freqs >= fl) & (freqs < fu)

        if np.sum(mask) > 0:
            # Считаем среднее значение АЧХ в дБ для этой полосы
            band_values = mag_db[mask]
            avg = 10 * np.log10(np.mean(10 ** (band_values / 10)))
            smoothed.append(avg)
        else:
            smoothed.append(float(np.interp(fc, freqs, mag_db)))

    return np.array(smoothed), centers

def calculate_frequency_response(ir, sr=48000.0, smooth=True):
    ir = mono_signal(ir, "IR")
    if not np.isfinite(sr) or sr <= 0:
        raise ValueError("Sample rate must be positive")
    if not np.any(ir):
        raise ValueError("Silent IR cannot produce a frequency response")
    # Preserve transfer gain: do not normalize each measurement to its own peak.
    n = max(len(ir), int(sr))
    f = rfftfreq(n, 1 / sr)[1:]
    mag = np.abs(rfft(ir, n=n))[1:]
    mag_db = 20 * np.log10(np.maximum(mag, 1e-12))

    if smooth:
        return third_octave_smoothing(mag_db, f)
    return f, mag_db

if __name__ == "__main__":
    print("=" * 60)
    print("ROOM·SCOPE — 1/3 октавное сглаживание")
    print("=" * 60)

    ir, sr = sf.read("test_ir.wav")
    print(f"IR: {len(ir)} samples, {sr} Hz")

    smoothed_db, centers = calculate_frequency_response(ir, sr, smooth=True)

    print(f"Полос: {len(centers)}")
    print(f"Первые 5 частот: {centers[:5]}")
    print(f"Первые 5 значений АЧХ: {smoothed_db[:5]} dB")
    print(f"АЧХ диапазон: {smoothed_db.min():.2f} ... {smoothed_db.max():.2f} dB")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.semilogx(centers, smoothed_db, 'o-', color='#2ca02c', linewidth=2, markersize=6)
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_title("Frequency Response (1/3 octave smoothing)")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Amplitude (dB)")
    ax.set_xlim(20, 20000)
    # Autoscale: a fixed -3..1 dB range concealed real room variation.
    ax.grid(True, which="both", ls="--", alpha=0.5)
    ax.set_xticks([20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax.set_xticklabels(['20', '50', '100', '200', '500', '1k', '2k', '5k', '10k', '20k'])

    plt.tight_layout()
    plt.savefig("freq_response_1_3_octave.png", dpi=150)
    print("✅ Сохранено: freq_response_1_3_octave.png")
