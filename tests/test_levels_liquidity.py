import numpy as np
import pandas as pd

from levels import liquidity


def _marks(pairs, idx):
    """pairs: {position_in_idx: price}"""
    s = pd.Series(np.nan, index=idx)
    for pos, price in pairs.items():
        s.iloc[pos] = price
    return s


def test_find_pools_groups_swings_within_tolerance():
    idx = pd.date_range("2026-01-01", periods=10, freq="h")
    marks = _marks({1: 100.0, 4: 100.5, 7: 105.0}, idx)  # 100 & 100.5 within 2pt tol
    atr = pd.Series(4.0, index=idx)  # 0.25*4=1.0, so min_points=2.0 governs

    pools = liquidity.find_pools(marks, atr, min_points=2.0, atr_mult=0.25)

    assert len(pools) == 1  # the 105.0 swing is alone, dropped (needs 2+ members)
    assert len(pools[0]["members"]) == 2
    assert pools[0]["level"] == 100.0


def test_find_pools_uses_atr_when_it_exceeds_the_floor():
    idx = pd.date_range("2026-01-01", periods=10, freq="h")
    # Gap of 3 points - outside the 2pt floor, but inside 0.25*ATR when ATR=20.
    marks = _marks({1: 100.0, 4: 103.0}, idx)
    atr = pd.Series(20.0, index=idx)

    pools = liquidity.find_pools(marks, atr, min_points=2.0, atr_mult=0.25)
    assert len(pools) == 1
    assert len(pools[0]["members"]) == 2


def test_find_pools_requires_at_least_two_members():
    idx = pd.date_range("2026-01-01", periods=5, freq="h")
    marks = _marks({1: 100.0}, idx)
    atr = pd.Series(4.0, index=idx)
    assert liquidity.find_pools(marks, atr) == []


def test_find_sweeps_detects_wick_through_then_close_back_for_eqh():
    idx = pd.date_range("2026-01-01", periods=8, freq="h")
    data = pd.DataFrame(
        {
            "Open": [100] * 8,
            "High": [100, 100, 100, 100, 100.5, 101.5, 100.2, 100],
            "Low": [99] * 8,
            "Close": [100, 100, 100, 100, 100.2, 100.8, 99.9, 100],
        },
        index=idx,
    )
    pools = [{"level": 101.0, "members": [(idx[1], 101.0), (idx[3], 101.0)]}]

    swept = liquidity.find_sweeps(pools, data, "high")
    # bar 5 (High=101.5 > 101.0, Close=100.8 < 101.0) is the sweep
    assert swept[0]["swept_at"] == idx[5]


def test_find_sweeps_none_if_never_swept():
    idx = pd.date_range("2026-01-01", periods=5, freq="h")
    data = pd.DataFrame(
        {"Open": [100] * 5, "High": [100] * 5, "Low": [99] * 5, "Close": [100] * 5},
        index=idx,
    )
    pools = [{"level": 105.0, "members": [(idx[0], 105.0), (idx[1], 105.0)]}]
    swept = liquidity.find_sweeps(pools, data, "high")
    assert swept[0]["swept_at"] is None


def test_find_sweeps_rejects_invalid_pool_type():
    import pytest

    with pytest.raises(ValueError):
        liquidity.find_sweeps([], pd.DataFrame(), "sideways")
