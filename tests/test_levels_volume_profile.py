import pandas as pd
import pytest

from levels import volume_profile


def _bars(rows):
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="1min", tz="UTC")
    return pd.DataFrame(rows, index=idx, columns=["High", "Low", "Close", "Volume"])


def test_build_profile_splits_volume_uniformly_across_bar_range():
    # single bar spanning [100, 102] with bin_size=1 -> two bins, half the
    # volume each (uniform-across-range approximation).
    data = _bars([[102, 100, 101, 20]])
    profile = volume_profile.build_profile(data, bin_size=1)
    assert profile[100] == pytest.approx(10.0)
    assert profile[101] == pytest.approx(10.0)


def test_build_profile_zero_range_bar_goes_entirely_into_one_bin():
    data = _bars([[100, 100, 100, 15]])
    profile = volume_profile.build_profile(data, bin_size=1)
    assert profile.sum() == pytest.approx(15.0)
    assert profile[100] == pytest.approx(15.0)


def test_build_profile_rejects_nonpositive_bin_size():
    data = _bars([[102, 100, 101, 20]])
    with pytest.raises(ValueError):
        volume_profile.build_profile(data, bin_size=0)


def test_poc_returns_highest_volume_bin():
    profile = pd.Series([5.0, 40.0, 12.0], index=[100.0, 101.0, 102.0])
    assert volume_profile.poc(profile) == pytest.approx(101.0)


def test_poc_rejects_empty_profile():
    with pytest.raises(ValueError):
        volume_profile.poc(pd.Series(dtype=float))


def test_hvn_lvn_finds_local_extremes():
    # index:   0    1    2    3    4    5    6
    values = [10.0, 5.0, 40.0, 5.0, 2.0, 30.0, 10.0]
    bins = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]
    profile = pd.Series(values, index=bins)
    hvn, lvn = volume_profile.hvn_lvn(profile, n=1)
    assert 102.0 in hvn  # local max (40, surrounded by 5s)
    assert 105.0 in hvn  # local max (30, surrounded by 2 and 10)
    assert 104.0 in lvn  # local min (2, surrounded by 5 and 30)


def test_hvn_ignores_zero_volume_bins():
    values = [0.0, 0.0, 0.0]
    profile = pd.Series(values, index=[100.0, 101.0, 102.0])
    hvn, lvn = volume_profile.hvn_lvn(profile, n=1)
    assert hvn == []
