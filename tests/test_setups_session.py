from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from setups import session

PARIS = ZoneInfo("Europe/Paris")


def _paris(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=PARIS)


def test_us_market_open_is_normally_15h30_paris():
    assert (
        session.us_market_open_paris(_paris(2026, 6, 15, 0, 0).date())
        .time()
        .isoformat(timespec="minutes")
        == "15:30"
    )


def test_us_market_open_shifts_to_14h30_during_the_march_offset_week():
    # SPEC 3.5: 9-27 mars 2026 is an offset week (US DST starts before EU's).
    assert (
        session.us_market_open_paris(_paris(2026, 3, 20, 0, 0).date())
        .time()
        .isoformat(timespec="minutes")
        == "14:30"
    )


def test_us_market_open_shifts_to_14h30_during_the_october_offset_week():
    # SPEC 3.5: 26-30 octobre 2026 (EU falls back before US's).
    assert (
        session.us_market_open_paris(_paris(2026, 10, 28, 0, 0).date())
        .time()
        .isoformat(timespec="minutes")
        == "14:30"
    )


def test_pre_open_window_is_flagged_unreliable_not_blocked():
    window = session.session_window(_paris(2026, 6, 15, 8, 30))
    assert window == "pre_open_unreliable"
    assert session.entry_allowed(window)  # flagged, not blocked


def test_cash_open_window_is_blocked():
    window = session.session_window(_paris(2026, 6, 15, 9, 5))
    assert window == "blocked_cash_open"
    assert not session.entry_allowed(window)


def test_normal_window_between_cash_open_and_us_open():
    window = session.session_window(_paris(2026, 6, 15, 12, 0))
    assert window == "normal"
    assert session.entry_allowed(window)


def test_us_open_window_is_blocked():
    window = session.session_window(_paris(2026, 6, 15, 15, 35))
    assert window == "blocked_us_open"
    assert not session.entry_allowed(window)


def test_normal_window_after_us_open_plus_15_minutes():
    window = session.session_window(_paris(2026, 6, 15, 15, 46))
    assert window == "normal"


def test_degraded_window_after_1730():
    window = session.session_window(_paris(2026, 6, 15, 18, 0))
    assert window == "degraded_after_close"
    assert session.entry_allowed(window)  # degraded, not blocked


def test_major_event_window_blocks_entries_within_15_minutes():
    event = _paris(2026, 6, 15, 14, 30)
    window = session.session_window(_paris(2026, 6, 15, 14, 40), major_events=[event])
    assert window == "blocked_major_event"
    assert not session.entry_allowed(window)


def test_outside_major_event_window_is_unaffected():
    event = _paris(2026, 6, 15, 14, 30)
    window = session.session_window(_paris(2026, 6, 15, 12, 0), major_events=[event])
    assert window == "normal"


def test_session_window_requires_timezone_aware_datetime():
    with pytest.raises(ValueError):
        session.session_window(datetime(2026, 6, 15, 12, 0))
