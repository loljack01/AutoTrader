import shutil

import pandas as pd
import pytest

from data import cache


@pytest.fixture(autouse=True)
def isolate_cache_dir(tmp_path, monkeypatch):
    """Redirects the module's cache directory to a throwaway path so
    tests never read or write the real data/cache/ contents."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    yield
    shutil.rmtree(tmp_path, ignore_errors=True)


def _bar(t, o, h, l, c, v=100):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


def test_ingest_creates_and_persists_cache():
    bars = [
        _bar(1_700_000_000, 100, 101, 99, 100.5),
        _bar(1_700_000_060, 100.5, 102, 100, 101),
    ]
    df = cache.ingest("TVC:CAC40", "1m", bars)

    assert len(df) == 2
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert cache.cache_path("TVC:CAC40", "1m").exists()

    reloaded = cache.load("TVC:CAC40", "1m")
    assert len(reloaded) == 2


def test_ingest_merges_and_dedupes_on_overlap():
    cache.ingest("FCE1!", "1h", [_bar(1_700_000_000, 100, 101, 99, 100.5)])
    # Second fetch overlaps the first bar (refreshed close) and adds a new one.
    merged = cache.ingest(
        "FCE1!",
        "1h",
        [
            _bar(1_700_000_000, 100, 101, 99, 100.9),
            _bar(1_700_003_600, 100.9, 103, 100, 102),
        ],
    )

    assert len(merged) == 2
    # The newer fetch's value for the overlapping bar wins.
    assert merged.Close.iloc[0] == pytest.approx(100.9)


def test_ingest_accumulates_beyond_a_single_fetch():
    # Simulates the real constraint: each fetch only ever returns a fixed
    # window, but repeated fetches should still grow the cache over time.
    cache.ingest(
        "FCE1!",
        "1h",
        [_bar(1_700_000_000 + i * 3600, 100, 101, 99, 100) for i in range(5)],
    )
    grown = cache.ingest(
        "FCE1!",
        "1h",
        [_bar(1_700_000_000 + i * 3600, 100, 101, 99, 100) for i in range(3, 8)],
    )
    assert len(grown) == 8


def test_closed_bars_drops_the_still_forming_last_bar():
    bars = [
        _bar(1_700_000_000, 100, 101, 99, 100.5),
        _bar(1_700_003_600, 100.5, 102, 100, 101),
    ]
    df = cache.ingest("FCE1!", "1h", bars)

    # The second bar opened at 1_700_003_600 and needs a full hour to
    # close; "now" is only 10 minutes past its open.
    now = pd.Timestamp(1_700_003_600 + 600, unit="s", tz="UTC")
    closed = cache.closed_bars(df, "1h", now)

    assert len(closed) == 1
    assert closed.index[0] == df.index[0]


def test_closed_bars_keeps_a_bar_once_its_full_duration_has_elapsed():
    bars = [_bar(1_700_000_000, 100, 101, 99, 100.5)]
    df = cache.ingest("FCE1!", "1h", bars)
    now = pd.Timestamp(1_700_000_000 + 3600, unit="s", tz="UTC")
    assert len(cache.closed_bars(df, "1h", now)) == 1


def test_closed_bars_requires_timezone_aware_now():
    bars = [_bar(1_700_000_000, 100, 101, 99, 100.5)]
    df = cache.ingest("FCE1!", "1h", bars)
    with pytest.raises(ValueError):
        cache.closed_bars(df, "1h", pd.Timestamp(1_700_003_600, unit="s"))


def test_to_paris_converts_a_known_utc_summer_timestamp():
    # 2026-06-15 10:00 UTC is CEST (UTC+2) in Europe/Paris.
    bars = [
        _bar(pd.Timestamp("2026-06-15 10:00", tz="UTC").timestamp(), 100, 101, 99, 100)
    ]
    df = cache.ingest("FCE1!", "1h", bars)
    paris = cache.to_paris(df)
    assert paris.index[0] == pd.Timestamp("2026-06-15 12:00", tz="Europe/Paris")
