from datetime import date

import pandas as pd

from data import roll

# Real FCE1! roll-week volume spikes from the SPEC (section 1, point 1),
# ~43 000 contracts/day is the documented "normal" average.
DOCUMENTED_SPIKES = {
    date(2026, 4, 14): 151_008,
    date(2026, 5, 12): 107_996,
    date(2026, 6, 15): 114_415,
    date(2026, 7, 14): 106_343,
    date(2026, 8, 18): 114_888,
    date(2026, 9, 14): 131_539,
    date(2026, 9, 15): 115_564,
}
BASELINE_VOLUME = 43_000


def test_third_friday_matches_documented_expiries():
    assert roll.third_friday(2026, 4) == date(2026, 4, 17)
    assert roll.third_friday(2026, 5) == date(2026, 5, 15)
    assert roll.third_friday(2026, 6) == date(2026, 6, 19)
    assert roll.third_friday(2026, 7) == date(2026, 7, 17)
    assert roll.third_friday(2026, 8) == date(2026, 8, 21)
    assert roll.third_friday(2026, 9) == date(2026, 9, 18)


def test_roll_week_spans_monday_to_expiry_friday():
    assert roll.roll_week(2026, 4) == (date(2026, 4, 13), date(2026, 4, 17))
    assert roll.roll_week(2026, 9) == (date(2026, 9, 14), date(2026, 9, 18))


def test_is_in_roll_week_matches_every_documented_spike_date():
    for day in DOCUMENTED_SPIKES:
        assert roll.is_in_roll_week(day), f"{day} should fall in its month's roll week"


def test_is_in_roll_week_false_for_an_ordinary_mid_month_day():
    assert roll.is_in_roll_week(date(2026, 3, 10)) is False


def test_flag_roll_bars_matches_documented_spikes_and_nothing_else():
    idx = pd.bdate_range("2026-01-01", "2026-09-20", tz="UTC")
    volume = pd.Series(BASELINE_VOLUME, index=idx, dtype=float)
    for day, vol in DOCUMENTED_SPIKES.items():
        volume.loc[pd.Timestamp(day, tz="UTC")] = vol
    # Decoy: a high-volume day outside any roll week must NOT be flagged -
    # the rule is window AND volume, not volume alone.
    volume.loc[pd.Timestamp("2026-03-10", tz="UTC")] = 90_000

    daily = pd.DataFrame({"Volume": volume})
    flagged = roll.flag_roll_bars(daily)

    flagged_dates = {ts.date() for ts in flagged.index[flagged]}
    assert flagged_dates == set(DOCUMENTED_SPIKES)
