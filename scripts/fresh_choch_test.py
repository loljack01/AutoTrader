"""Fresh CHoCH entry, rules fixed on 2026-10-27 BEFORE running.

Problem seen on the 27/10 CAC puts (1m and 5m): the frozen rules accept an
entry as long as ONE CHoCH happened since the sweep (4h window), at the
first bar where net R:R >= 1.3. That R:R rises when price moves back
against the setup, so entries often come late, after the CHoCH has
already failed (up to 31 bars and +4.2R later).

Fix (both sides, mirror for calls), added to the frozen 15m rules:
  A fresh   entry only on the most recent CHoCH bar or at most 3 bars after it
  B valid   no entry once a close has gone back beyond the level that CHoCH
            broke (above it for puts, below it for calls)
  fix       A + B
Everything else is the frozen 15m set (2x ATR stop floor, 8pt margin,
4h window, net R:R >= 1.3, Paris session filter, one trade per sweep),
calls and puts with no trend filter, stop margin and cost scaled by the
fixed per-market factors of scripts/frozen_15m_calls_trend.py.

The CAC history was glanced at while diagnosing (late entries looked a
bit worse on CAC 5m/15m, mixed and small), so the decision uses the 9
OTHER markets only; CAC is shown for information.

Decision rule (fixed before running): "fix" becomes a NEW candidate,
tracked live next to the frozen versions (which do not change), only if
on the 9 other markets pooled:
  - its net R is > 0 at 1pt AND at 3pt-equivalent cost, and
  - it beats the frozen rules (base) at both costs, and
  - its net R is > 0 on at least 5 of the 9 markets at 1pt.
A and B alone, and the fix on calls and puts separately, are shown for
information only.

Usage: python scripts/fresh_choch_test.py
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

VERSIONS = {"base": {}, "A fresh (3 barres)": {"choch_max_age": 3},
            "B invalidation": {"choch_invalidation": True},
            "fix (A+B)": {"choch_max_age": 3, "choch_invalidation": True}}


def run(d, k, cost, opts):
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    t = pd.concat([bt.backtest(d, True, False, direction=dr, **opts).assign(side=dr) for dr in ("buy", "sell")],
                  ignore_index=True)
    return t[t.result != "open"]


def main():
    now = pd.Timestamp.now(tz="UTC")
    res = {(v, c): {} for v in VERSIONS for c in (1.0, 3.0)}
    sides = {}
    for symbol, (name, k) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        print(f"\n## {name}{' (info seulement)' if symbol == 'FCE1!' else ''}")
        for v, opts in VERSIONS.items():
            line = []
            for cost in (1.0, 3.0):
                t = run(d, k, cost, opts)
                r = t.net_r.to_numpy()
                res[(v, cost)][symbol] = r
                if cost == 1.0 and v in ("base", "fix (A+B)"):
                    sides[(v, symbol)] = (t[t.side == "buy"].net_r.sum(), t[t.side == "sell"].net_r.sum())
                line.append(f"{len(r):3d} trades {(r > 0).mean() if len(r) else 0:4.0%} {r.sum():+6.1f}R")
            print(f"  {v:20s} 1pt-eq: {line[0]} | 3pt-eq: {line[1]}")
    others = [s for s in MARKETS if s != "FCE1!"]
    print("\n## 9 autres marches ensemble (decision)")
    for v in VERSIONS:
        r1 = np.concatenate([res[(v, 1.0)][s] for s in others])
        r3 = np.concatenate([res[(v, 3.0)][s] for s in others])
        pos = sum(res[(v, 1.0)][s].sum() > 0 for s in others)
        calls = sum(sides[(v, s)][0] for s in others) if (v, others[0]) in sides else np.nan
        puts = sum(sides[(v, s)][1] for s in others) if (v, others[0]) in sides else np.nan
        extra = f" | calls {calls:+.1f}R puts {puts:+.1f}R" if not np.isnan(calls) else ""
        print(f"  {v:20s} 1pt-eq: n={len(r1):3d} gagnants={(r1 > 0).mean():4.0%} net={r1.sum():+6.1f}R moy={r1.mean():+.3f}R "
              f"t={tstat(r1):+.2f} | 3pt-eq net={r3.sum():+6.1f}R | marches positifs {pos}/9{extra}")
    f1 = sum(res[("fix (A+B)", 1.0)][s].sum() for s in others)
    f3 = sum(res[("fix (A+B)", 3.0)][s].sum() for s in others)
    b1 = sum(res[("base", 1.0)][s].sum() for s in others)
    b3 = sum(res[("base", 3.0)][s].sum() for s in others)
    pos = sum(res[("fix (A+B)", 1.0)][s].sum() > 0 for s in others)
    ok = f1 > 0 and f3 > 0 and f1 > b1 and f3 > b3 and pos >= 5
    print(f"\nRegle fixee avant: fix {'RETENU comme nouvelle candidate' if ok else 'NON RETENU'} "
          f"(9 marches: {f1:+.1f}R a 1pt-eq, {f3:+.1f}R a 3pt-eq ; base {b1:+.1f}/{b3:+.1f}R ; marches positifs {pos}/9)")


if __name__ == "__main__":
    main()
