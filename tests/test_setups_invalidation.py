from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from setups import invalidation

PARIS = ZoneInfo("Europe/Paris")


def test_buy_invalidated_on_close_below_level():
    result = invalidation.check_invalidation(
        "buy",
        level=8035.0,
        close=8030.0,
        close_time=datetime(2026, 9, 24, 11, 0, tzinfo=PARIS),
        interval="15m",
    )
    assert result["invalidated"]
    assert not result["needs_cash_session_confirmation"]


def test_buy_not_invalidated_on_close_above_level():
    result = invalidation.check_invalidation(
        "buy",
        level=8035.0,
        close=8040.0,
        close_time=datetime(2026, 9, 24, 11, 0, tzinfo=PARIS),
        interval="15m",
    )
    assert not result["invalidated"]


def test_sell_invalidated_on_close_above_level():
    result = invalidation.check_invalidation(
        "sell",
        level=8146.0,
        close=8150.0,
        close_time=datetime(2026, 9, 24, 11, 0, tzinfo=PARIS),
        interval="15m",
    )
    assert result["invalidated"]


def test_invalidation_outside_cash_session_needs_confirmation():
    result = invalidation.check_invalidation(
        "buy",
        level=8035.0,
        close=8030.0,
        close_time=datetime(2026, 9, 24, 19, 0, tzinfo=PARIS),
        interval="15m",
    )
    assert result["invalidated"]
    assert result["needs_cash_session_confirmation"]


def test_invalidation_before_cash_open_needs_confirmation():
    result = invalidation.check_invalidation(
        "buy",
        level=8035.0,
        close=8030.0,
        close_time=datetime(2026, 9, 24, 8, 30, tzinfo=PARIS),
        interval="15m",
    )
    assert result["needs_cash_session_confirmation"]


def test_1_minute_interval_is_rejected():
    with pytest.raises(ValueError):
        invalidation.check_invalidation(
            "buy",
            level=8035.0,
            close=8030.0,
            close_time=datetime(2026, 9, 24, 11, 0, tzinfo=PARIS),
            interval="1m",
        )


def test_rejects_invalid_direction():
    with pytest.raises(ValueError):
        invalidation.check_invalidation(
            "sideways",
            level=8035.0,
            close=8030.0,
            close_time=datetime(2026, 9, 24, 11, 0, tzinfo=PARIS),
            interval="15m",
        )


def test_accepts_a_bare_time_for_close_time():
    from datetime import time

    result = invalidation.check_invalidation(
        "buy", level=8035.0, close=8030.0, close_time=time(19, 0), interval="15m"
    )
    assert result["needs_cash_session_confirmation"]
