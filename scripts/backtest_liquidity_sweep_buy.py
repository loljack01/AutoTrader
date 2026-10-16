"""Liquidity Sweep + CHoCH, buy side only, rules frozen on 2026-10-07.

Buy rule: an EQL pool is swept (Low < level, Close > level), then a
bullish CHoCH occurs within 4h of clock time (so a sweep never carries
over the overnight gap); entry at the close of the bar where both
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

Usage: python scripts/backtest_liquidity_sweep_buy.py [1m|5m|15m|1h] [--since YYYY-MM-DD]
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
CHOCH_WINDOW = pd.Timedelta(hours=4)
INTERVALS = ("1m", "5m", "15m", "1h")


def backtest(d, one_trade_per_sweep=True, discount_only=False, since=None, entry_mask=None, direction="buy",
             gap_fill=False, breakeven_r=None, session_exit=False, entry_hours=None, consumed_pools=False):
    """`entry_mask`: optional bool array aligned with `d`; entries are only
    allowed on bars where it is True (e.g. a higher-timeframe trend filter).
    `direction="sell"` runs the exact mirror: EQH sweep, bearish CHoCH,
    stop above the sweep high, target the nearest unswept EQL below,
    location filter = premium (above equilibrium).

    Audit options, all off by default (defaults reproduce the frozen rules):
    gap_fill        a bar opening beyond the stop/target exits at its open
    breakeven_r     once price has gone this many R in favour, stop -> entry
    session_exit    close any open trade at the last bar of each Paris day
    entry_hours     (start, end) Paris hours, e.g. (9.25, 17.5); entries outside are skipped
    consumed_pools  a pool closed through before being swept is consumed:
                    it can no longer be swept nor used as a target"""
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")
    side = 1 if direction == "buy" else -1
    n = len(d)
    atr = TA.ATR(d, 14)
    is_hi, is_lo = structure.find_swings(d, n=SWING_N)
    sh = structure.confirmed_level(is_hi, d.High, SWING_N)
    sl = structure.confirmed_level(is_lo, d.Low, SWING_N)
    bull_bos, bear_bos = structure.bos_events(d.Close, sh, sl)
    choch = structure.choch_events(bull_bos, bear_bos)
    trigger_choch = (choch & (bull_bos if side == 1 else bear_bos)).to_numpy()
    equilibrium = ((sh + sl) / 2).to_numpy()

    hi_marks = structure.confirmed_marks(is_hi, d.High, SWING_N)
    lo_marks = structure.confirmed_marks(is_lo, d.Low, SWING_N)
    eqh = liquidity.find_sweeps(liquidity.find_pools(hi_marks, atr), d, "high")
    eql = liquidity.find_sweeps(liquidity.find_pools(lo_marks, atr), d, "low")
    pos = {ts: i for i, ts in enumerate(d.index)}
    close_np = d.Close.to_numpy()

    def consumed_at(p, pool_type):
        """Index of the first close through the level after confirmation, or None."""
        if not consumed_pools:
            return None
        c = pos[p["members"][1][0]]
        after = close_np[c + 1:]
        hit = np.flatnonzero(after > p["level"]) if pool_type == "high" else np.flatnonzero(after < p["level"])
        return c + 1 + hit[0] if len(hit) else None

    for pools, kind in ((eqh, "high"), (eql, "low")):
        for p in pools:
            b = consumed_at(p, kind)
            p["broken_i"] = b
            if b is not None and p["swept_at"] is not None and pos[p["swept_at"]] > b:
                p["swept_at"] = None

    swept_pools, target_pools = (eql, eqh) if side == 1 else (eqh, eql)
    fallback_target = (hi_marks if side == 1 else lo_marks).ffill()
    extreme = d.Low if side == 1 else d.High

    sweeps = {}
    for p in swept_pools:
        if p["swept_at"] is not None:
            i = pos[p["swept_at"]]
            v = extreme.iloc[i]
            sweeps[i] = min(sweeps.get(i, np.inf), v) if side == 1 else max(sweeps.get(i, -np.inf), v)

    def nearest_unswept_target(i, entry):
        levels = [
            p["level"] for p in target_pools
            if pos[p["members"][1][0]] <= i
            and not (p["swept_at"] is not None and p["swept_at"] <= d.index[i])
            and not (p["broken_i"] is not None and p["broken_i"] <= i)
            and (p["level"] - entry) * side > 0
        ]
        if not levels:
            return None
        return min(levels) if side == 1 else max(levels)

    paris_idx = d.index.tz_convert("Europe/Paris")
    paris_date = paris_idx.date
    last_of_day = np.append(paris_date[1:] != paris_date[:-1], True)
    paris_hour = paris_idx.hour + paris_idx.minute / 60

    start = d.index.searchsorted(pd.Timestamp(since, tz="UTC")) if since else 0
    trades = []
    open_trade = None
    last_sweep = None
    used_sweeps = set()

    def close_trade(i, exit_price, result):
        risk = abs(open_trade["entry"] - open_trade["initial_stop"])
        cost_r = ROUND_TRIP_COST / risk
        if result == "take" and not gap_fill:
            net = abs(open_trade["take"] - open_trade["entry"]) / risk - cost_r
        elif result == "stop" and not gap_fill and breakeven_r is None:
            net = -(1.0 + cost_r)
        else:
            net = side * (exit_price - open_trade["entry"]) / risk - cost_r
        rec = {k: v for k, v in open_trade.items() if k != "initial_stop"}
        rec["stop"] = open_trade["initial_stop"]
        trades.append({**rec, "exit_time": d.index[i], "result": result, "net_r": net})

    for i in range(n):
        if i in sweeps:
            last_sweep = (i, sweeps[i])

        if open_trade is not None:
            bar = d.iloc[i]
            stop_lvl, take_lvl = open_trade["stop"], open_trade["take"]
            if side == 1:
                hit = "stop" if bar.Low <= stop_lvl else ("take" if bar.High >= take_lvl else None)
                gapped = (bar.Open <= stop_lvl) if hit == "stop" else (bar.Open >= take_lvl) if hit == "take" else False
            else:
                hit = "stop" if bar.High >= stop_lvl else ("take" if bar.Low <= take_lvl else None)
                gapped = (bar.Open >= stop_lvl) if hit == "stop" else (bar.Open <= take_lvl) if hit == "take" else False
            if hit:
                price = bar.Open if (gap_fill and gapped) else (stop_lvl if hit == "stop" else take_lvl)
                close_trade(i, price, hit)
                open_trade = None
            else:
                if breakeven_r is not None:
                    risk = abs(open_trade["entry"] - open_trade["initial_stop"])
                    fav = (bar.High - open_trade["entry"]) if side == 1 else (open_trade["entry"] - bar.Low)
                    if fav >= breakeven_r * risk:
                        open_trade["stop"] = open_trade["entry"]
                if session_exit and last_of_day[i]:
                    close_trade(i, close_np[i], "eod")
                    open_trade = None

        if i < start or open_trade is not None or last_sweep is None:
            continue
        sweep_i, sweep_extreme = last_sweep
        if d.index[i] - d.index[sweep_i] > CHOCH_WINDOW or (one_trade_per_sweep and sweep_i in used_sweeps):
            continue
        if not trigger_choch[sweep_i:i + 1].any():
            continue
        dt = d.index[i]
        if not session.entry_allowed(session.session_window(dt.tz_convert("Europe/Paris"))):
            continue
        if entry_hours is not None and not (entry_hours[0] <= paris_hour[i] < entry_hours[1]):
            continue
        if session_exit and last_of_day[i]:
            continue
        close = float(d.Close.iloc[i])
        if discount_only and not ((equilibrium[i] - close) * side > 0):
            continue
        if entry_mask is not None and not entry_mask[i]:
            continue

        atr_val = atr.iloc[i]
        risk = max((close - (sweep_extreme - side * STOP_MARGIN)) * side, MIN_RISK_ATR_MULT * atr_val if not np.isnan(atr_val) else 0.0)
        stop = close - side * risk
        take = nearest_unswept_target(i, close)
        if take is None:
            take = fallback_target.iloc[i]
        if take is None or np.isnan(take) or (take - close) * side <= 0:
            continue
        if net_rr(close, stop, take, ROUND_TRIP_COST) < MIN_NET_RR:
            continue

        open_trade = {"entry_time": dt, "sweep_time": d.index[sweep_i], "entry": close, "stop": float(stop),
                      "initial_stop": float(stop), "take": float(take)}
        used_sweeps.add(sweep_i)

    if open_trade is not None:
        rec = {k: v for k, v in open_trade.items() if k != "initial_stop"}
        rec["stop"] = open_trade["initial_stop"]
        trades.append({**rec, "exit_time": None, "result": "open", "net_r": np.nan})
    return pd.DataFrame(trades, columns=["entry_time", "sweep_time", "entry", "stop", "take", "exit_time", "result", "net_r"])


def summarize(label, t):
    t = t[t.result != "open"]
    if t.empty:
        print(f"  {label:34s} 0 trade")
        return
    wins = (t.result == "take").mean()
    print(f"  {label:34s} n={len(t):3d}  WR={wins:5.1%}  net={t.net_r.sum():+6.1f}R  moy={t.net_r.mean():+.2f}R")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("interval", nargs="?", default="5m", choices=INTERVALS)
    parser.add_argument("--since", help="only open trades on bars at or after this UTC date")
    args = parser.parse_args()

    d = cache.closed_bars(cache.load(SYMBOL, args.interval), args.interval, pd.Timestamp.now(tz="UTC"))
    print(f"{SYMBOL} {args.interval}: {d.index[0]} -> {d.index[-1]} ({len(d)} bars)" + (f", trades since {args.since}" if args.since else ""))
    for discount_only in (False, True):
        for one_per_sweep in (False, True):
            label = ("discount" if discount_only else "sans filtre") + (", 1 trade/balayage" if one_per_sweep else ", re-entrees")
            summarize(label, backtest(d, one_per_sweep, discount_only, args.since))


if __name__ == "__main__":
    main()
