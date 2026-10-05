import argparse
import numpy as np
from scipy.signal import find_peaks
import json
import soundfile as sf
from dsp.octave_smoothing import calculate_frequency_response
from dsp.validation import response_arrays
from pathlib import Path

def calculate_peq_filters(centers, smoothed_db, threshold_db=3.0, max_filters=5):
    centers, smoothed_db = response_arrays(centers, smoothed_db)
    if not np.isfinite(threshold_db) or threshold_db <= 0 or not isinstance(max_filters, int) or max_filters < 0:
        raise ValueError("Invalid PEQ limits")
    # Only attenuate local peaks above the median. Deep cancellation nulls are not boost targets.
    relative = smoothed_db - np.median(smoothed_db)
    peaks, properties = find_peaks(relative, prominence=threshold_db, height=threshold_db)
    filters = []
    for i in np.argsort(properties['prominences'])[::-1][:max_filters]:
        idx = peaks[i]
        left, right = max(0, idx - 1), min(len(centers) - 1, idx + 1)
        q = np.clip(centers[idx] / (centers[right] - centers[left]), 0.5, 10)
        filters.append({'type': 'peak', 'freq_hz': float(centers[idx]),
                        'gain_db': round(float(-min(relative[idx], 12)), 1), 'q_factor': round(float(q), 2)})
    return sorted(filters, key=lambda f: f['freq_hz'])


def save_profile_json(filters, centers=None, smoothed_db=None, filepath='profile.json', label=None, source='unknown'):
    """Сохраняет профиль позиции: и найденные PEQ-фильтры, и саму АЧХ (centers/smoothed_db).

    Кривая АЧХ нужна для сравнения двух позиций между собой (compare_profiles.py) —
    одних только найденных пиков для этого недостаточно.
    """
    centers, smoothed_db = response_arrays(centers, smoothed_db)
    profile = {
        'roomscope_version': '0.3',
        'label': label,
        'target': 'flat',
        'source': source,
        'microphone': 'unverified',
        'peq_status': 'suggestions-only',
        'peq_filters': filters,
        'response': {
            'reference': 'sweep-relative',
            'unit': 'dB',
            'centers_hz': [float(c) for c in centers] if centers is not None else None,
            'smoothed_db': [float(v) for v in smoothed_db] if smoothed_db is not None else None,
        },
    }
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False, allow_nan=False)
    print(f'Profile saved: {filepath}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ROOM·SCOPE — расчёт АЧХ и PEQ-фильтров из импульсного отклика')
    parser.add_argument('--ir', default='test_ir.wav', help='файл импульсного отклика (WAV)')
    parser.add_argument('--out', default='profile.json', help='куда сохранить профиль')
    parser.add_argument('--label', default=None, help='название позиции, напр. "seat_A / speaker default"')
    parser.add_argument('--threshold-db', type=float, default=2.0, help='порог для детекции пиков, дБ')
    parser.add_argument('--max-filters', type=int, default=5, help='максимум PEQ-фильтров')
    args = parser.parse_args()

    print('=' * 60)
    print('ROOM-SCOPE - PEQ Processing')
    print('=' * 60)
    ir, sr = sf.read(args.ir)
    print('IR analysis: ' + str(len(ir)) + ' samples, ' + str(sr) + ' Hz')
    smoothed_db, centers = calculate_frequency_response(ir, sr, smooth=True)
    filters = calculate_peq_filters(centers, smoothed_db, threshold_db=args.threshold_db, max_filters=args.max_filters)
    print('Filters found: ' + str(len(filters)))
    for i, f in enumerate(filters, 1):
        print('  ' + str(i) + '. Freq: ' + str(f['freq_hz']) + ' Hz | Gain: ' + str(f['gain_db']) + ' dB | Q: ' + str(f['q_factor']))
    if not filters:
        print('  (No peaks detected. Response is within tolerance).')
    save_profile_json(filters, centers=centers, smoothed_db=smoothed_db, filepath=args.out, label=args.label)
    print('=' * 60)
