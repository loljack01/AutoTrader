"""Cumulative local OHLCV cache (SPEC section 1, points 3-5).

TradingView's ``get_ohlcv`` MCP tool returns at most 5000 bars per call
and has no pagination or end-date parameter, so a single call only ever
covers a fixed rolling window (~13 days for FCE1! at 1-minute, several
months at higher intervals). This module cannot call that tool itself -
only Claude, running inside a tool-use turn, can. The intended flow is:
Claude fetches bars via the MCP tool, then calls :func:`ingest` here to
merge them into that symbol+interval's persistent cache under
``data/cache/``, so repeated fetches accumulate history beyond any
single call's cap instead of only ever holding the latest window.

Bars are stored in UTC - the API's own native timezone - rather than
Europe/Paris, to keep the cache unambiguous across the DST transitions
SPEC section 3.5 warns about (Europe and US shift on different dates).
Converting to Paris time for display is handled by :func:`to_paris`,
kept separate from storage.
"""

import re
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent / "cache"

# Bar duration for each interval the MCP tool accepts. Used to tell a
# still-forming last bar (SPEC section 1.4: never validate a close on it)
# from one that has actually closed.
_INTERVAL_DURATIONS = {
    "1m": pd.Timedelta(minutes=1),
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1D": pd.Timedelta(days=1),
    "1W": pd.Timedelta(weeks=1),
}


def _safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", symbol).strip("_")


def cache_path(symbol: str, interval: str) -> Path:
    return CACHE_DIR / f"{_safe_name(symbol)}_{interval}.csv"


def _bars_to_frame(bars) -> pd.DataFrame:
    """Converts the MCP tool's raw bar list ([{t,o,h,l,c,v}, ...]) into an
    OHLCV DataFrame indexed by each bar's UTC open time."""
    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"], unit="s", utc=True)
    df = df.rename(
        columns={
            "t": "Date",
            "o": "Open",
            "h": "High",
            "l": "Low",
            "c": "Close",
            "v": "Volume",
        }
    )
    return df.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]].sort_index()


def load(symbol: str, interval: str) -> pd.DataFrame:
    """Loads this symbol+interval's cache, or an empty frame if none exists yet."""
    path = cache_path(symbol, interval)
    if not path.exists():
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    return pd.read_csv(path, index_col=0, parse_dates=True)


def ingest(symbol: str, interval: str, bars) -> pd.DataFrame:
    """Merges freshly-fetched bars into this symbol+interval's cache and
    persists the result. On overlap, the newly-fetched bar wins - this
    lets a still-forming bar's values get refreshed on the next fetch.
    Returns the full merged cache."""
    new = _bars_to_frame(bars)
    existing = load(symbol, interval)
    merged = pd.concat([existing, new])
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()

    path = cache_path(symbol, interval)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(path)
    return merged


def closed_bars(df: pd.DataFrame, interval: str, now: pd.Timestamp) -> pd.DataFrame:
    """Drops any bar not yet fully formed as of `now` (SPEC section 1.4:
    the last bar returned is always in progress and must never be used
    to validate a close). `df`'s index holds each bar's OPEN time, so a
    bar has closed once `now` reaches its open time plus its duration."""
    duration = _INTERVAL_DURATIONS[interval]
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return df[df.index + duration <= now]


def to_paris(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a copy of `df` with its (UTC) index converted to Europe/Paris,
    for display - SPEC section 1.2: API timestamps are UTC, user-facing
    output is Paris time."""
    out = df.copy()
    out.index = out.index.tz_convert("Europe/Paris")
    return out
