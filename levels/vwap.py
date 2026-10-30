"""Session VWAP (added for the user's confirmation-checklist framework,
not part of the original PDF spec). Resets at each new Europe/Paris
calendar day, matching how VWAP is used in practice: a same-day
reference level, not a running-forever average.
"""

import pandas as pd


def session_vwap(data: pd.DataFrame) -> pd.Series:
    """`data` must have a tz-aware DatetimeIndex and High/Low/Close/Volume
    columns. Returns the volume-weighted average price, resetting at each
    new Europe/Paris calendar day."""
    if data.index.tz is None:
        raise ValueError("data.index must be timezone-aware")

    typical_price = (data.High + data.Low + data.Close) / 3
    paris_date = data.index.tz_convert("Europe/Paris").normalize()

    pv = typical_price * data.Volume
    cum_pv = pv.groupby(paris_date).cumsum()
    cum_vol = data.Volume.groupby(paris_date).cumsum()
    return cum_pv / cum_vol
