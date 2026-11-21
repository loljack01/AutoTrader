import pandas as pd

from levels import fvg


def _bar(o, h, l, c):
    return {"Open": o, "High": h, "Low": l, "Close": c}


def test_find_fvgs_detects_bearish_gap():
    # bar0 low=100, bar1 whatever, bar2 high=98 < bar0 low=100 -> bearish FVG [98, 100]
    idx = pd.date_range("2026-01-01", periods=3, freq="h")
    data = pd.DataFrame(
        [_bar(102, 103, 100, 101), _bar(99, 99.5, 97, 98), _bar(97, 98, 96, 97)],
        index=idx,
    )
    gaps = fvg.find_fvgs(data)
    assert len(gaps) == 1
    assert gaps[0]["type"] == "bearish"
    assert gaps[0]["top"] == 100
    assert gaps[0]["bottom"] == 98
    assert gaps[0]["created_at"] == idx[2]


def test_find_fvgs_detects_bullish_gap():
    # bar0 high=100, bar2 low=103 > bar0 high=100 -> bullish FVG [100, 103]
    idx = pd.date_range("2026-01-01", periods=3, freq="h")
    data = pd.DataFrame(
        [
            _bar(98, 100, 97, 99),
            _bar(101, 102, 100.5, 101.5),
            _bar(103, 104, 103, 103.5),
        ],
        index=idx,
    )
    gaps = fvg.find_fvgs(data)
    assert len(gaps) == 1
    assert gaps[0]["type"] == "bullish"
    assert gaps[0]["bottom"] == 100
    assert gaps[0]["top"] == 103


def test_find_fvgs_none_when_bars_overlap_normally():
    idx = pd.date_range("2026-01-01", periods=3, freq="h")
    data = pd.DataFrame(
        [_bar(100, 101, 99, 100), _bar(100, 101, 99, 100), _bar(100, 101, 99, 100)],
        index=idx,
    )
    assert fvg.find_fvgs(data) == []


def test_mark_inversions_flips_a_bearish_fvg_once_price_closes_back_above():
    idx = pd.date_range("2026-01-01", periods=5, freq="h")
    data = pd.DataFrame(
        [
            _bar(102, 103, 100, 101),  # 0
            _bar(99, 99.5, 97, 98),  # 1
            _bar(97, 98, 96, 97),  # 2  <- bearish FVG [98,100] created here
            _bar(97, 99, 97, 98.5),  # 3  close 98.5, still below top=100
            _bar(99, 101, 98, 100.5),  # 4  close 100.5 > 100 -> inverted
        ],
        index=idx,
    )
    gaps = fvg.find_fvgs(data)
    fvg.mark_inversions(gaps, data)
    assert gaps[0]["inverted_at"] == idx[4]


def test_mark_inversions_none_if_never_crossed():
    idx = pd.date_range("2026-01-01", periods=4, freq="h")
    data = pd.DataFrame(
        [
            _bar(102, 103, 100, 101),
            _bar(99, 99.5, 97, 98),
            _bar(97, 98, 96, 97),
            _bar(97, 97.5, 96.5, 97),
        ],
        index=idx,
    )
    gaps = fvg.find_fvgs(data)
    fvg.mark_inversions(gaps, data)
    assert gaps[0]["inverted_at"] is None
