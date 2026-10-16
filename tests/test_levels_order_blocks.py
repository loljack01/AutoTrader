import pandas as pd

from levels import order_blocks


def _bar(o, h, l, c):
    return {"Open": o, "High": h, "Low": l, "Close": c}


def test_bearish_ob_is_the_last_bullish_candle_before_the_bos():
    idx = pd.date_range("2026-01-01", periods=4, freq="h")
    data = pd.DataFrame(
        [
            _bar(100, 102, 99, 101),  # 0 bullish - the OB candle
            _bar(101, 101.5, 98, 98.5),  # 1 bearish
            _bar(98.5, 99, 95, 96),  # 2 bearish, impulse
            _bar(96, 96.5, 93, 94),  # 3 bearish, BOS confirms here
        ],
        index=idx,
    )
    bearish_bos = pd.Series([False, False, False, True], index=idx)
    bullish_bos = pd.Series(False, index=idx)

    obs = order_blocks.find_order_blocks(data, bullish_bos, bearish_bos)

    assert len(obs) == 1
    ob = obs[0]
    assert ob["type"] == "bearish"
    assert ob["candle_at"] == idx[0]
    assert ob["top"] == 102
    assert ob["bottom"] == 99
    assert ob["confirmed_at"] == idx[3]


def test_bullish_ob_is_the_last_bearish_candle_before_the_bos():
    idx = pd.date_range("2026-01-01", periods=4, freq="h")
    data = pd.DataFrame(
        [
            _bar(100, 101, 98, 99),  # 0 bearish - the OB candle
            _bar(99, 101, 98.5, 100.5),  # 1 bullish
            _bar(100.5, 104, 100, 103),  # 2 bullish, impulse
            _bar(103, 107, 102.5, 106),  # 3 bullish, BOS confirms here
        ],
        index=idx,
    )
    bullish_bos = pd.Series([False, False, False, True], index=idx)
    bearish_bos = pd.Series(False, index=idx)

    obs = order_blocks.find_order_blocks(data, bullish_bos, bearish_bos)

    assert len(obs) == 1
    ob = obs[0]
    assert ob["type"] == "bullish"
    assert ob["candle_at"] == idx[0]
    assert ob["top"] == 101
    assert ob["bottom"] == 98


def test_no_ob_recorded_when_no_opposite_candle_precedes_the_bos():
    idx = pd.date_range("2026-01-01", periods=2, freq="h")
    data = pd.DataFrame(
        [_bar(100, 101, 99, 98), _bar(98, 98.5, 95, 96)], index=idx  # both bearish
    )
    bearish_bos = pd.Series([False, True], index=idx)
    bullish_bos = pd.Series(False, index=idx)

    obs = order_blocks.find_order_blocks(data, bullish_bos, bearish_bos)
    assert obs == []
