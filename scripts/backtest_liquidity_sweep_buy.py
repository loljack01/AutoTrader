"""Liquidity Sweep + CHoCH, buy side only, rules frozen on 2026-10-07.

Buy rule: an EQL pool is swept (Low < level, Close > level), then a
bullish CHoCH occurs within 4h; entry at the close of the bar where both
are true. Stop = max(sweep low - 8pt, 1x ATR(14)) below entry. Target =
nearest unswept EQH above entry, falling back to the last confirmed swing
high. Round-trip cost 3pt, minimum net R:R 1.3, Paris session filter, one
open trade at a time. Optional location filter: buy only below the
execution-timeframe range equilibrium (discount).

One trade per sweep: once a sweep has produced a trade, it cannot trigger
another one, whatever the outcome. Without this, a stopped-out setup
re-entered minutes later while still inside the 4h window, stacking
several losses on the same idea (e.g. 5 stops in 2h on 2026-09-30).

No edge has been demonstrated for this strategy. Everything up to
2026-10-07 has already been examined; a genuine test only uses bars
after that date (`--since 2026-10-08`).

Usage: python scripts/backtest_liquidity_sweep_buy.py [5m|15m|1h] [--since YYYY-MM-DD]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from finta import TA

from data import cache
from levels import structure, liquidity
from setups import session
from setups.net_r import net_rr

SYMBOL = "FCE1!"
ROUND_TRIP_COST = 3.0
MIN_NET_RR = 1.3
STOP_MARGIN = 8.0
SWING_N = 2
MIN_RISK_ATR_MULT = 1.0
CHOCH_LOOKBACK = {"5m": 48, "15m": 16, "1h": 4}  # 4h in bars


def backtest(d, lookback, one_trade_per_sweep=True, discount_only=False, since=None):
    n = len(d)
    atr = TA.ATR(d, 14)
    is_hi, is_lo = structure.find_swings(d, n=SWING_N)
    sh = structure.confirmed_level(is_hi, d.High, SWING_N)
    sl = structure.confirmed_level(is_lo, d.Low, SWING_N)
    bull_bos, bear_bos = structure.bos_events(d.Close, sh, sl)
    bull_choch = (structure.choch_events(bull_bos, bear_bos) & bull_bos).to_numpy()
    equilibrium = ((sh + sl) / 2).to_numpy()

    hi_marks = structure.confirmed_marks(is_hi, d.High, SWING_N)
    lo_marks = structure.confirmed_marks(is_lo, d.Low, SWING_N)
    eqh = liquidity.find_sweeps(liquidity.find_pools(hi_marks, atr), d, "high")
    eql = liquidity.find_sweeps(liquidity.find_pools(lo_marks, atr), d, "low")
    pos = {ts: i for i, ts in enumerate(d.index)}
    swing_high_conf = hi_marks.ffill()

    sweep_low = {}
    for p in eql:
        if p["swept_at"] is not None:
            i = pos[p["swept_at"]]
            sweep_low[i] = min(sweep_low.get(i, np.inf), d.Low.iloc[i])

    def nearest_unswept_eqh(i, entry):
        levels = [
            p["level"] for p in eqh
            if pos[p["members"][1][0]] <= i
            and not (p["swept_at"] is not None and p["swept_at"] <= d.index[i])
            and p["level"] > entry
        ]
        return min(levels) if levels else None

    start = d.index.searchsorted(pd.Timestamp(since, tz="UTC")) if since else 0
    trades = []
    open_trade = None
    last_sweep = None
    used_sweeps = set()

    for i in range(n):
        if i in sweep_low:
            last_sweep = (i, sweep_low[i])

        if open_trade is not None:
            bar = d.iloc[i]
            hit = "stop" if bar.Low <= open_trade["stop"] else ("take" if bar.High >= open_trade["take"] else None)
            if hit:
                risk = open_trade["entry"] - open_trade["stop"]
                cost_r = ROUND_TRIP_COST / risk
                gross = (open_trade["take"] - open_trade["entry"]) / risk if hit == "take" else -1.0
                net = gross - cost_r if hit == "take" else -(1.0 + cost_r)
                trades.append({**open_trade, "exit_time": d.index[i], "result": hit, "net_r": net})
                open_trade = None

        if i < start or open_trade is not None or last_sweep is None:
            continue
        sweep_i, sweep_extreme = last_sweep
        if i - sweep_i > lookback or (one_trade_per_sweep and sweep_i in used_sweeps):
            continue
        if not bull_choch[sweep_i:i + 1].any():
            continue
        dt = d.index[i]
        if not session.entry_allowed(session.session_window(dt.tz_convert("Europe/Paris"))):
            continue
        close = float(d.Close.iloc[i])
        if discount_only and not (close < equilibrium[i]):
            continue

        atr_val = atr.iloc[i]
        risk = max(close - (sweep_extreme - STOP_MARGIN), MIN_RISK_ATR_MULT * atr_val if not np.isnan(atr_val) else 0.0)
        stop = close - risk
        take = nearest_unswept_eqh(i, close)
        if take is None:
            take = swing_high_conf.iloc[i]
        if take is None or np.isnan(take) or take <= close:
            continue
        if net_rr(close, stop, take, ROUND_TRIP_COST) < MIN_NET_RR:
            continue

        open_trade = {"entry_time": dt, "sweep_time": d.index[sweep_i], "entry": close, "stop": float(stop), "take": float(take)}
        used_sweeps.add(sweep_i)

    return pd.DataFrame(trades, columns=["entry_time", "sweep_time", "entry", "stop", "take", "exit_time", "result", "net_r"])


def summarize(label, t):
    if t.empty:
        print(f"  {label:34s} 0 trade")
        return
    wins = (t.result == "take").mean()
    print(f"  {label:34s} n={len(t):3d}  WR={wins:5.1%}  net={t.net_r.sum():+6.1f}R  moy={t.net_r.mean():+.2f}R")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("interval", nargs="?", default="5m", choices=sorted(CHOCH_LOOKBACK))
    parser.add_argument("--since", help="only open trades on bars at or after this UTC date")
    args = parser.parse_args()

    d = cache.closed_bars(cache.load(SYMBOL, args.interval), args.interval, pd.Timestamp.now(tz="UTC"))
    lookback = CHOCH_LOOKBACK[args.interval]
    print(f"{SYMBOL} {args.interval}: {d.index[0]} -> {d.index[-1]} ({len(d)} bars)" + (f", trades since {args.since}" if args.since else ""))
    for discount_only in (False, True):
        for one_per_sweep in (False, True):
            label = ("discount" if discount_only else "sans filtre") + (", 1 trade/balayage" if one_per_sweep else ", re-entrees")
            summarize(label, backtest(d, lookback, one_per_sweep, discount_only, args.since))


if __name__ == "__main__":
    main()
