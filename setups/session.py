"""Time-of-day filters, Europe/Paris (SPEC section 3.5).

The US market open is never hardcoded: it's computed each day as 9:30
America/New_York converted to Europe/Paris. `zoneinfo` resolves each
timezone's own DST transition independently, so the weeks where the EU
and US changeover dates fall apart (9-27 March and 26-30 October 2026,
per the SPEC) produce 14:30 automatically instead of the usual 15:30 -
no lookup table of exception dates needed.

| Plage | Règle |
|---|---|
| 08h00-09h00 | Pré-ouverture comptant : signaux "peu fiables" |
| 09h00-09h15 | Ouverture comptant : pas d'entrée |
| 09h15 - ouverture US | Séance normale |
| Ouverture US -> +15 min | Pas d'entrée |
| +15 min après ouverture US - 17h30 | Séance normale |
| après 17h30 | Signaux dégradés |
| +/-15 min autour d'une statistique majeure | Pas d'entrée |
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
NEW_YORK = ZoneInfo("America/New_York")

# Windows where SPEC 3.5 explicitly says "pas d'entrée" - a hard block.
_BLOCKED_WINDOWS = {"blocked_cash_open", "blocked_us_open", "blocked_major_event"}


def us_market_open_paris(day) -> datetime:
    ny_open = datetime.combine(day, time(9, 30), tzinfo=NEW_YORK)
    return ny_open.astimezone(PARIS)


def session_window(dt: datetime, major_events: list = None) -> str:
    """Classifies a Paris-aware `dt` into one of the SPEC 3.5 windows.
    `major_events`: optional list of Paris-aware datetimes for scheduled
    major economic releases - entries are blocked +/-15 minutes around
    each."""
    if dt.tzinfo is None:
        raise ValueError("dt must be timezone-aware (Europe/Paris)")

    if major_events:
        for event in major_events:
            if abs((dt - event).total_seconds()) <= 15 * 60:
                return "blocked_major_event"

    day = dt.date()
    us_open = us_market_open_paris(day)
    pre_open_start = datetime.combine(day, time(8, 0), tzinfo=PARIS)
    cash_open = datetime.combine(day, time(9, 0), tzinfo=PARIS)
    cash_open_end = datetime.combine(day, time(9, 15), tzinfo=PARIS)
    session_end = datetime.combine(day, time(17, 30), tzinfo=PARIS)

    if pre_open_start <= dt < cash_open:
        return "pre_open_unreliable"
    if cash_open <= dt < cash_open_end:
        return "blocked_cash_open"
    if us_open <= dt < us_open + timedelta(minutes=15):
        return "blocked_us_open"
    if dt >= session_end:
        return "degraded_after_close"
    if cash_open_end <= dt < session_end:
        return "normal"
    return "outside_hours"


def entry_allowed(window: str) -> bool:
    return window not in _BLOCKED_WINDOWS
