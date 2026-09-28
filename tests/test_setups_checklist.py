import pandas as pd
import pytest

from setups import checklist


def _all_confirmations(**overrides):
    base = {name: True for name in checklist.CONFIRMATION_NAMES}
    base.update(overrides)
    return base


def test_evaluate_valid_when_score_meets_minimum():
    confirmations = _all_confirmations(breakout_volume=False, pullback_holds=False)  # 3 of 5
    result = checklist.evaluate("buy", confirmations, min_confirmations=3)
    assert result.score == 3
    assert result.valid


def test_evaluate_invalid_when_score_below_minimum():
    confirmations = _all_confirmations(breakout_volume=False, pullback_holds=False)  # 3 of 5
    result = checklist.evaluate("buy", confirmations, min_confirmations=4)
    assert result.score == 3
    assert not result.valid


def test_evaluate_lists_missing_confirmations():
    confirmations = _all_confirmations(structure_aligned=False, correct_side=False)
    result = checklist.evaluate("sell", confirmations, min_confirmations=3)
    assert set(result.missing) == {"structure_aligned", "correct_side"}


def test_evaluate_rejects_invalid_direction():
    with pytest.raises(ValueError):
        checklist.evaluate("sideways", _all_confirmations())


def test_evaluate_rejects_incomplete_confirmations_dict():
    incomplete = {name: True for name in checklist.CONFIRMATION_NAMES if name != "correct_side"}
    with pytest.raises(ValueError):
        checklist.evaluate("buy", incomplete)


def test_evaluate_rejects_unknown_confirmation_key():
    with pytest.raises(ValueError):
        checklist.evaluate("buy", _all_confirmations(cvd_delta=True))


def _bool_series(values):
    idx = pd.date_range("2026-01-01", periods=len(values), freq="1min", tz="UTC")
    return pd.Series(values, index=idx)


def test_structure_aligned_true_after_choch_then_distinct_bos():
    #                        0      1      2      3      4      5
    choch_bull = _bool_series([False, True, False, False, False, False])
    bos_bull = _bool_series([False, True, False, True, False, False])  # bar 1 = CHoCH's own BOS, bar 3 = confirming BOS
    choch_bear = _bool_series([False] * 6)
    bos_bear = _bool_series([False] * 6)

    bullish, bearish = checklist.structure_aligned(choch_bull, bos_bull, choch_bear, bos_bear, lookback=10)
    assert not bullish.iloc[2]  # CHoCH fired but no distinct confirming BOS yet
    assert bullish.iloc[3]  # confirming BOS just fired
    assert bullish.iloc[4]  # still within lookback, stays true
    assert not bearish.any()


def test_structure_aligned_false_when_only_choch_no_confirming_bos():
    choch_bull = _bool_series([False, True, False, False, False])
    bos_bull = _bool_series([False, True, False, False, False])  # only the CHoCH's own BOS bar
    choch_bear = _bool_series([False] * 5)
    bos_bear = _bool_series([False] * 5)

    bullish, _ = checklist.structure_aligned(choch_bull, bos_bull, choch_bear, bos_bear, lookback=10)
    assert not bullish.any()


def test_structure_aligned_false_outside_lookback_window():
    choch_bull = _bool_series([False, True, False, False, False, False])
    bos_bull = _bool_series([False, True, False, False, False, True])
    choch_bear = _bool_series([False] * 6)
    bos_bear = _bool_series([False] * 6)

    bullish, _ = checklist.structure_aligned(choch_bull, bos_bull, choch_bear, bos_bear, lookback=2)
    assert not bullish.iloc[5]  # confirming BOS at bar 5 is 4 bars after CHoCH at bar 1, past lookback=2


def _price_series(values):
    idx = pd.date_range("2026-01-01", periods=len(values), freq="1min", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


def test_zone_reclaimed_true_after_crossing_from_below():
    close = _price_series([98, 99, 101, 102])
    level = _price_series([100, 100, 100, 100])
    reclaimed = checklist.zone_reclaimed(close, level, "buy", lookback=2)
    assert not reclaimed.iloc[0]  # below, no prior side to reclaim from
    assert not reclaimed.iloc[1]  # still below
    assert reclaimed.iloc[2]  # just crossed above, was below within lookback
    assert reclaimed.iloc[3]  # still within lookback of being below


def test_zone_reclaimed_false_when_always_above():
    close = _price_series([105, 106, 107, 108])
    level = _price_series([100, 100, 100, 100])
    reclaimed = checklist.zone_reclaimed(close, level, "buy", lookback=2)
    assert not reclaimed.any()


def test_zone_reclaimed_short_direction_mirrors_long():
    close = _price_series([102, 101, 99, 98])
    level = _price_series([100, 100, 100, 100])
    reclaimed = checklist.zone_reclaimed(close, level, "sell", lookback=2)
    assert reclaimed.iloc[2]  # crossed below


def test_pullback_holds_true_while_staying_above_after_reclaim():
    close = _price_series([98, 101, 100.5, 100.2])
    level = _price_series([100, 100, 100, 100])
    reclaimed = _bool_series([False, True, False, False])
    holds = checklist.pullback_holds(close, level, reclaimed, "buy")
    assert holds.iloc[1]
    assert holds.iloc[2]  # pulled back toward level but stayed above
    assert holds.iloc[3]


def test_pullback_holds_false_after_closing_back_below():
    close = _price_series([98, 101, 99.5, 100.2])
    level = _price_series([100, 100, 100, 100])
    reclaimed = _bool_series([False, True, False, False])
    holds = checklist.pullback_holds(close, level, reclaimed, "buy")
    assert holds.iloc[1]
    assert not holds.iloc[2]  # closed back below the level - pullback failed
    assert not holds.iloc[3]  # still tainted even though back above


def test_breakout_volume_true_when_volume_spikes_on_event():
    volume = pd.Series([10.0] * 20 + [30.0])
    event = pd.Series([False] * 20 + [True])
    result = checklist.breakout_volume(volume, event, window=20, multiplier=1.5)
    assert result.iloc[-1]


def test_breakout_volume_false_when_volume_normal():
    volume = pd.Series([10.0] * 20 + [11.0])
    event = pd.Series([False] * 20 + [True])
    result = checklist.breakout_volume(volume, event, window=20, multiplier=1.5)
    assert not result.iloc[-1]


def test_breakout_volume_false_when_event_false_even_with_spike():
    volume = pd.Series([10.0] * 20 + [30.0])
    event = pd.Series([False] * 21)
    result = checklist.breakout_volume(volume, event, window=20, multiplier=1.5)
    assert not result.iloc[-1]
