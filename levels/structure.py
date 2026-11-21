"""Market structure: swings, BOS, CHoCH, trend (SPEC section 2.1).

    swing_high(i) = high[i] > high[i±1..n]   avec n = 2 par défaut
    swing_low(i)  = low[i]  < low[i±1..n]

A swing at i is a raw pivot, dated at i. It is only KNOWN at the close of
bar i+n - the n bars on its right are what confirm it - so anything
built on top of a swing (a zone, a BOS) is only knowable from i+n
onward, never earlier. Every function here keeps that distinction
explicit rather than silently forward-filling from i, which would be a
look-ahead bug.

Tie-break rule (SPEC): on a strict tie between two highs (or two lows),
the FIRST one in time is the swing; later ones at the same price are not
separate swings - they become an EQH/EQL liquidity pool instead (see
levels/liquidity.py).
"""

import numpy as np
import pandas as pd


def find_swings(data: pd.DataFrame, n: int = 2):
    """Returns (is_swing_high, is_swing_low): boolean Series aligned to
    `data.index`, True at bar i iff high[i] (resp. low[i]) is the unique
    extreme of the window [i-n, i+n] - or, on a tie, the first bar in
    that window to reach that extreme value."""
    high, low = data.High, data.Low
    n_bars = len(data)
    is_swing_high = pd.Series(False, index=data.index)
    is_swing_low = pd.Series(False, index=data.index)

    for i in range(n, n_bars - n):
        window_high = high.iloc[i - n : i + n + 1]
        if high.iloc[i] == window_high.max():
            first_at_max = window_high.idxmax()  # pandas: first occurrence wins
            if first_at_max == data.index[i]:
                is_swing_high.iloc[i] = True

        window_low = low.iloc[i - n : i + n + 1]
        if low.iloc[i] == window_low.min():
            first_at_min = window_low.idxmin()
            if first_at_min == data.index[i]:
                is_swing_low.iloc[i] = True

    return is_swing_high, is_swing_low


def confirmed_marks(is_swing: pd.Series, price: pd.Series, n: int) -> pd.Series:
    """NaN everywhere except exactly at each swing's confirmation bar
    (i+n), where it holds that swing's price - SPEC's "un swing en i
    n'est connu qu'à la clôture de la bougie i+n", made explicit rather
    than forward-filled."""
    out = pd.Series(np.nan, index=is_swing.index)
    positions = np.where(is_swing.to_numpy())[0]
    for pos in positions:
        confirm_pos = pos + n
        if confirm_pos < len(out):
            out.iloc[confirm_pos] = price.iloc[pos]
    return out


def confirmed_level(is_swing: pd.Series, price: pd.Series, n: int) -> pd.Series:
    """Like confirmed_marks(), but forward-filled: at any bar, the most
    recently confirmed swing price (NaN before the first one confirms).
    This is the series BOS/CHoCH and zone calculations compare price
    against."""
    return confirmed_marks(is_swing, price, n).ffill()


def bos_events(
    close: pd.Series, swing_high_level: pd.Series, swing_low_level: pd.Series
):
    """Bullish BOS: close breaks above the last confirmed swing high.
    Bearish BOS: close breaks below the last confirmed swing low.
    Both booleans, False (not NaN) where no confirmed level exists yet."""
    bullish = (close > swing_high_level).fillna(False)
    bearish = (close < swing_low_level).fillna(False)
    return bullish, bearish


def choch_events(bullish_bos: pd.Series, bearish_bos: pd.Series) -> pd.Series:
    """CHoCH = the first BOS contrary to the trend then in force. True
    only on the first bullish BOS after the most recent bearish BOS (and
    symmetrically) - a second BOS in the same direction is continuation,
    not a change of character."""
    choch = pd.Series(False, index=bullish_bos.index)
    state = None  # 'up' after a bullish BOS, 'down' after a bearish BOS
    for i in range(len(bullish_bos)):
        if bullish_bos.iloc[i]:
            if state != "up":
                choch.iloc[i] = True
            state = "up"
        elif bearish_bos.iloc[i]:
            if state != "down":
                choch.iloc[i] = True
            state = "down"
    return choch


def classify_trend(
    is_swing_high: pd.Series,
    high: pd.Series,
    is_swing_low: pd.Series,
    low: pd.Series,
    n: int,
) -> pd.Series:
    """'bullish' once the two most recently confirmed swings are BOTH a
    higher high and a higher low, 'bearish' once both are lower, else
    'range'. Holds 'range' until at least two swing highs and two swing
    lows have confirmed."""
    hi_marks = confirmed_marks(is_swing_high, high, n)
    lo_marks = confirmed_marks(is_swing_low, low, n)

    trend = pd.Series("range", index=high.index, dtype=object)
    prev_hi = cur_hi = prev_lo = cur_lo = None
    current = "range"
    for i in range(len(high)):
        if not np.isnan(hi_marks.iloc[i]):
            prev_hi, cur_hi = cur_hi, hi_marks.iloc[i]
        if not np.isnan(lo_marks.iloc[i]):
            prev_lo, cur_lo = cur_lo, lo_marks.iloc[i]
        if prev_hi is not None and prev_lo is not None:
            higher_high = cur_hi > prev_hi
            higher_low = cur_lo > prev_lo
            if higher_high and higher_low:
                current = "bullish"
            elif not higher_high and not higher_low:
                current = "bearish"
            else:
                current = "range"
        trend.iloc[i] = current
    return trend
