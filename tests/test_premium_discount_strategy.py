import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "strategies"))
from premium_discount import (  # noqa: E402
    PremiumDiscountZones,
    compute_market_structure,
    compute_liquidity_sweeps,
    resample_ohlc,
)

DEFAULT_PARAMS = dict(
    granularity="1h",
    lookback_candles=300,
    swing_n=3,
    ema_period=20,
    use_trend_filter=False,
    use_structure_filter=False,
    use_liquidity_sweep=False,
    use_htf_filter=False,
    htf_resample="4h",
    use_ote=False,
    ote_low=0.618,
    ote_high=0.79,
    one_trade_per_range=True,
    allow_pyramiding=False,
    RR=2.0,
    sl_buffer_mode="pct",
    sl_buffer_pc=0.001,
    atr_period=14,
    sl_atr_mult=0.25,
)


class FakeBroker:
    """Minimal stand-in for AutoTrader's broker `get_candles`/`get_positions`
    interface."""

    def __init__(self, data: pd.DataFrame, open_position: bool = False):
        self.data = data
        self.open_position = open_position

    def get_candles(
        self, instrument, granularity=None, count=None, end_time=None, **kwargs
    ):
        window = self.data.loc[:end_time] if end_time is not None else self.data
        return window.iloc[-count:] if count else window

    def get_positions(self, instrument=None, **kwargs):
        return {instrument: object()} if self.open_position else {}


def _set_candle(data, i, open_, close):
    cols = data.columns
    data.iloc[i, cols.get_loc("Open")] = open_
    data.iloc[i, cols.get_loc("Close")] = close
    data.iloc[i, cols.get_loc("High")] = max(open_, close) + 0.1
    data.iloc[i, cols.get_loc("Low")] = min(open_, close) - 0.1


def _build_long_setup():
    """Down-up-pullback price path ending on a bullish-engulfing reversal
    inside the discount half of the resulting swing range."""
    down = np.linspace(100, 90, 15)
    up = np.linspace(90, 150, 40)
    pull = np.linspace(150, 108, 25)
    close = np.concatenate([down, up, pull])
    open_ = np.concatenate([[100], close[:-1]])
    high = np.maximum(open_, close) + 0.3
    low = np.minimum(open_, close) - 0.3
    idx = pd.date_range("2024-01-01", periods=len(close), freq="h")
    data = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close}, index=idx
    )
    _set_candle(data, -2, 109.0, 108.8)
    _set_candle(data, -1, 108.5, 113.0)
    return data


def _build_short_setup():
    """Up-down-rally price path ending on a bearish-engulfing reversal
    inside the premium half of the resulting swing range."""
    up = np.linspace(100, 110, 15)
    down = np.linspace(110, 50, 40)
    rally = np.linspace(50, 92, 25)
    close = np.concatenate([up, down, rally])
    open_ = np.concatenate([[100], close[:-1]])
    high = np.maximum(open_, close) + 0.3
    low = np.minimum(open_, close) - 0.3
    idx = pd.date_range("2024-01-01", periods=len(close), freq="h")
    data = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close}, index=idx
    )
    _set_candle(data, -2, 90.0, 90.2)
    _set_candle(data, -1, 90.5, 86.0)
    return data


def _make_strategy(data, broker=None, **param_overrides):
    params = dict(DEFAULT_PARAMS, **param_overrides)
    broker = broker if broker is not None else FakeBroker(data)
    return PremiumDiscountZones(params, "TEST", broker, None, {})


def test_long_signal_in_discount_zone():
    data = _build_long_setup()
    strat = _make_strategy(data)
    order = strat.generate_signal(data.index[-1])
    stop_loss, take_profit = float(order.stop_loss), float(order.take_profit)

    assert order.direction == 1
    assert stop_loss < data.Close.iloc[-1] < take_profit
    # Stop is just beyond the swing low that defines the range
    expected_stop = strat.swing_low.iloc[-1] - DEFAULT_PARAMS["sl_buffer_pc"] * float(
        data.Close.iloc[-1]
    )
    assert stop_loss == pytest.approx(expected_stop)


