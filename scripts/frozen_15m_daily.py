"""FROZEN on 2026-10-10: Liquidity Sweep + CHoCH, calls AND puts, FCE1!
15m, stop floor 2x ATR, one trade per sweep, daily trend filter. Two
versions are tracked side by side and neither may be changed:

    sma20  (main)      calls only if the previous session's daily close is
                       above its 20-day SMA, puts only if below
    ema20  (candidate) same with a 20-day EMA instead of the SMA

Everything else is the frozen sweep rule set of
scripts/backtest_liquidity_sweep_buy.py (stop = max(sweep extreme +/- 8pt,
2x ATR), target = nearest unswept opposite pool, net R:R >= 1.3, Paris
session filter, 4h sweep->CHoCH window, one open trade per side), cost
1pt round trip with 3pt shown as a pessimistic check.

Scorecard: only trades entered on or after FREEZE_START count, unless
--since is given. Capital: --capital EUR, 1% of current capital risked
per trade.

Reference (data before 2026-10-10, 1pt): sma20 20 trades +10.0R,
ema20 18 trades +12.0R. A different result on that period means the
underlying code changed and the freeze is broken.

Usage: python scripts/frozen_15m_daily.py [--capital 1000] [--since 2026-10-12|debut]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt

FREEZE_START = "2026-10-12"
REFERENCE_END = "2026-10-10"
REFERENCE = {"sma20": (20, 10.0), "ema20": (18, 12.0)}
INTERVAL = "15m"
BAR = pd.Timedelta(minutes=15)
RISK_PCT = 0.01
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_daily_trades.csv"


def trend_up(d, kind):
    daily = bt.cache.load(bt.SYMBOL, "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    c = daily.Close
    ma = c.rolling(20).mean() if kind == "sma20" else c.ewm(span=20, adjust=False).mean()
    up = (c > ma).to_numpy() & ma.notna().to_numpy()
    done_at = (daily.index + pd.Timedelta(days=1)).to_numpy()
    pos = np.searchsorted(done_at, (d.index + BAR).to_numpy(), side="right") - 1
    return np.where(pos >= 0, up[np.clip(pos, 0, None)], False).astype(bool)


def run(d, kind, cost):
    bt.ROUND_TRIP_COST = cost
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    up = trend_up(d, kind)
    parts = []
    for direction, mask in (("buy", up), ("sell", ~up)):
        t = bt.backtest(d, one_trade_per_sweep=True, discount_only=False, entry_mask=mask, direction=direction)
        t["side"] = "call" if direction == "buy" else "put"
        parts.append(t)
    return pd.concat(parts, ignore_index=True).sort_values("entry_time").reset_index(drop=True)


def capital(trades, start):
    equity, low, high = start, start, start
    stakes, events = {}, []
    for k, t in trades.iterrows():
        events += [(t.entry_time, 0, k), (t.exit_time, 1, k)]
    max_dd = 0.0
    for _, kind, k in sorted(events):
        if kind == 0:
            stakes[k] = equity * RISK_PCT
        else:
            equity += trades.loc[k, "net_r"] * stakes.pop(k)
            low, high = min(low, equity), max(high, equity)
            max_dd = max(max_dd, 1 - equity / high)
    return equity, low, max_dd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--since", default=FREEZE_START)
    args = parser.parse_args()

    d = bt.cache.closed_bars(bt.cache.load(bt.SYMBOL, INTERVAL), INTERVAL, pd.Timestamp.now(tz="UTC"))
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m/%y %H:%M")
    print(f"FCE1! {INTERVAL} {paris(d.index[0])} -> {paris(d.index[-1])} (Paris), marche {d.Close.iloc[0]:.0f} -> {d.Close.iloc[-1]:.0f}")

    for kind, (n_ref, r_ref) in REFERENCE.items():
        ref = run(d[d.index < REFERENCE_END], kind, 1.0)
        ref = ref[ref.result != "open"]
        ok = len(ref) == n_ref and round(ref.net_r.sum(), 1) == r_ref
        print(f"Controle reference {kind}: {len(ref)} trades, {ref.net_r.sum():+.1f}R -> {'OK' if ok else 'DIFFERENT, le code a change'}")

    since = None if args.since == "debut" else args.since
    logs = []
    for kind in REFERENCE:
        for cost in (1.0, 3.0):
            t = run(d, kind, cost)
            if since:
                t = t[t.entry_time >= since].reset_index(drop=True)
            closed = t[t.result != "open"].reset_index(drop=True)
            eq, low, dd = capital(closed, args.capital)
            wins = (closed.result == "take").sum()
            c, p = closed[closed.side == "call"], closed[closed.side == "put"]
            label = "depuis le debut" if not since else f"depuis le {since}"
            print(f"\n=== {kind} {'(principal)' if kind == 'sma20' else '(candidate)'}, {label}, cout {cost:.0f}pt: {len(closed)} trades clos "
                  f"({len(c)} calls {c.net_r.sum():+.1f}R, {len(p)} puts {p.net_r.sum():+.1f}R), {wins} gagnants, net {closed.net_r.sum():+.2f}R | "
                  f"capital {args.capital:,.0f} -> {eq:,.0f} EUR ({eq / args.capital - 1:+.1%}), plus bas {low:,.0f}, baisse max {dd:.0%} ===")
            if cost == 1.0:
                for _, r in t.iterrows():
                    exit_txt = "OUVERT" if r.result == "open" else f"{r.result} {paris(r.exit_time)} {r.net_r:+.2f}R"
                    print(f"  {paris(r.entry_time)}  {r.side:4s} entree {r.entry:.1f}  stop {r.stop:.1f}  cible {r['take']:.1f}  -> {exit_txt}")
                logs.append(t.assign(version=kind))
    if since == FREEZE_START:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(logs, ignore_index=True).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
