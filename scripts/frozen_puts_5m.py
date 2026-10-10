"""FROZEN on 2026-10-10: Liquidity Sweep + CHoCH, puts only (sell side),
FCE1! 5m, stop floor 2x ATR, one trade per sweep. Do not change these
settings; the point is to judge them on bars after the freeze only.

Rules (the sell mirror of scripts/backtest_liquidity_sweep_buy.py):
    - an EQH pool is swept (High > level, Close < level), then a bearish
      CHoCH occurs within 4h of clock time; entry at that bar's close
    - stop = max(sweep high + 8pt, 2x ATR(14)) above entry
    - target = nearest unswept EQL below entry, else last confirmed swing low
    - minimum net R:R 1.3, Paris session filter, one open trade at a time,
      one trade per sweep, no premium/discount filter
    - cost 1pt round trip (Boursorama turbo spread estimate); 3pt shown
      as a pessimistic check

Scorecard: only trades entered on or after FREEZE_START count. Capital
simulation: 1000 EUR start, 1% of current capital risked per trade.

Reference (data up to the 2026-10-09 close, before the freeze): 36 puts,
16 winners, +8.9R at 1pt cost. If a re-run on that period gives
something else, the underlying code changed and the freeze is broken.

Usage: python scripts/frozen_puts_5m.py [--capital 1000] [--since 2026-10-12|debut]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

import backtest_liquidity_sweep_buy as bt

FREEZE_START = "2026-10-12"
REFERENCE_END = "2026-10-10"
REFERENCE = {"n": 36, "net_r": 8.9}
INTERVAL = "5m"
START_CAPITAL = 1000.0
RISK_PCT = 0.01
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_puts_5m_trades.csv"


def run(d, cost):
    bt.ROUND_TRIP_COST = cost
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    return bt.backtest(d, one_trade_per_sweep=True, discount_only=False, direction="sell")


def capital(trades, start=START_CAPITAL):
    equity = start
    stakes, events = {}, []
    for k, t in trades.iterrows():
        events += [(t.entry_time, 0, k), (t.exit_time, 1, k)]
    for _, kind, k in sorted(events):
        if kind == 0:
            stakes[k] = equity * RISK_PCT
        else:
            equity += trades.loc[k, "net_r"] * stakes.pop(k)
    return equity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capital", type=float, default=START_CAPITAL)
    parser.add_argument("--since", default=FREEZE_START)
    args = parser.parse_args()
    since = None if args.since == "debut" else args.since
    d = bt.cache.closed_bars(bt.cache.load(bt.SYMBOL, INTERVAL), INTERVAL, pd.Timestamp.now(tz="UTC"))
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    print(f"FCE1! {INTERVAL} jusqu'au {paris(d.index[-1])} (Paris)")

    ref = run(d[d.index < REFERENCE_END], 1.0)
    ref = ref[ref.result != "open"]
    ok = len(ref) == REFERENCE["n"] and round(ref.net_r.sum(), 1) == REFERENCE["net_r"]
    print(f"Controle reference avant gel: {len(ref)} puts, {ref.net_r.sum():+.1f}R -> {'OK' if ok else 'DIFFERENT, le code a change'}")

    for cost in (1.0, 3.0):
        t = run(d, cost)
        if since:
            t = t[t.entry_time >= since].reset_index(drop=True)
        closed = t[t.result != "open"]
        opened = t[t.result == "open"]
        wins = (closed.result == "take").sum()
        label = f"Depuis le {since}" if since else "Depuis le debut"
        print(f"\n=== {label}, cout {cost:.0f}pt: {len(closed)} puts clos, {wins} gagnants, net {closed.net_r.sum():+.2f}R, "
              f"capital {capital(closed, args.capital):,.0f} EUR (depart {args.capital:,.0f}, risque {RISK_PCT:.0%}) ===")
        for _, r in t.iterrows():
            exit_txt = "OUVERT" if r.result == "open" else f"{r.result} {paris(r.exit_time)} {r.net_r:+.2f}R"
            print(f"  {paris(r.entry_time)}  put entree {r.entry:.1f}  stop {r.stop:.1f}  cible {r['take']:.1f}  -> {exit_txt}")
        if cost == 1.0 and since == FREEZE_START:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            t.to_csv(OUT, index=False)
        if len(opened) == 0 and len(t) == 0:
            print("  aucun put depuis le gel")


if __name__ == "__main__":
    main()
