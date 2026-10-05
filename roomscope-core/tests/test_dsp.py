"""ROOM·SCOPE — базовые unit-тесты DSP-ядра.

Запуск (в venv проекта, где уже стоят numpy/scipy/soundfile):
    pytest tests/test_dsp.py -v
"""
import numpy as np
import pytest

from dsp.swept_sine import generate_swept_sine
from dsp.octave_smoothing import get_third_octave_centers
from dsp.peq_calculator import calculate_peq_filters, save_profile_json


def test_generate_swept_sine_length_and_range():
    sr = 48000
    duration = 2.0
    sweep = generate_swept_sine(f_start=20, f_end=20000, duration=duration, sample_rate=sr, amplitude=0.9)
    assert len(sweep) == int(sr * duration)
    assert np.max(np.abs(sweep)) <= 0.9 + 1e-9


def test_third_octave_centers_cover_audio_band():
    centers = get_third_octave_centers()
    assert centers[0] == 20
    assert centers[-1] == 20000
    assert len(centers) == 31


def test_peq_does_not_boost_cancellation_nulls():
    centers = get_third_octave_centers()
    values = np.zeros(len(centers))
    values[15] = -20
    assert calculate_peq_filters(centers, values) == []


def test_peq_cuts_peaks_with_bounded_gain():
    centers = get_third_octave_centers()
    values = np.zeros(len(centers))
    values[5] = 25
    filters = calculate_peq_filters(centers, values)
    assert filters[0]["gain_db"] == -12
    assert filters[0]["freq_hz"] == 63
    assert 0.5 <= filters[0]["q_factor"] <= 10


def test_calculate_peq_filters_flat_response_returns_empty():
    centers = get_third_octave_centers()
    smoothed_db = np.zeros(len(centers))
    filters = calculate_peq_filters(centers, smoothed_db, threshold_db=2.0, max_filters=5)
    assert filters == []


def test_record_synthetic_matches_sweep_length():
    from measurement import record_synthetic, DEFAULT_CONFIG
    sr = 48000
    sweep = generate_swept_sine(f_start=20, f_end=20000, duration=1.0, sample_rate=sr, amplitude=0.9)
    cfg = dict(DEFAULT_CONFIG)
    cfg["sample_rate"] = sr
    recording = record_synthetic(sweep, cfg)
    assert len(recording) == len(sweep) + int(sr * cfg["tail_duration"])
    assert np.isfinite(recording).all()


def test_save_profile_json_includes_response_curve(tmp_path):
    """profile.json должен нести саму АЧХ (не только найденные PEQ-пики) —
    иначе compare_profiles.py нечего будет сравнивать между позициями A/B."""
    centers = get_third_octave_centers()
    smoothed_db = np.zeros(len(centers))
    out = tmp_path / "profile.json"

    save_profile_json([], centers=centers, smoothed_db=smoothed_db, filepath=str(out), label="seat_A / test")

    import json
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["roomscope_version"] == "0.3"
    assert data["label"] == "seat_A / test"
    assert data["response"]["centers_hz"] == list(centers.astype(float))
    assert len(data["response"]["smoothed_db"]) == len(centers)


def test_compare_profiles_detects_improvement(tmp_path):
    from compare_profiles import load_profile, compare

    centers = get_third_octave_centers()
    a_db = np.zeros(len(centers))
    dip = 15
    a_db[dip] = -8.0
    b_db = a_db.copy()
    b_db[dip] += 3.0  # "подвинули колонку" -> провал стал мельче

    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    save_profile_json([], centers=centers, smoothed_db=a_db, filepath=str(path_a), label="A")
    save_profile_json([], centers=centers, smoothed_db=b_db, filepath=str(path_b), label="B")

    profile_a = load_profile(str(path_a))
    profile_b = load_profile(str(path_b))
    bands, summary = compare(profile_a, profile_b)

    assert len(bands) == len(centers)
    dip_band = bands[dip]
    assert dip_band["delta_db"] == pytest.approx(3.0)
    assert summary["rms_delta_db"] > 0
    assert summary["biggest_gain"]["freq_hz"] == centers[dip]


def test_compare_profiles_rejects_mismatched_bands():
    from compare_profiles import compare

    profile_a = {"label": "A", "centers": np.array([20.0, 25.0, 31.5]), "smoothed_db": np.zeros(3)}
    profile_b = {"label": "B", "centers": np.array([20.0, 25.0, 40.0]), "smoothed_db": np.zeros(3)}

    with pytest.raises(ValueError):
        compare(profile_a, profile_b)
