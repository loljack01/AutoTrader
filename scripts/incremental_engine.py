"""Bar-by-bar re-implementation of the MAIN strategy engine
(backtest_liquidity_sweep_buy.backtest with the frozen_15m_calls_trend
settings: one trade per sweep, no discount filter, MIN_RISK_ATR_MULT 2,
STOP_MARGIN 8 x k, SWING_N 2, MIN_NET_RR 1.3, CHoCH window 4h, Paris session
filter, calls only when the previous daily close is above its 20-day SMA).

Written as the exact blueprint of tradingview/strategie_principale_alertes.pine:
every quantity is computed causally, one bar at a time, with the same state a
Pine script keeps in `var` variables. `compare()` checks that it reproduces
the reference engine's trades on the cached 15m data.

Usage: python scripts/incremental_engine.py [SYMBOL]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from ma_grid_test import trend_up
from setups import session


def run(d, k, cost_pts, up):
    """Returns the trades of both directions, like the reference engine."""
    o, h, l, c = (d[x].to_numpy() for x in ("Open", "High", "Low", "Close"))
    t = d.index
    n = len(d)
    tr = np.maximum.reduce([h - l, np.abs(h - np.roll(c, 1)), np.abs(np.roll(c, 1) - l)])
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    margin, cost = 8.0 * k, cost_pts * k
    allowed = np.array([session.entry_allowed(session.session_window(ts.tz_convert("Europe/Paris"))) for ts in t])

    # shared structure state
    sh = sl = np.nan                 # last confirmed swing high / low
    state = None                     # CHoCH state machine
    pools = {"high": [], "low": []}  # active pools: dict(level, confirm, swept)
    cur = {"high": None, "low": None}
    last_trig = {1: -1, -1: -1}
    last_sweep = {1: None, -1: None}
    used = {1: set(), -1: set()}
    open_tr = {1: None, -1: None}
    trades = []

    for i in range(n):
        # 1. sweeps of pools confirmed on earlier bars
        for kind, side in (("low", 1), ("high", -1)):
            for p in pools[kind]:
                if p["swept"] is None and p["confirm"] < i:
                    if (kind == "low" and l[i] < p["level"] and c[i] > p["level"]) or \
                       (kind == "high" and h[i] > p["level"] and c[i] < p["level"]):
                        p["swept"] = i
                        ext = l[i] if side == 1 else h[i]
                        last_sweep[side] = (i, ext)
        # 2. swing confirmed at this bar (pivot at i-2)
        j = i - 2
        if j >= 2 and i < n:
            if h[j] > h[j - 1] and h[j] > h[j - 2] and h[j] >= h[j + 1] and h[j] >= h[j + 2]:
                sh = h[j]
                _join("high", h[j], i, atr[i], cur, pools)
            if l[j] < l[j - 1] and l[j] < l[j - 2] and l[j] <= l[j + 1] and l[j] <= l[j + 2]:
                sl = l[j]
                _join("low", l[j], i, atr[i], cur, pools)
        # 3. BOS / CHoCH
        bull = not np.isnan(sh) and c[i] > sh
        bear = not np.isnan(sl) and c[i] < sl
        if bull:
            if state != "up":
                last_trig[1] = i
            state = "up"
        elif bear:
            if state != "down":
                last_trig[-1] = i
            state = "down"
        for side in (1, -1):
            # 4. exits (entry bar excluded)
            tr_ = open_tr[side]
            if tr_ is not None and tr_["i"] < i:
                hit = None
                if side == 1:
                    hit = "stop" if l[i] <= tr_["stop"] else ("take" if h[i] >= tr_["take"] else None)
                else:
                    hit = "stop" if h[i] >= tr_["stop"] else ("take" if l[i] <= tr_["take"] else None)
                if hit:
                    risk = abs(tr_["entry"] - tr_["stop"])
                    net = (abs(tr_["take"] - tr_["entry"]) / risk - cost / risk) if hit == "take" else -(1 + cost / risk)
                    trades.append({**{x: tr_[x] for x in ("entry_time", "entry", "stop", "take")},
                                   "side": side, "exit_time": t[i], "result": hit, "net_r": net})
                    open_tr[side] = None
            # 5. entries
            if open_tr[side] is not None or last_sweep[side] is None:
                continue
            si, ext = last_sweep[side]
            if t[i] - t[si] > pd.Timedelta(hours=4) or si in used[side] or last_trig[side] < si:
                continue
            if not allowed[i] or (side == 1 and not up[i]):
                continue
            risk = max((c[i] - (ext - side * margin)) * side, 2.0 * atr[i] if not np.isnan(atr[i]) else 0.0)
            stop = c[i] - side * risk
            tgt_kind = "high" if side == 1 else "low"
            cands = [p["level"] for p in pools[tgt_kind]
                     if p["confirm"] <= i and not (p["swept"] is not None and p["swept"] <= i)
                     and (p["level"] - c[i]) * side > 0]
            if cands:
                take = min(cands) if side == 1 else max(cands)
            else:
                take = sh if side == 1 else sl
            if take is None or np.isnan(take) or (take - c[i]) * side <= 0:
                continue
            if (abs(take - c[i]) - cost) / (risk + cost) < 1.3:
                continue
            open_tr[side] = {"i": i, "entry_time": t[i], "entry": c[i], "stop": stop, "take": take}
            used[side].add(si)
    for side in (1, -1):
        if open_tr[side] is not None:
            tr_ = open_tr[side]
            trades.append({**{x: tr_[x] for x in ("entry_time", "entry", "stop", "take")},
                           "side": side, "exit_time": None, "result": "open", "net_r": np.nan})
    return pd.DataFrame(trades)


def _join(kind, price, i, atr_i, cur, pools):
    tol = max(2.0, 0.25 * atr_i) if not np.isnan(atr_i) else 2.0
    p = cur[kind]
    if p is not None and abs(price - p["level"]) <= tol:
        p["count"] += 1
        if p["count"] == 2:
            p["confirm"] = i
            pools[kind].append(p)
    else:
        cur[kind] = {"level": price, "count": 1, "confirm": None, "swept": None}


def compare(symbol="FCE1!"):
    k = MARKETS[symbol][1]
    now = pd.Timestamp.now(tz="UTC")
    d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
    up = np.asarray(trend_up(symbol, d, "SMA", 20), bool)
    bt.ROUND_TRIP_COST, bt.MIN_RISK_ATR_MULT, bt.STOP_MARGIN = 1.0 * k, 2.0, 8.0 * k
    bt.SWING_N, bt.MIN_NET_RR, bt.CHOCH_WINDOW = 2, 1.3, pd.Timedelta(hours=4)
    ref = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up).assign(side=1),
                     bt.backtest(d, True, False, direction="sell").assign(side=-1)], ignore_index=True)
    inc = run(d, k, 1.0, up)
    key = lambda df: set(zip(df["side"], df["entry_time"], df["entry"].round(4), df["stop"].round(4), df["take"].round(4), df["result"]))
    a, b = key(ref), key(inc)
    print(f"{symbol}: reference {len(ref)} trades, incremental {len(inc)} trades, identical {len(a & b)}")
    for x in sorted(a - b, key=lambda z: z[1]):
        print("  only reference  ", x)
    for x in sorted(b - a, key=lambda z: z[1]):
        print("  only incremental", x)
    return a == b


if __name__ == "__main__":
    ok = all([compare(s) for s in (sys.argv[1:] or ["FCE1!"])])
    print("IDENTIQUE" if ok else "DIFFERENT")
