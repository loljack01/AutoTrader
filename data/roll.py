"""Monthly contract-roll detection for continuous futures such as FCE1!
and BRN1! (SPEC section 1, point 1).

A continuous front-month contract "rolls" to the next expiry on a fixed
schedule - the 3rd Friday of each month for FCE1!. Open interest migrates
to the new contract over the few sessions around that date, producing a
volume spike (>2x the recent daily average) that is a rollover artifact,
not a price signal. Bars in that window are flagged so callers can
exclude them from volume statistics and backtests, and block live
signals on the roll day itself (SPEC section 10), rather than silently
treating them as normal price action.
"""

from calendar import Calendar
from datetime import date, timedelta

import pandas as pd


def third_friday(year: int, month: int) -> date:
    fridays = [
        d
        for d in Calendar().itermonthdates(year, month)
        if d.month == month and d.weekday() == 4
    ]
    return fridays[2]


def roll_week(year: int, month: int) -> tuple[date, date]:
    """Returns (Monday, Friday) of the expiry week - the roll window."""
    friday = third_friday(year, month)
    monday = friday - timedelta(days=friday.weekday())
    return monday, friday


def is_in_roll_week(day: date) -> bool:
    monday, friday = roll_week(day.year, day.month)
    return monday <= day <= friday


def flag_roll_bars(
    daily: pd.DataFrame,
    volume_col: str = "Volume",
    ma_window: int = 20,
    threshold: float = 2.0,
) -> pd.Series:
    """Flags each row of a DAILY-interval frame as roll-contaminated:
    inside that month's roll week AND volume > `threshold` times the
    trailing `ma_window`-session average volume computed on non-roll
    sessions only ("hors roulement" per SPEC section 1.1), so an earlier
    roll spike never inflates the baseline a later one is compared to.
    `daily.index` must be datetime-like, one row per session."""
    in_roll_week = pd.Series(
        [is_in_roll_week(ts.date()) for ts in daily.index], index=daily.index
    )
    clean_volume = daily[volume_col].where(~in_roll_week)
    baseline = (
        clean_volume.rolling(ma_window, min_periods=max(5, ma_window // 2))
        .mean()
        .ffill()
        .shift(1)
    )
    return in_roll_week & (daily[volume_col] > threshold * baseline)