def test_short_signal_in_premium_zone():
    data = _build_short_setup()
    strat = _make_strategy(data)
    order = strat.generate_signal(data.index[-1])
    stop_loss, take_profit = float(order.stop_loss), float(order.take_profit)

    assert order.direction == -1
    assert take_profit < data.Close.iloc[-1] < stop_loss
    expected_stop = strat.swing_high.iloc[-1] + DEFAULT_PARAMS["sl_buffer_pc"] * float(
        data.Close.iloc[-1]
    )
    assert stop_loss == pytest.approx(expected_stop)


def test_trend_filter_blocks_counter_trend_signal():
    # The long setup pulls back from the swing high, so a short-period EMA
    # sits above price - an uptrend-only filter should block the long.
    data = _build_long_setup()
    strat = _make_strategy(data, use_trend_filter=True)
    order = strat.generate_signal(data.index[-1])

    assert order.direction is None


def test_no_signal_without_reversal_trigger():
    # Same range/zone, but the final candle is not an engulfing reversal.
    data = _build_long_setup()
    _set_candle(data, -1, 108.7, 108.9)
    strat = _make_strategy(data)
    order = strat.generate_signal(data.index[-1])

    assert order.direction is None


def test_insufficient_data_returns_blank_order():
    data = _build_long_setup().iloc[:5]
    strat = _make_strategy(data, ema_period=20, swing_n=3)
    order = strat.generate_signal(data.index[-1])

    assert order.direction is None


def test_zones_are_ordered_and_bracket_equilibrium():
    data = _build_long_setup()
    strat = _make_strategy(data)
    strat.generate_features(data)

    discount_lower, discount_upper = (
        strat.discount_zone[0].iloc[-1],
        strat.discount_zone[1].iloc[-1],
    )
    premium_lower, premium_upper = (
        strat.premium_zone[0].iloc[-1],
        strat.premium_zone[1].iloc[-1],
    )
    equilibrium = strat.equilibrium.iloc[-1]

    assert discount_lower < discount_upper
    assert discount_upper == pytest.approx(equilibrium)
    assert premium_lower == pytest.approx(equilibrium)
    assert premium_lower < premium_upper
    assert discount_lower == pytest.approx(strat.swing_low.iloc[-1])
    assert premium_upper == pytest.approx(strat.swing_high.iloc[-1])


def test_ote_zone_sits_near_the_correct_swing():
    # Discount OTE (retracement of the H->L leg) must sit just above L, in
    # the lower half of the range; premium OTE (retracement of the L->H
    # leg) must sit just below H, in the upper half. Getting this backwards
    # would place "buy" entries near the top of the range and vice versa.
    data = _build_long_setup()
    strat = _make_strategy(data, use_ote=True)
    strat.generate_features(data)

    swing_low = strat.swing_low.iloc[-1]
    swing_high = strat.swing_high.iloc[-1]
    equilibrium = strat.equilibrium.iloc[-1]
    discount_lower, discount_upper = (
        strat.discount_zone[0].iloc[-1],
        strat.discount_zone[1].iloc[-1],
    )
    premium_lower, premium_upper = (
        strat.premium_zone[0].iloc[-1],
        strat.premium_zone[1].iloc[-1],
    )

    assert swing_low < discount_lower < discount_upper < equilibrium
    assert equilibrium < premium_lower < premium_upper < swing_high


def test_one_trade_per_range_blocks_reentry():
    data = _build_long_setup()
    strat = _make_strategy(data)

    first = strat.generate_signal(data.index[-1])
    assert first.direction == 1

    # Same data/range/trigger - a second call must not re-enter.
    second = strat.generate_signal(data.index[-1])
    assert second.direction is None


def test_one_trade_per_range_can_be_disabled():
    data = _build_long_setup()
    strat = _make_strategy(data, one_trade_per_range=False)

    first = strat.generate_signal(data.index[-1])
    second = strat.generate_signal(data.index[-1])

    assert first.direction == 1
    assert second.direction == 1


