"""ROOM·SCOPE — сравнение двух профилей (A/B по позиции колонки/слушателя).

Сценарий: замерил АЧХ в позиции A -> сохранил profile_A.json -> подвинул
колонку -> замерил снова -> сохранил profile_B.json -> сравнил:

    python compare_profiles.py profiles/seatA_default.json profiles/seatA_moved18cm.json

Печатает таблицу по 1/3-октавным полосам (было -> стало -> дельта), общий
RMS-дельта и тройку самых заметных изменений. С флагом --plot строит график
"было vs стало".
"""
import argparse
import json

import numpy as np
from dsp.validation import response_arrays
from pathlib import Path


def load_profile(path):
    with open(path, 'r', encoding='utf-8') as f:
        profile = json.load(f)
    response = profile.get('response') or {}
    centers = response.get('centers_hz')
    smoothed_db = response.get('smoothed_db')
    if not centers or not smoothed_db:
        raise ValueError(
            f"'{path}' не содержит кривую АЧХ (response.centers_hz/smoothed_db). "
            "Профиль нужно пересчитать через обновлённый dsp/peq_calculator.py (>=0.2)."
        )
    response_arrays(centers, smoothed_db)
    return {
        'reference': response.get("reference", "legacy-peak-normalized"),
        'label': profile.get('label') or path,
        'centers': np.array(centers, dtype=float),
        'smoothed_db': np.array(smoothed_db, dtype=float),
    }


def compare(profile_a, profile_b):
    """Возвращает список по полосам + сводные метрики. Чистая функция — без файлового I/O."""
    for profile in (profile_a, profile_b):
        response_arrays(profile['centers'], profile['smoothed_db'])
    if profile_a.get('reference') != profile_b.get('reference'):
        raise ValueError("Profiles use different level references")
    if profile_a['centers'].shape != profile_b['centers'].shape or not np.allclose(profile_a['centers'], profile_b['centers']):
        raise ValueError(
            "Профили посчитаны с разными наборами 1/3-октавных полос — сравнение невозможно "
            "(проверь, что оба через одну и ту же octave_smoothing.get_third_octave_centers)."
        )

    centers = profile_a['centers']
    delta = profile_b['smoothed_db'] - profile_a['smoothed_db']

    bands = []
    for f, a_db, b_db, d in zip(centers, profile_a['smoothed_db'], profile_b['smoothed_db'], delta):
        bands.append({
            'freq_hz': float(f),
            'a_db': float(a_db),
            'b_db': float(b_db),
            'delta_db': float(d),
        })

    rms_delta = float(np.sqrt(np.mean(delta ** 2)))
    mean_delta = float(np.mean(delta))
    best_idx = int(np.argmax(delta))    # смещение вверх = стало больше энергии в полосе
    worst_idx = int(np.argmin(delta))   # смещение вниз = провал стал глубже (или пик срезан — смотри знак)

    summary = {
        'rms_delta_db': round(rms_delta, 2),
        'mean_delta_db': round(mean_delta, 2),
        'biggest_gain': bands[best_idx],
        'biggest_drop': bands[worst_idx],
    }
    return bands, summary


def print_report(label_a, label_b, bands, summary, flat_tolerance_db=0.5):
    print('=' * 72)
    print('ROOM·SCOPE — сравнение позиций')
    print(f'  A: {label_a}')
    print(f'  B: {label_b}')
    print('=' * 72)
    print(f"{'Freq':>8} | {'A, dB':>7} | {'B, dB':>7} | {'Δ, dB':>7} | вердикт")
    print('-' * 72)
    for b in bands:
        f = b['freq_hz']
        freq_label = f'{f:.0f}' if f < 1000 else f'{f/1000:.1f}k'
        d = b['delta_db']
        if abs(d) < flat_tolerance_db:
            verdict = '≈ без изменений'
        elif d > 0:
            verdict = '▲ стало больше'
        else:
            verdict = '▼ стало меньше'
        print(f"{freq_label:>8} | {b['a_db']:>7.1f} | {b['b_db']:>7.1f} | {d:>+7.1f} | {verdict}")
    print('-' * 72)
    print(f"RMS-дельта по всему диапазону : {summary['rms_delta_db']:+.2f} дБ")
    print(f"Средняя дельта                : {summary['mean_delta_db']:+.2f} дБ")
    print(f"Сильнее всего выросло         : {summary['biggest_gain']['freq_hz']:.0f} Hz "
          f"({summary['biggest_gain']['delta_db']:+.1f} дБ)")
    print(f"Сильнее всего просело         : {summary['biggest_drop']['freq_hz']:.0f} Hz "
          f"({summary['biggest_drop']['delta_db']:+.1f} дБ)")
    print('=' * 72)
    if summary['rms_delta_db'] < 0 or abs(summary['mean_delta_db']) > 1.0:
        pass  # интерпретация направления (лучше/хуже) зависит от цели (flat) — оставляем пользователю таблицу


def save_plot(label_a, label_b, bands, out_path):
    import matplotlib.pyplot as plt

    freqs = [b['freq_hz'] for b in bands]
    a_vals = [b['a_db'] for b in bands]
    b_vals = [b['b_db'] for b in bands]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.semilogx(freqs, a_vals, 'o-', color='#878d97', linewidth=2, markersize=5, label=label_a)
    ax.semilogx(freqs, b_vals, 'o-', color='#57c9a8', linewidth=2, markersize=5, label=label_b)
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_title('ROOM·SCOPE — сравнение позиций (A vs B)')
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Amplitude (dB)')
    ax.set_xlim(20, 20000)
    ax.grid(True, which='both', ls='--', alpha=0.4)
    ax.set_xticks([20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax.set_xticklabels(['20', '50', '100', '200', '500', '1k', '2k', '5k', '10k', '20k'])
    ax.legend()
    plt.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'✅ График сохранён: {out_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ROOM·SCOPE — сравнение двух профилей позиции (A/B)')
    parser.add_argument('profile_a', help='путь к profile A (например, до перемещения колонки)')
    parser.add_argument('profile_b', help='путь к profile B (после перемещения)')
    parser.add_argument('--plot', default=None, help='сохранить сравнительный график в этот файл (PNG)')
    parser.add_argument('--flat-tolerance-db', type=float, default=0.5, help='порог "без изменений", дБ')
    args = parser.parse_args()

    a = load_profile(args.profile_a)
    b = load_profile(args.profile_b)
    bands, summary = compare(a, b)
    print_report(a['label'], b['label'], bands, summary, flat_tolerance_db=args.flat_tolerance_db)

    if args.plot:
        save_plot(a['label'], b['label'], bands, args.plot)
