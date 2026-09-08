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
    RR=2.0,
    sl_buffer_pc=0.001,
)


class FakeBroker:
    """Minimal stand-in for AutoTrader's broker `get_candles` interface."""

    def __init__(self, data: pd.DataFrame):
        self.data = data

    def get_candles(
        self, instrument, granularity=None, count=None, end_time=None, **kwargs
    ):
        window = self.data.loc[:end_time] if end_time is not None else self.data
        return window.iloc[-count:] if count else window


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


def _make_strategy(data, **param_overrides):
    params = dict(DEFAULT_PARAMS, **param_overrides)
    return PremiumDiscountZones(params, "TEST", FakeBroker(data), None, {})


def test_long_signal_in_discount_zone():
    data = _build_long_setup()
    strat = _make_strategy(data)
    order = strat.generate_signal(data.index[-1])
    stop_loss, take_profit = float(order.stop_loss), float(order.take_profit)

    assert order.direction == 1
    assert stop_loss < data.Close.iloc[-1] < take_profit
    # Stop is just beyond the swing low that defines the range
    assert stop_loss == pytest.approx(strat.swing_low.iloc[-1] * 0.999)


def test_short_signal_in_premium_zone():
    data = _build_short_setup()
    strat = _make_strategy(data)
    order = strat.generate_signal(data.index[-1])
    stop_loss, take_profit = float(order.stop_loss), float(order.take_profit)

    assert order.direction == -1
    assert take_profit < data.Close.iloc[-1] < stop_loss
    assert stop_loss == pytest.approx(strat.swing_high.iloc[-1] * 1.001)


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