def test_atr_stop_buffer_widens_with_volatility():
    data = _build_long_setup()
    calm = _make_strategy(data, sl_buffer_mode="atr", sl_atr_mult=0.25)
    order_calm = calm.generate_signal(data.index[-1])

    volatile_data = data.copy()
    volatile_data["High"] = volatile_data["High"] + 5
    volatile_data["Low"] = volatile_data["Low"] - 5
    volatile = _make_strategy(volatile_data, sl_buffer_mode="atr", sl_atr_mult=0.25)
    order_volatile = volatile.generate_signal(volatile_data.index[-1])

    calm_risk = float(data.Close.iloc[-1]) - float(order_calm.stop_loss)
    volatile_risk = float(volatile_data.Close.iloc[-1]) - float(
        order_volatile.stop_loss
    )
    assert volatile_risk > calm_risk


def test_find_swings_does_not_repaint_past_values():
    # Regression test for look-ahead bias: appending future bars must never
    # change swing values already reported for earlier bars.
    from autotrader import indicators

    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, 80))
    high = close + rng.random(80)
    low = close - rng.random(80)
    open_ = close + rng.normal(0, 0.1, 80)
    idx = pd.date_range("2024-01-01", periods=80, freq="h")
    data = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close}, index=idx
    )

    full = indicators.find_swings(data, n=3)
    partial = indicators.find_swings(data.iloc[:60], n=3)

    pd.testing.assert_frame_equal(full.iloc[:60], partial)


def _swings_for(data, n=3):
    from autotrader import indicators

    swings = indicators.find_swings(data, n=n)
    swing_high = swings.Highs.replace(0, np.nan).ffill()
    swing_low = swings.Lows.replace(0, np.nan).ffill()
    return swing_high, swing_low


def test_market_structure_labels_continuation_as_bos():
    # A clean up-down-up-down zigzag making a higher low then a higher
    # high: both later breaks continue the (implicitly bullish, since it's
    # the first-ever break) structure, so both should be BOS, not CHoCH.
    down1 = np.linspace(100, 90, 15)
    up1 = np.linspace(90, 110, 15)
    down2 = np.linspace(110, 95, 15)  # higher low than 90
    up2 = np.linspace(95, 120, 15)  # higher high than 110
    close = np.concatenate([down1, up1, down2, up2])
    open_ = np.concatenate([[100], close[:-1]])
    high = np.maximum(open_, close) + 0.3
    low = np.minimum(open_, close) - 0.3
    idx = pd.date_range("2024-01-01", periods=len(close), freq="h")
    data = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close}, index=idx
    )

    swing_high, swing_low = _swings_for(data)
    trend, event = compute_market_structure(data, swing_high, swing_low)

    fired = event[event.notna()]
    assert len(fired) > 0
    assert set(fired.unique()) == {"BOS_bullish"}
    assert trend.iloc[-1] == "bullish"


def test_market_structure_labels_reversal_as_choch():
    # Downtrend (LH then LL confirms bearish BOS), then a rally that breaks
    # back above the last LH - the first break against the established
    # trend must be labelled a CHoCH, not another BOS.
    up0 = np.linspace(100, 110, 12)
    down1 = np.linspace(110, 90, 12)
    up1 = np.linspace(90, 105, 12)  # lower high (105 < 110)
    down2 = np.linspace(105, 80, 12)  # lower low (80 < 90) -> BOS_bearish
    rally = np.linspace(80, 108, 12)  # breaks back above 105 -> CHoCH_bullish
    close = np.concatenate([up0, down1, up1, down2, rally])
    open_ = np.concatenate([[100], close[:-1]])
    high = np.maximum(open_, close) + 0.3
    low = np.minimum(open_, close) - 0.3
    idx = pd.date_range("2024-01-01", periods=len(close), freq="h")
    data = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close}, index=idx
    )

    swing_high, swing_low = _swings_for(data)
    trend, event = compute_market_structure(data, swing_high, swing_low)

    fired = event[event.notna()]
    assert "BOS_bearish" in fired.values
    assert "CHoCH_bullish" in fired.values
    # The CHoCH must come after at least one bearish BOS, and structure
    # must end bullish, not flip back and forth.
    choch_pos = fired[fired == "CHoCH_bullish"].index[0]
    bos_positions = fired[fired == "BOS_bearish"].index
    assert (bos_positions < choch_pos).all()
    assert trend.iloc[-1] == "bullish"


