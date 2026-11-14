"""Limit entry on a pullback after the CHoCH, rules fixed on 2026-10-28
BEFORE running (idea from the user on the 28/10 CAC 1m put: "the entry
should have been higher").

Frozen 15m rules (sweep + CHoCH, stop = max(sweep extreme +/- 8pt, 2x
ATR), target = nearest unswept opposite pool, net R:R >= 1.3 checked at
the signal close, 4h window, Paris session filter, one trade per sweep),
calls and puts with no trend filter, cost and stop margin scaled by the
fixed per-market factors of scripts/frozen_15m_calls_trend.py.

  base   entry at the signal close (frozen)
  limit  instead, a limit order halfway between the signal close and the
         stop (limit_frac=0.5), valid 4 bars; same stop and target, so
         the risk is halved and the reward grows. Filled at the limit
         when a bar touches it; a fill bar that also touches the stop is
         a stop; the fill bar never counts as reaching the target.
         Cancelled (missed) if the target is touched first or after 4
         bars. A missed setup still uses its sweep.

The danger is adverse selection: the setups that never pull back are
often the best ones, and they are the ones a limit order misses. Shown
for information: fill rate, and what the base trades of the missed setups
made (matched by sweep).

Decision rule (fixed before running), on the 10 markets pooled: "limit"
becomes a NEW candidate, tracked live next to the frozen versions (which
do not change), only if its net R is > 0 at 1pt AND 3pt-equivalent cost,
it beats base at both costs, and its net R is > 0 on at least 6 of the 10
markets at 1pt. Otherwise rejected, no re-tuning (no other fraction or
validity tried).

Usage: python scripts/limit_entry_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from other_markets_test import tstat

VERSIONS = {"base": {}, "limit": {"limit_frac": 0.5, "limit_bars": 4}}


def run(d, k, cost, opts):
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    return pd.concat([bt.backtest(d, True, False, direction=dr, **opts).assign(side=dr) for dr in ("buy", "sell")],
                     ignore_index=True)


def main():
    now = pd.Timestamp.now(tz="UTC")
    res = {(v, c): {} for v in VERSIONS for c in (1.0, 3.0)}
    fills = missed = 0
    missed_base = []
    for symbol, (name, k) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        line = {}
        for v, opts in VERSIONS.items():
            parts = []
            for cost in (1.0, 3.0):
                t = run(d, k, cost, opts)
                closed = t[t.result.isin(["stop", "take"])]
                r = closed.net_r.to_numpy()
                res[(v, cost)][symbol] = r
                parts.append(f"{len(r):3d} trades {(r > 0).mean() if len(r) else 0:4.0%} {r.sum():+6.1f}R")
                if cost == 1.0 and v == "base":
                    base_t = closed
                if cost == 1.0 and v == "limit":
                    m = t[t.result == "missed"]
                    fills += len(closed)
                    missed += len(m)
                    missed_base.append(base_t[base_t.sweep_time.isin(m.sweep_time)].net_r.to_numpy())
            line[v] = " | 3pt-eq: ".join(parts)
        print(f"{name:14s} base 1pt-eq: {line['base']}\n{'':14s} limit 1pt-eq: {line['limit']}")
    print("\n## 10 marches ensemble")
    for v in VERSIONS:
        r1 = np.concatenate(list(res[(v, 1.0)].values()))
        r3 = np.concatenate(list(res[(v, 3.0)].values()))
        pos = sum(x.sum() > 0 for x in res[(v, 1.0)].values())
        print(f"  {v:6s} 1pt-eq: n={len(r1):3d} gagnants={(r1 > 0).mean():4.0%} net={r1.sum():+6.1f}R moy={r1.mean():+.3f}R "
              f"t={tstat(r1):+.2f} | 3pt-eq net={r3.sum():+6.1f}R | marches positifs {pos}/10")
    mb = np.concatenate(missed_base)
    print(f"\n  ordres limites: {fills} executes, {missed} rates ({missed / max(fills + missed, 1):.0%}) ; "
          f"les setups rates faisaient en base: {len(mb)} trades, {(mb > 0).mean() if len(mb) else 0:.0%} gagnants, {mb.sum():+.1f}R")
    l1 = sum(x.sum() for x in res[("limit", 1.0)].values())
    l3 = sum(x.sum() for x in res[("limit", 3.0)].values())
    b1 = sum(x.sum() for x in res[("base", 1.0)].values())
    b3 = sum(x.sum() for x in res[("base", 3.0)].values())
    pos = sum(x.sum() > 0 for x in res[("limit", 1.0)].values())
    ok = l1 > 0 and l3 > 0 and l1 > b1 and l3 > b3 and pos >= 6
    print(f"\nRegle fixee avant: limit {'RETENU comme nouvelle candidate' if ok else 'REJETE'} "
          f"({l1:+.1f}R a 1pt-eq, {l3:+.1f}R a 3pt-eq ; base {b1:+.1f}/{b3:+.1f}R ; marches positifs {pos}/10)")


if __name__ == "__main__":
    main()
