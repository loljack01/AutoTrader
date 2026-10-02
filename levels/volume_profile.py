"""Approximate volume profile from OHLCV bars (added for the user's
confirmation-checklist framework, not part of the original PDF spec).

A real volume profile needs trade-level (tape) data. From OHLCV alone we
approximate each bar's volume as spread UNIFORMLY across its [Low, High]
range into fixed-width price bins - the standard approximation when only
bar data is available. It is weaker than a real footprint/tape-based
profile and never claims otherwise.
"""

import numpy as np
import pandas as pd


def build_profile(data: pd.DataFrame, bin_size: float) -> pd.Series:
    """Returns a Series indexed by each bin's lower price edge, holding
    the approximate volume traded in that bin across all of `data`."""
    if bin_size <= 0:
        raise ValueError("bin_size must be positive")
    if data.empty:
        raise ValueError("data is empty")

    low = float(data.Low.min())
    high = float(data.High.max())
    n_bins = int(np.ceil((high - low) / bin_size)) + 1
    edges = low + np.arange(n_bins + 1) * bin_size
    volume_by_bin = np.zeros(n_bins)

    for bar_low, bar_high, vol in zip(data.Low.to_numpy(), data.High.to_numpy(), data.Volume.to_numpy()):
        if vol <= 0:
            continue
        span = bar_high - bar_low
        if span <= 0:
            bin_idx = min(max(int((bar_low - low) / bin_size), 0), n_bins - 1)
            volume_by_bin[bin_idx] += vol
            continue
        first_bin = max(int((bar_low - low) / bin_size), 0)
        last_bin = min(int((bar_high - low) / bin_size), n_bins - 1)
        for b in range(first_bin, last_bin + 1):
            overlap = max(0.0, min(bar_high, edges[b + 1]) - max(bar_low, edges[b]))
            volume_by_bin[b] += vol * (overlap / span)

    return pd.Series(volume_by_bin, index=edges[:-1])


def poc(profile: pd.Series) -> float:
    """Point of Control: the bin (lower edge) holding the most volume."""
    if profile.empty:
        raise ValueError("profile is empty")
    return float(profile.idxmax())


def hvn_lvn(profile: pd.Series, n: int = 2):
    """Returns (hvn_levels, lvn_levels): price levels of local volume
    maxima/minima - a bin only counts if it is the strict extreme of its
    `n`-bin neighborhood on each side (same fractal logic as
    levels.structure.find_swings, applied to volume instead of price)."""
    values = profile.to_numpy()
    bins = profile.index.to_numpy()
    n_bins = len(values)
    hvn, lvn = [], []
    for i in range(n, n_bins - n):
        window = values[i - n : i + n + 1]
        if values[i] == window.max() and values[i] > 0:
            hvn.append(float(bins[i]))
        if values[i] == window.min():
            lvn.append(float(bins[i]))
    return hvn, lvn