def test_market_structure_does_not_repaint():
    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.normal(0, 1, 100))
    high = close + rng.random(100)
    low = close - rng.random(100)
    open_ = close + rng.normal(0, 0.1, 100)
    idx = pd.date_range("2024-01-01", periods=100, freq="h")
    data = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close}, index=idx
    )

    swing_high, swing_low = _swings_for(data)
    trend_full, event_full = compute_market_structure(data, swing_high, swing_low)

    partial_data = data.iloc[:70]
    partial_high, partial_low = _swings_for(partial_data)
    trend_partial, event_partial = compute_market_structure(
        partial_data, partial_high, partial_low
    )

    pd.testing.assert_series_equal(trend_full.iloc[:70], trend_partial)
    pd.testing.assert_series_equal(event_full.iloc[:70], event_partial)


def test_structure_filter_blocks_signal_with_no_established_structure():
    # The long setup's pullback never breaks back below the swing low that
    # defines its range, so no BOS/CHoCH has fired yet at the entry bar -
    # with the structure filter on, that must block the trade.
    data = _build_long_setup()
    strat = _make_strategy(data, use_structure_filter=True)

    order = strat.generate_signal(data.index[-1])
    assert order.direction is None


def test_structure_filter_allows_signal_when_structure_agrees(monkeypatch):
    # Force an already-bullish structure state, to isolate the filter's
    # wiring in generate_signal from having to hand-construct a full
    # second leg of price history just to get a real CHoCH/BOS to fire.
    import premium_discount

    data = _build_long_setup()
    strat = _make_strategy(data, use_structure_filter=True)

    def fake_market_structure(data, swing_high, swing_low):
        trend = pd.Series(["bullish"] * len(data), index=data.index)
        event = pd.Series([None] * len(data), index=data.index)
        return trend, event

    monkeypatch.setattr(
        premium_discount, "compute_market_structure", fake_market_structure
    )

    order = strat.generate_signal(data.index[-1])
    assert order.direction == 1


def test_open_position_blocks_new_entry():
    # Even with one_trade_per_range disabled, a second entry must not be
    # taken while a position is already open on the instrument - this is
    # what protects a restarted strategy (whose _last_entry_range memory
    # was just wiped) from pyramiding into an existing position.
    data = _build_long_setup()
    broker = FakeBroker(data, open_position=True)
    strat = _make_strategy(data, broker=broker, one_trade_per_range=False)

    order = strat.generate_signal(data.index[-1])
    assert order.direction is None


def test_allow_pyramiding_overrides_open_position_guard():
    data = _build_long_setup()
    broker = FakeBroker(data, open_position=True)
    strat = _make_strategy(data, broker=broker, allow_pyramiding=True)

    order = strat.generate_signal(data.index[-1])
    assert order.direction == 1


def test_atr_mode_with_insufficient_history_returns_blank_order():
    # atr_period exceeds ema_period/swing warmup here; before min_bars
    # accounted for atr_period this could slip through generate_signal's
    # data-length gate and later compute a NaN ATR, producing an order
    # with a NaN stop loss instead of failing safe.
    data = _build_long_setup().iloc[:12]
    strat = _make_strategy(
        data,
        ema_period=5,
        swing_n=3,
        sl_buffer_mode="atr",
        atr_period=14,
    )

    order = strat.generate_signal(data.index[-1])
    assert order.direction is None


