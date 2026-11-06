import pandas as pd
import pytest

from levels import vwap


def _bars(rows, tz="UTC", freq="1h", start="2026-01-01 00:00"):
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz=tz)
    df = pd.DataFrame(rows, index=idx, columns=["High", "Low", "Close", "Volume"])
    return df


def test_session_vwap_matches_manual_calculation():
    # typical price per bar: (H+L+C)/3
    rows = [
        [102, 98, 100, 10],   # typical = 100
        [104, 100, 102, 20],  # typical = 102
    ]
    data = _bars(rows)
    result = vwap.session_vwap(data)

    expected_0 = 100.0
    expected_1 = (100 * 10 + 102 * 20) / (10 + 20)
    assert result.iloc[0] == pytest.approx(expected_0)
    assert result.iloc[1] == pytest.approx(expected_1)


def test_session_vwap_resets_at_paris_day_boundary():
    # 20:00 UTC on Jan 1 is still Paris day 1 (UTC+1 in January); 23:30 UTC
    # on Jan 1 is already 00:30 Paris on Jan 2 - a new session.
    idx = pd.to_datetime(["2026-01-01 20:00", "2026-01-01 23:30"]).tz_localize("UTC")
    data = pd.DataFrame(
        {"High": [101, 201], "Low": [99, 199], "Close": [100, 200], "Volume": [10, 10]},
        index=idx,
    )
    result = vwap.session_vwap(data)
    # second bar starts a new Paris session: its VWAP is its OWN typical
    # price (200), not blended with the much lower prior-day bar.
    assert result.iloc[1] == pytest.approx(200.0)


def test_session_vwap_rejects_naive_index():
    data = pd.DataFrame(
        {"High": [101], "Low": [99], "Close": [100], "Volume": [10]},
        index=pd.date_range("2026-01-01", periods=1, freq="1h"),
    )
    with pytest.raises(ValueError):
        vwap.session_vwap(data)
