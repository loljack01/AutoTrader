"""Two exit variants, fixed on 2026-10-26 BEFORE running, after a 1m call
(26/10 15:06) went 82% of the way to its target then was stopped.

Base: frozen live rule set (2x ATR stop floor, 8pt margin, one trade per
sweep, net R:R >= 1.3, 4h window, Paris session filter), calls and puts,
no trend filter. Entries are the same in all three versions (selected with
the full target); only the exit changes.

  A "cible avancee": take profit at 80% of the way to the target.
  B "stop a l'entree": once price has gone +1R in favour, the stop moves
    to the entry price (exit there costs the round trip only).

Decision rule (fixed before running): a variant is kept as a NEW candidate
(tracked separately, frozen versions unchanged) only if its net R beats
the base on BOTH halves of the history, on BOTH 5m and 15m, at BOTH 1pt
and 3pt cost. 1m is shown for information only (5 weeks of data).

Usage: python scripts/exit_variants_test.py [tool_result.json ...]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt

VARIANTS = {"base": {}, "A cible 80%": {"take_frac": 0.8}, "B stop a l'entree a +1R": {"breakeven_r": 1.0}}


def set_rules(cost):
    bt.ROUND_TRIP_COST = cost
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)


def run(d, cost, kwargs):
    set_rules(cost)
    parts = [bt.backtest(d, True, False, direction=direction, **kwargs) for direction in ("buy", "sell")]
    t = pd.concat(parts, ignore_index=True)
    return t[t.result != "open"].sort_values("entry_time").reset_index(drop=True)


def main():
    for f in sys.argv[1:]:
        j = json.load(open(f))
        bt.cache.ingest(bt.SYMBOL, j["interval"], j["bars"])
    now = pd.Timestamp.now(tz="UTC")
    verdict = {k: [] for k in VARIANTS if k != "base"}
    for iv in ("1m", "5m", "15m"):
        d = bt.cache.closed_bars(bt.cache.load(bt.SYMBOL, iv), iv, now)
        half = d.index[len(d) // 2]
        print(f"\n######## {iv}: {d.index[0].date()} -> {d.index[-1].date()} (moitie au {half.date()})")
        for cost in (1.0, 3.0):
            res = {}
            for name, kwargs in VARIANTS.items():
                t = run(d, cost, kwargs)
                r = t.net_r.to_numpy()
                h1, h2 = t[t.entry_time < half].net_r.sum(), t[t.entry_time >= half].net_r.sum()
                res[name] = (h1, h2)
                wins = (r > 0).mean() if len(r) else 0
                print(f"  cout {cost:.0f}pt {name:24s} n={len(t):3d} gagnants={wins:4.0%} net={r.sum():+6.1f}R moy={r.mean() if len(r) else 0:+.3f}R | moities {h1:+.1f}/{h2:+.1f}R")
            if iv in ("5m", "15m"):
                b1, b2 = res["base"]
                for name in verdict:
                    v1, v2 = res[name]
                    verdict[name].append(v1 > b1 and v2 > b2)
    print("\nRegle fixee avant (bat la base sur les 2 moities, en 5m ET 15m, a 1pt ET 3pt):")
    for name, v in verdict.items():
        print(f"  {name}: {'RETENU comme nouvelle candidate' if all(v) else 'NON RETENU'} ({sum(v)}/{len(v)} cas gagnes)")


if __name__ == "__main__":
    main()
