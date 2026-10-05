import json

import numpy as np
import pytest
import soundfile as sf

from dsp.swept_sine import generate_swept_sine
from dsp.impulse_response import generate_inverse_filter, deconvolve, calculate_ir_metrics, save_ir
from dsp.octave_smoothing import get_third_octave_edges, calculate_frequency_response
from measurement import load_config, DEFAULT_CONFIG, run_measurement, record_real
from compare_profiles import compare, load_profile
from pipeline import run


def test_third_octave_edges_are_one_third_octave_wide():
    low, high = get_third_octave_edges(1000)
    assert np.log2(high / low) == pytest.approx(1 / 3)


def test_response_preserves_gain_between_measurements():
    ir = np.zeros(4800)
    ir[0] = 1
    a, centers = calculate_frequency_response(ir)
    b, _ = calculate_frequency_response(ir * 0.5)
    assert len(centers) == 31
    np.testing.assert_allclose(a, 0, atol=1e-8)
    np.testing.assert_allclose(b - a, 20 * np.log10(0.5), atol=1e-8)


@pytest.mark.parametrize('values', [np.zeros(100), [1, np.nan], [[1, 2], [3, 4]], []])
def test_response_rejects_invalid_recordings(values):
    with pytest.raises(ValueError):
        calculate_frequency_response(values)


@pytest.mark.parametrize('params', [{'duration': 0}, {'amplitude': 2}, {'f_end': 24000}, {'sample_rate': 1}, {'duration': float('nan')}])
def test_sweep_rejects_invalid_parameters(params):
    with pytest.raises(ValueError):
        generate_swept_sine(**params)


def test_short_sweep_fade_does_not_broadcast_fail():
    assert len(generate_swept_sine(duration=0.001)) == 48


def test_deconvolution_recovers_delay_and_reflection():
    sr = 48000
    sweep = generate_swept_sine(duration=1, amplitude=0.1)
    room = np.zeros(2400)
    room[240] = 0.7
    room[1200] = 0.2
    from scipy.signal import fftconvolve
    result = deconvolve(fftconvolve(sweep, room), generate_inverse_filter(sweep))
    offset = len(sweep) - 1
    assert np.argmax(np.abs(result)) == offset + 240
    assert result[offset + 240] == pytest.approx(0.7, abs=0.01)
    assert result[offset + 1200] == pytest.approx(0.2, abs=0.01)
    values, centers = calculate_frequency_response(deconvolve(sweep, generate_inverse_filter(sweep)), sr)
    middle = values[(centers >= 100) & (centers <= 10000)]
    assert np.ptp(middle) < 0.5


def test_rt60_uses_energy_decay_instead_of_first_zero_crossing():
    sr = 48000
    t = np.arange(sr) / sr
    ir = np.exp(-np.log(1000) * t / 0.6) * np.cos(2 * np.pi * 1000 * t)
    assert calculate_ir_metrics(ir, sr)['rt60_estimate_sec'] == pytest.approx(0.6, abs=0.01)
    assert calculate_ir_metrics(np.zeros(100))['rt60_estimate_sec'] is None


def test_ir_file_preserves_amplitude(tmp_path):
    ir = np.array([0.0, 2.4, 0.3, -1.5])
    path = tmp_path / 'nested' / 'ir.wav'
    save_ir(ir, path)
    read, _ = sf.read(path)
    np.testing.assert_allclose(read, ir, atol=1e-6)


def test_config_rejects_unknown_mode_and_missing_file(tmp_path):
    path = tmp_path / 'config.json'
    with pytest.raises(ValueError):
        load_config(path)
    path.write_text('{"mode":"raell"}')
    with pytest.raises(ValueError):
        load_config(path)


def test_real_recording_passes_devices_and_keeps_tail(monkeypatch):
    import sounddevice as sd
    called = {}
    monkeypatch.setattr(sd, 'check_input_settings', lambda **kwargs: None)
    monkeypatch.setattr(sd, 'check_output_settings', lambda **kwargs: None)
    monkeypatch.setattr(sd, 'wait', lambda: None)
    def playrec(data, **kwargs):
        called.update(kwargs)
        return np.zeros_like(data)
    monkeypatch.setattr(sd, 'playrec', playrec)
    cfg = {**DEFAULT_CONFIG, 'input_device': 2, 'output_device': 4}
    result = record_real(np.ones(100), cfg)
    assert result.shape == (48100,)
    assert called['device'] == (2, 4)


def test_clipped_real_recording_is_rejected(monkeypatch, tmp_path):
    import measurement
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps({**DEFAULT_CONFIG, 'mode': 'real', 'duration': 0.1}))
    monkeypatch.setattr(measurement, 'record_real', lambda *_: np.ones(100))
    with pytest.raises(ValueError, match='clipped'):
        run_measurement(cfg, tmp_path / 'recording.wav', tmp_path / 'sweep.wav')
    assert not (tmp_path / 'recording.wav').exists()


def test_pipeline_roundtrip_and_protects_existing_session(tmp_path):
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps({**DEFAULT_CONFIG, 'duration': 0.2}))
    profile = run(cfg, tmp_path / 'session', 'Test A')
    data = json.loads(profile.read_text())
    assert data['source'] == 'synthetic'
    assert data['response']['reference'] == 'sweep-relative'
    assert len(data['response']['centers_hz']) == 29
    parsed = load_profile(profile)
    assert compare(parsed, parsed)[1]['rms_delta_db'] == 0
    with pytest.raises(ValueError, match='not empty'):
        run(cfg, tmp_path / 'session', 'Overwrite')


def test_comparison_rejects_different_lengths_and_nan():
    valid = {'centers': np.array([20, 25, 31.5]), 'smoothed_db': np.zeros(3)}
    invalid = {'centers': np.array([20, 25]), 'smoothed_db': np.zeros(2)}
    with pytest.raises(ValueError):
        compare(valid, invalid)
    with pytest.raises(ValueError):
        compare(valid, {**valid, 'smoothed_db': np.array([0, np.nan, 0])})
