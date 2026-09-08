import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "strategies"))
from premium_discount import PremiumDiscountZones  # noqa: E402

DEFAULT_PARAMS = dict(
    granularity="1h",
    lookback_candles=300,
    swing_n=3,
    ema_period=20,
    use_trend_filter=False,
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