def _build_sweep_setup():
    """Same down-up-pullback shape as _build_long_setup, but the final
    candle is a liquidity sweep of the swing low (wick below it, close
    back above) rather than a proper engulfing pattern."""
    down = np.linspace(100, 90, 15)
    up = np.linspace(90, 150, 40)
    pull = np.linspace(150, 108, 25)
    close = np.concatenate([down, up, pull])
    open_ = np.concatenate([[100], close[:-1]])
    high = np.maximum(open_, close) + 0.3
    low = np.minimum(open_, close) - 0.3
    idx = pd.date_range("2024-01-01", periods=len(close), freq="h")
    data = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close}, index=idx
    )

    from autotrader import indicators

    swing_low_before = (
        indicators.find_swings(data, n=3).Lows.replace(0, np.nan).ffill().iloc[-2]
    )
    cols = data.columns
    data.iloc[-1, cols.get_loc("Open")] = swing_low_before + 0.3
    data.iloc[-1, cols.get_loc("Close")] = swing_low_before + 0.5
    data.iloc[-1, cols.get_loc("Low")] = swing_low_before - 1.0
    data.iloc[-1, cols.get_loc("High")] = swing_low_before + 0.6
    return data


def test_liquidity_sweep_detected_causally():
    data = _build_sweep_setup()
    swing_high, swing_low = _swings_for(data)
    bullish_sweep, bearish_sweep = compute_liquidity_sweeps(data, swing_high, swing_low)

    assert bool(bullish_sweep.iloc[-1]) is True
    assert bool(bearish_sweep.iloc[-1]) is False

    # Causality: appending future bars must not change past sweep values.
    swing_high_partial, swing_low_partial = _swings_for(data.iloc[:-5])
    bullish_partial, _ = compute_liquidity_sweeps(
        data.iloc[:-5], swing_high_partial, swing_low_partial
    )
    pd.testing.assert_series_equal(
        bullish_sweep.iloc[:-5], bullish_partial, check_names=False
    )


def test_sweep_setup_is_not_a_valid_engulfing():
    # Sanity check that this fixture actually isolates the sweep trigger:
    # the crafted candle must NOT also satisfy bullish_engulfing, or the
    # next test wouldn't prove the sweep path did the work.
    from autotrader import indicators

    data = _build_sweep_setup()
    assert bool(indicators.bullish_engulfing(data)[-1]) is False


def test_liquidity_sweep_trigger_is_opt_in():
    data = _build_sweep_setup()

    strat_off = _make_strategy(data, use_liquidity_sweep=False)
    assert strat_off.generate_signal(data.index[-1]).direction is None

    strat_on = _make_strategy(data, use_liquidity_sweep=True)
    order_on = strat_on.generate_signal(data.index[-1])
    assert order_on.direction == 1


def test_resample_ohlc_aggregates_correctly_and_drops_incomplete_bar():
    # 170 one-minute bars from 00:00 run through 02:49 (each bar is
    # indexed by its OPEN time, so this covers price action up to
    # 02:50) - two complete hours plus a partial third hour, which must
    # be dropped since it's still 10 minutes short of 03:00.
    idx = pd.date_range("2024-01-01 00:00", periods=170, freq="1min")
    rng = np.random.default_rng(1)
    close = 100 + np.cumsum(rng.normal(0, 0.1, 170))
    data = pd.DataFrame(
        {"Open": close, "High": close + 0.2, "Low": close - 0.2, "Close": close},
        index=idx,
    )

    resampled = resample_ohlc(data, "1h")

    assert list(resampled.index) == [
        pd.Timestamp("2024-01-01 00:00"),
        pd.Timestamp("2024-01-01 01:00"),
    ]
    hour0 = data.loc["2024-01-01 00:00":"2024-01-01 00:59"]
    assert resampled["Open"].iloc[0] == pytest.approx(hour0["Open"].iloc[0])
    assert resampled["High"].iloc[0] == pytest.approx(hour0["High"].max())
    assert resampled["Low"].iloc[0] == pytest.approx(hour0["Low"].min())
    assert resampled["Close"].iloc[0] == pytest.approx(hour0["Close"].iloc[-1])


