import numpy as np
import pandas as pd

from levels import structure


def _ohlc(closes, idx=None):
    closes = np.array(closes, dtype=float)
    idx = idx or pd.date_range("2026-01-01", periods=len(closes), freq="h")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes + 0.1,
            "Low": closes - 0.1,
            "Close": closes,
        },
        index=idx,
    )


def test_find_swings_marks_a_simple_v_shape_pivot():
    # down-down-LOW-up-up: bar 2 is a swing low with n=2 either side.
    data = _ohlc([10, 9, 8, 9, 10])
    _, is_low = structure.find_swings(data, n=2)
    assert list(is_low) == [False, False, True, False, False]


def test_find_swings_marks_a_simple_peak():
    data = _ohlc([8, 9, 10, 9, 8])
    is_high, _ = structure.find_swings(data, n=2)
    assert list(is_high) == [False, False, True, False, False]


def test_find_swings_tie_keeps_only_the_first_extreme():
    # Two equal highs (bars 2 and 4) within the same n=2 window of each
    # other - SPEC: the first is the swing, the second is not (it forms
    # an EQH instead, handled by levels/liquidity.py).
    data = _ohlc([8, 9, 10, 9, 10, 9, 8])
    is_high, _ = structure.find_swings(data, n=2)
    assert is_high.iloc[2] is np.True_ or is_high.iloc[2] == True  # noqa: E712
    assert not is_high.iloc[4]


def test_confirmed_marks_only_set_at_the_confirmation_bar():
    data = _ohlc([10, 9, 8, 9, 10, 11, 12])
    is_low, _ = structure.find_swings(data, n=2)[1], None
    is_high, is_low = structure.find_swings(data, n=2)
    marks = structure.confirmed_marks(is_low, data.Low, n=2)
    # The swing low is at bar 2; confirmed at bar 2+2=4.
    assert np.isnan(marks.iloc[3])
    assert marks.iloc[4] == data.Low.iloc[2]


def test_confirmed_level_is_not_visible_before_confirmation():
    data = _ohlc([10, 9, 8, 9, 10, 11, 12])
    is_high, is_low = structure.find_swings(data, n=2)
    level = structure.confirmed_level(is_low, data.Low, n=2)
    # Before the confirmation bar (index 4), nothing is known yet.
    assert level.iloc[:4].isna().all()
    assert level.iloc[4] == data.Low.iloc[2]
    assert level.iloc[6] == data.Low.iloc[2]  # forward-filled


def test_bos_events_fire_on_close_breaking_a_confirmed_level():
    idx = pd.date_range("2026-01-01", periods=8, freq="h")
    close = pd.Series([100, 99, 98, 99, 100, 101, 105, 104], index=idx)
    swing_high_level = pd.Series([np.nan] * 5 + [100, 100, 100], index=idx)
    swing_low_level = pd.Series([np.nan] * 8, index=idx)

    bullish, bearish = structure.bos_events(close, swing_high_level, swing_low_level)
    assert not bullish.iloc[:5].any()
    assert bullish.iloc[6]  # close=105 > 100
    assert not bearish.any()


def test_choch_only_fires_on_the_first_reversal_not_on_continuation():
    idx = pd.date_range("2026-01-01", periods=6, freq="h")
    bullish_bos = pd.Series([True, True, False, False, False, True], index=idx)
    bearish_bos = pd.Series([False, False, True, True, False, False], index=idx)

    choch = structure.choch_events(bullish_bos, bearish_bos)
    # bar 0: first bullish BOS ever -> CHoCH (state was None)
    # bar 1: second bullish BOS in a row -> continuation, not CHoCH
    # bar 2: first bearish BOS after being 'up' -> CHoCH
    # bar 3: second bearish BOS in a row -> continuation
    # bar 5: first bullish BOS after being 'down' -> CHoCH
    assert list(choch) == [True, False, True, False, False, True]


def test_classify_trend_bullish_on_higher_highs_and_higher_lows():
    # Two clean up-legs: low 8 -> high 12 -> higher low 9 -> higher high 13
    data = _ohlc([10, 9, 8, 9, 10, 11, 12, 11, 10, 9, 11, 12, 13, 12, 11])
    is_high, is_low = structure.find_swings(data, n=2)
    trend = structure.classify_trend(is_high, data.High, is_low, data.Low, n=2)
    assert trend.iloc[-1] == "bullish"


def test_classify_trend_starts_as_range_before_two_swings_of_each_confirm():
    data = _ohlc([10, 9, 8, 9, 10])
    is_high, is_low = structure.find_swings(data, n=2)
    trend = structure.classify_trend(is_high, data.High, is_low, data.Low, n=2)
    assert (trend == "range").all()
