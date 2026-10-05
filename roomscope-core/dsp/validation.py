"""Shared numerical contracts; invalid data must never become a plausible plot."""
import numpy as np


def mono_signal(values, name="signal"):
    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or data.size < 2 or not np.isfinite(data).all():
        raise ValueError(f"{name} must be a finite mono signal with at least 2 samples")
    return data


def response_arrays(centers, values):
    centers = mono_signal(centers, "frequencies")
    values = mono_signal(values, "response")
    if centers.shape != values.shape or np.any(centers <= 0) or np.any(np.diff(centers) <= 0):
        raise ValueError("Response requires equal-length arrays and increasing positive frequencies")
    return centers, values