def test_resample_ohlc_keeps_bar_that_just_completed():
    # 120 minutes exactly spans two complete hours (00:00-00:59,
    # 01:00-01:59), with the last data point being the final minute of
    # the second hour - that bar is complete and must be kept.
    idx = pd.date_range("2024-01-01 00:00", periods=120, freq="1min")
    close = np.linspace(100, 110, 120)
    data = pd.DataFrame(
        {"Open": close, "High": close + 0.2, "Low": close - 0.2, "Close": close},
        index=idx,
    )
    resampled = resample_ohlc(data, "1h")
    assert list(resampled.index) == [
        pd.Timestamp("2024-01-01 00:00"),
        pd.Timestamp("2024-01-01 01:00"),
    ]


def test_resample_ohlc_rejects_a_rule_not_coarser_than_the_data():
    # Resampling '1h' data to '1h' (or finer) would silently produce a
    # no-op "higher timeframe" identical to the base data - this must be
    # a loud error, not a silently useless filter.
    idx = pd.date_range("2024-01-01", periods=10, freq="h")
    close = np.linspace(100, 110, 10)
    data = pd.DataFrame(
        {"Open": close, "High": close + 0.2, "Low": close - 0.2, "Close": close},
        index=idx,
    )
    with pytest.raises(ValueError):
        resample_ohlc(data, "1h")
    with pytest.raises(ValueError):
        resample_ohlc(data, "30min")


def test_resample_ohlc_base_period_robust_to_session_gap():
    # An overnight session gap between the first two bars must not be
    # mistaken for the instrument's actual bar spacing (which would
    # corrupt the "is the last bar complete" check for every later call).
    day1 = pd.date_range(
        "2024-01-01 17:00", periods=2, freq="1min"
    )  # last 2 min of day 1
    day2 = pd.date_range(
        "2024-01-02 08:00", periods=170, freq="1min"
    )  # day 2, incomplete last hour
    idx = day1.append(day2)
    close = np.linspace(100, 110, len(idx))
    data = pd.DataFrame(
        {"Open": close, "High": close + 0.2, "Low": close - 0.2, "Close": close},
        index=idx,
    )

    resampled = resample_ohlc(data, "1h")

    # Day 2 spans 08:00 to 10:49 (170 minutes) - two complete hours
    # (08:00, 09:00) plus a partial third (10:00-10:49), which must be
    # dropped despite the ~15-hour overnight gap earlier in the series.
    assert resampled.index[-1] == pd.Timestamp("2024-01-02 09:00")


def _build_htf_veto_setup():
    """A long, persistent downtrend (so a 4h resample confirms bearish
    structure) with a small local bullish-engulfing reversal in the final
    two hourly bars - a setup that only a higher-timeframe check would
    catch as still counter-trend."""
    rng = np.random.default_rng(3)

    def leg(a, b, n, noise=0.5):
        return np.linspace(a, b, n) + rng.normal(0, noise, n)

    segments = [
        leg(300, 250, 60),
        leg(250, 255, 5),
        leg(255, 200, 60),
        leg(200, 205, 5),
        leg(205, 150, 60),
    ]
    close = np.concatenate(segments)
    open_ = np.concatenate([[300], close[:-1]])
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    idx = pd.date_range("2024-01-01", periods=len(close), freq="h")
    data = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close}, index=idx
    )
    _set_candle(data, -2, 151.0, 150.8)
    _set_candle(data, -1, 150.5, 155.0)
    return data


def test_htf_filter_vetoes_local_reversal_against_larger_trend():
    data = _build_htf_veto_setup()

    strat_off = _make_strategy(data, use_htf_filter=False)
    assert strat_off.generate_signal(data.index[-1]).direction == 1

    strat_on = _make_strategy(data, use_htf_filter=True, htf_resample="4h")
    order_on = strat_on.generate_signal(data.index[-1])
    assert order_on.direction is None
    assert strat_on.htf_trend.iloc[-1] == "bearish"


def test_htf_filter_fails_closed_without_enough_higher_timeframe_history():
    data = _build_long_setup()
    strat = _make_strategy(data, use_htf_filter=True, htf_resample="4h", swing_n=3)

    order = strat.generate_signal(data.index[-1])
    assert order.direction is None
