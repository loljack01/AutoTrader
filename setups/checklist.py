"""Multi-confirmation checklist (user's own discretionary framework,
2026-09-28): replace a single-condition trigger with a scored alignment
of independent signals, so a decision is never made on one condition or
a feeling.

LONG confirmations (SHORT is the exact mirror):
    1. structure_aligned : bullish CHoCH followed by a distinct, later
       confirming bullish BOS (not just the CHoCH bar itself)
    2. zone_reclaimed     : price closed back above a key level (VWAP,
       POC, an old resistance) after having been below it
    3. pullback_holds     : since reclaiming, price has not closed back
       below that level
    4. breakout_volume    : the bar that reclaimed the level traded at
       least `multiplier` times its trailing average volume
    5. correct_side       : current price is on the discount side of
       range equilibrium for a long (premium side for a short)

CVD / delta (buyer vs. seller aggressor volume) is DELIBERATELY EXCLUDED:
it requires trade-level tick data with aggressor side, which this
toolkit's OHLCV data source does not provide. Approximating it from OHLCV
alone (e.g. by candle color) would be a silent inaccuracy dressed up as a
real signal, so it is left out rather than faked. If a real CVD/delta
feed becomes available, add it as a 6th confirmation rather than
replacing one of these five.

A setup is valid only once at least `min_confirmations` hold (default 3
of 5) - never on a single condition.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

CONFIRMATION_NAMES = (
    "structure_aligned",
    "zone_reclaimed",
    "pullback_holds",
    "breakout_volume",
    "correct_side",
)


@dataclass
class ChecklistResult:
    direction: str
    confirmations: dict
    score: int
    valid: bool
    missing: list = field(default_factory=list)


def evaluate(direction: str, confirmations: dict, min_confirmations: int = 3) -> ChecklistResult:
    """Pure scoring gate: `confirmations` must supply a bool for every
    name in CONFIRMATION_NAMES - no partial or inferred confirmations."""
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")

    given = set(confirmations)
    expected = set(CONFIRMATION_NAMES)
    if given != expected:
        missing_keys = expected - given
        unknown_keys = given - expected
        parts = []
        if missing_keys:
            parts.append(f"missing {sorted(missing_keys)}")
        if unknown_keys:
            parts.append(f"unknown {sorted(unknown_keys)}")
        raise ValueError(f"confirmations dict mismatch: {', '.join(parts)}")

    score = sum(1 for v in confirmations.values() if v)
    missing = [name for name in CONFIRMATION_NAMES if not confirmations[name]]
    return ChecklistResult(
        direction=direction,
        confirmations=dict(confirmations),
        score=score,
        valid=score >= min_confirmations,
        missing=missing,
    )


def structure_aligned(
    choch_bullish: pd.Series,
    bos_bullish: pd.Series,
    choch_bearish: pd.Series,
    bos_bearish: pd.Series,
    lookback: int,
):
    """Returns (bullish, bearish) boolean Series. True at bar i iff a
    CHoCH in that direction occurred within the last `lookback` bars AND
    a DISTINCT confirming BOS in the same direction fired strictly after
    that CHoCH, at or before bar i (a second push, not the CHoCH itself)."""
    n = len(choch_bullish)
    bullish = pd.Series(False, index=choch_bullish.index)
    bearish = pd.Series(False, index=choch_bullish.index)
    bos_bull_np = bos_bullish.to_numpy()
    bos_bear_np = bos_bearish.to_numpy()

    last_choch_bull = None
    last_choch_bear = None
    for i in range(n):
        if choch_bullish.iloc[i]:
            last_choch_bull = i
        if choch_bearish.iloc[i]:
            last_choch_bear = i
        if last_choch_bull is not None and i - last_choch_bull <= lookback:
            if bos_bull_np[last_choch_bull + 1 : i + 1].any():
                bullish.iloc[i] = True
        if last_choch_bear is not None and i - last_choch_bear <= lookback:
            if bos_bear_np[last_choch_bear + 1 : i + 1].any():
                bearish.iloc[i] = True
    return bullish, bearish


def zone_reclaimed(close: pd.Series, level: pd.Series, direction: str, lookback: int) -> pd.Series:
    """True at bar i iff close[i] is on `direction`'s side of level[i]
    AND, within the last `lookback` bars, close was on the OTHER side -
    a genuine reclaim, not just "currently above" in a steady uptrend."""
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")
    above = close > level
    on_side = above if direction == "buy" else ~above
    was_other_side = (~on_side).rolling(lookback + 1, min_periods=1).max().astype(bool)
    # was_other_side at i also covers bar i itself; a bar can't reclaim on
    # the same bar it's already on the wrong side of, so require it held
    # among the PRIOR `lookback` bars specifically.
    was_other_side_prior = was_other_side.shift(1).fillna(False).astype(bool)
    return on_side & was_other_side_prior


def pullback_holds(close: pd.Series, level: pd.Series, reclaimed: pd.Series, direction: str) -> pd.Series:
    """True at bar i iff a reclaim (per `reclaimed`) happened at or
    before i, and close has not, since the most recent reclaim, closed
    back on the wrong side of `level`."""
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")
    above = close > level
    on_side = above if direction == "buy" else ~above

    n = len(close)
    out = pd.Series(False, index=close.index)
    reclaimed_np = reclaimed.to_numpy()
    on_side_np = on_side.to_numpy()
    last_reclaim = None
    for i in range(n):
        if reclaimed_np[i]:
            last_reclaim = i
        if last_reclaim is not None:
            out.iloc[i] = bool(on_side_np[last_reclaim : i + 1].all())
    return out


def breakout_volume(volume: pd.Series, event: pd.Series, window: int = 20, multiplier: float = 1.5) -> pd.Series:
    """True at bar i iff `event[i]` (e.g. a reclaim) is True AND
    volume[i] >= multiplier * the trailing `window`-bar average volume
    (excluding bar i itself)."""
    avg_volume = volume.shift(1).rolling(window, min_periods=1).mean()
    return event & (volume >= multiplier * avg_volume)
