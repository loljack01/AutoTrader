"""Liquidity pools and sweeps (SPEC section 2.2).

    EQH / EQL : deux extrêmes ou plus dont l'écart est inférieur à
    max(2 points, 0.25 x ATR(14) de l'unité de temps) -> pool de
    liquidité.

    Balayage (sweep) : une mèche dépasse le pool, puis la bougie clôture
    de l'autre côté.

Pools are built from CONFIRMED swings only (levels/structure.py's
confirmed_marks output) - an unconfirmed pivot cannot yet be part of a
liquidity pool, for the same look-ahead reason a swing itself isn't
known before its confirmation bar.
"""

import numpy as np
import pandas as pd


def find_pools(
    marks: pd.Series, atr: pd.Series, min_points: float = 2.0, atr_mult: float = 0.25
):
    """`marks`: a confirmed_marks()-style Series (NaN except exactly at
    each swing's confirmation bar). Walks the confirmed swings in time
    order; a swing joins the currently open pool if it's within
    tolerance of that pool's reference level (the first member's price),
    otherwise it starts a new pool. Tolerance is evaluated at the
    joining swing's own bar. Only pools with 2+ members are real
    liquidity pools (a single swing isn't "equal" to anything yet)."""
    pools = []
    current = None
    for ts, price in marks.dropna().items():
        atr_val = atr.loc[ts]
        tol = (
            max(min_points, atr_mult * atr_val) if not np.isnan(atr_val) else min_points
        )
        if current is not None and abs(price - current["level"]) <= tol:
            current["members"].append((ts, price))
        else:
            current = {"level": price, "members": [(ts, price)]}
            pools.append(current)
    return [p for p in pools if len(p["members"]) >= 2]


def find_sweeps(pools, data: pd.DataFrame, pool_type: str):
    """For each pool, looks for the first bar after its 2nd member
    confirms where price wicks past the pool level and closes back on
    the other side. `pool_type`: 'high' (EQH - buy-side liquidity above
    price; swept when High > level then Close < level) or 'low' (EQL -
    sell-side liquidity below price; swept when Low < level then Close >
    level). Returns the input pools with a 'swept_at' key added
    (None if never swept in `data`)."""
    if pool_type not in ("high", "low"):
        raise ValueError("pool_type must be 'high' or 'low'")

    for pool in pools:
        confirm_ts = pool["members"][1][0]
        after = data.loc[confirm_ts:].iloc[1:]
        level = pool["level"]
        if pool_type == "high":
            hit = after[(after.High > level) & (after.Close < level)]
        else:
            hit = after[(after.Low < level) & (after.Close > level)]
        pool["swept_at"] = hit.index[0] if len(hit) else None
    return pools
