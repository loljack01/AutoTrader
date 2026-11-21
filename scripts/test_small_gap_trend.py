"""TEST 7 of docs/test_7_petit_ecart_tendance_fige_2026-11-09.md (frozen on
2026-11-09 BEFORE running, at the user's request: "Oui, fige le test").
Run on 2026-11-09 at the user's explicit order, which lifted the moratorium of
06/11 (rule 12 of docs/regles_execution.md) for this test only.

Origin and honesty: idea born from the CAC morning of 2026-11-09 (open below
the previous close, then +80 points, no signal of the main strategy nor of the
gap rules). It is therefore POST-HOC; no history of the 10 markets was used to
choose the parameters below, which are fixed here once and never re-tuned.

15m bars, each market's cash session (as scripts/gap_fill_test.py): European
futures open 9:00 Paris, US futures 9:30 New York.
  reference   R = previous official daily close (1D bar close)
  zone        small gap: |C0 - R| < 0.25 x daily ATR(14), C0 = close of the first
              15m bar of the cash session (the complement of the zone 0.25-1.0
              ATR of gap_fill_test.py and frozen_gap_continuation.py, which
              both skip it)
  direction   with the daily trend of the main strategy: buy if the previous
              daily close is above its 20-day SMA, sell otherwise
              (ma_grid_test.trend_up, same function as the main strategy)
  entry       at C0
  stop        0.5 x daily ATR(14) against the position
  target      0.5 x daily ATR(14) in favour (1:1)
  time exit   close of the bar ending 3h after the cash open
A bar that touches both stop and target counts as a stop. A stop is filled at
the stop, or at the open if the bar opens beyond it. One trade per market per
day. Cost 1pt and 3pt CAC-equivalent (fixed per-market factors from
scripts/frozen_15m_calls_trend.py).

Random baseline: for each real trade, a random cash-session day of the same
market, entry at its first 15m close, random direction, same stop and target
(0.5 ATR), same exits; 200 draws (seed 0).

Decision rule (fixed before running), ALL conditions:
  (a) at least 150 trades pooled over the 10 markets;
  (b) pooled net R > 0 at 1pt AND at 3pt;
  (c) both time halves (per market, summed) > 0 at 1pt;
  (d) at least 6 of 10 markets > 0 at 1pt;
  (e) pooled net R at 1pt above the 95th percentile of the random baseline;
  (f) t-statistic at 1pt >= 2.45 (Bonferroni 5 % / 7 tests, one-sided).
If passed: worth forward tracking WITHOUT money (100 trades), never directly
real money. Otherwise REJECTED, no parameter re-tuning. Data limit: 15m
history only starts between 2026-05 and 2026-08 depending on the market, so
the test is short; condition (a) guards against a tiny sample.
Multiple-testing budget: 7 tests (tests 1-7 of 2026).

Result (run on 2026-11-09 at the user's order "Lance le test 7"): REJETE. 425 trades
on the 10 markets, 49 % winners, net +4.0R at 1pt (+0.009R/trade, t = +0.35),
-13.5R at 3pt; halves -5.7R / +9.7R; 6 of 10 markets positive at 1pt; random
baseline median -9.6R, 95th percentile +11.9R. Conditions (b) 3pt, (c) halves,
(e) baseline and (f) t fail.

Usage: python scripts/test_small_gap_trend.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
import gap_fill_test as gf
from frozen_15m_calls_trend import MARKETS
from ma_grid_test import trend_up
from other_markets_test import tstat

ZONE_ATR, DIST_ATR, MIN_TRADES, T_MIN = 0.25, 0.5, 150, 2.45


def real_trades(symbol, d, cost):
    ref, datr = gf.daily_ref(symbol, d)
    up = np.asarray(trend_up(symbol, d, "SMA", 20), bool)
    rows = []
    for i, last in gf.days(symbol, d):
        r, a, c0 = ref[i], datr[i], d.Close.iat[i]
        if np.isnan(r) or np.isnan(a) or not abs(c0 - r) < ZONE_ATR * a:
            continue
        side = 1 if up[i] else -1
        rows.append({"time": d.index[i], "side": side,
                     "net_r": gf.trade(d, i, last, side, DIST_ATR * a, cost)})
    return pd.DataFrame(rows, columns=["time", "side", "net_r"])


def main():
    now = pd.Timestamp.now(tz="UTC")
    rng = np.random.default_rng(0)
    pooled = {1.0: [], 3.0: []}
    halves, positive, rand_totals = [0.0, 0.0], 0, np.zeros(200)
    for symbol, (name, k) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        half = d.index[len(d) // 2]
        line = {}
        for cost in (1.0, 3.0):
            t = real_trades(symbol, d, cost * k)
            r = t.net_r.to_numpy()
            pooled[cost].append(r)
            line[cost] = f"n={len(t):3d} gagnants={(r > 0).mean() if len(r) else 0:4.0%} net={r.sum():+6.1f}R"
            if cost == 1.0:
                halves[0] += t[t.time < half].net_r.sum()
                halves[1] += t[t.time >= half].net_r.sum()
                positive += r.sum() > 0
                n_real = len(t)
        _, datr = gf.daily_ref(symbol, d)
        pool = [(i, last) for i, last in gf.days(symbol, d) if not np.isnan(datr[i])]
        for s in range(200):
            tot = 0.0
            for _ in range(n_real):
                i, last = pool[rng.integers(len(pool))]
                tot += gf.trade(d, i, last, int(rng.choice((1, -1))), DIST_ATR * datr[i], 1.0 * k)
            rand_totals[s] += tot
        print(f"{name:14s} 1pt-eq: {line[1.0]} | 3pt-eq: {line[3.0]}")
    r1, r3 = np.concatenate(pooled[1.0]), np.concatenate(pooled[3.0])
    p95 = np.percentile(rand_totals, 95)
    ts = tstat(r1) if len(r1) > 2 else float("nan")
    print(f"\n10 marches ensemble: 1pt-eq n={len(r1)} gagnants={(r1 > 0).mean() if len(r1) else 0:.0%} net={r1.sum():+.1f}R "
          f"moy={r1.mean() if len(r1) else 0:+.3f}R t={ts:+.2f} | 3pt-eq net={r3.sum():+.1f}R")
    print(f"  moities {halves[0]:+.1f}/{halves[1]:+.1f}R | marches positifs {positive}/10 | "
          f"hasard: mediane {np.median(rand_totals):+.1f}R, 95e centile {p95:+.1f}R")
    ok = (len(r1) >= MIN_TRADES and r1.sum() > 0 and r3.sum() > 0 and min(halves) > 0
          and positive >= 6 and r1.sum() > p95 and ts >= T_MIN)
    print(f"\nRegle fixee avant: {'A SUIVRE SANS ARGENT' if ok else 'REJETEE'}")


if __name__ == "__main__":
    main()
