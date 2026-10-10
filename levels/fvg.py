"""Fair Value Gaps / imbalances (SPEC section 2.3).

    FVG baissier : high[i] < low[i-2]  ->  zone [high[i], low[i-2]]
    FVG haussier : low[i]  > high[i-2] ->  zone [high[i-2], low[i]]

A FVG is only knowable at the close of bar i (it needs bars i-2, i-1 and
i). A FVG crossed by a later close is "inverted": it changes role,
support becoming resistance or vice versa.
"""

import pandas as pd


def find_fvgs(data: pd.DataFrame):
    """Returns a list of FVGs in chronological order, each a dict with
    type ('bullish'/'bearish'), top, bottom, created_at, and inverted_at
    (filled in by mark_inversions(), None until then)."""
    high, low = data.High, data.Low
    fvgs = []
    for i in range(2, len(data)):
        ts = data.index[i]
        if high.iloc[i] < low.iloc[i - 2]:
            fvgs.append(
                {
                    "type": "bearish",
                    "top": low.iloc[i - 2],
                    "bottom": high.iloc[i],
                    "created_at": ts,
                    "inverted_at": None,
                }
            )
        elif low.iloc[i] > high.iloc[i - 2]:
            fvgs.append(
                {
                    "type": "bullish",
                    "top": low.iloc[i],
                    "bottom": high.iloc[i - 2],
                    "created_at": ts,
                    "inverted_at": None,
                }
            )
    return fvgs


def mark_inversions(fvgs, data: pd.DataFrame):
    """A bearish FVG (created as resistance, price gapping down through
    it) inverts to support once a later close moves back above its top.
    A bullish FVG (support) inverts to resistance once a later close
    moves below its bottom. Mutates and returns `fvgs`."""
    for gap in fvgs:
        after = data.loc[gap["created_at"] :].iloc[1:]
        if gap["type"] == "bearish":
            crossed = after[after.Close > gap["top"]]
        else:
            crossed = after[after.Close < gap["bottom"]]
        gap["inverted_at"] = crossed.index[0] if len(crossed) else None
    return fvgs
