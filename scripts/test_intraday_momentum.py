"""INTRADAY strategy "Momentum de fin de seance" (market intraday momentum:
Gao, Han, Li & Zhou, "Market intraday momentum", Journal of Financial
Economics 2018 - the return from the previous close to the end of the first
half-hour predicts the return of the last half-hour), rules fixed on
2026-11-05 BEFORE running, at the user's request ("build yourself an
intraday strategy"). 20th idea; taken from the literature, not from a
chart, and different from everything tested before (no sweep, no range, no
VWAP). The published rule is used as it is: nothing is tuned (no other
window, threshold or filter is tried).

Data: 15m bars of the 10 index futures of the main strategy in data/cache
(FCE1!, FDAX1!, FESX1!, ES1!, NQ1!, ICEEUR:Z1!, FSMI1!, YM1!, RTY1!, FIB1!),
every closed cash session in the cache up to 2026-11-04 (CAC from 22/05,
the others from July-August 2026: a few months only, read as indicative).
Cash sessions as in scripts/gap_fill_test.py: Europe 9:00-17:30 Paris, US
9:30-16:00 New York. Previous official close = previous daily (1D) close.

Rule, per market and per cash session:
  signal  r1 = close of the 15m bar ending 30 min after the cash open
          (9:30 Paris / 10:00 New York) / previous official close - 1
  entry   at the close of the 15m bar ending 30 min before the end of the
          session (17:00 Paris / 15:30 New York), in the direction of r1
          (call if r1 > 0, put if r1 < 0, nothing if r1 = 0)
  exit    close of the last bar of the session (17:30 Paris / 16:00 New
          York); protective stop (needed for a turbo) at 0.5 x daily
          ATR(14) from the entry, checked on the bars in between (an open
          beyond the stop exits at the open)
R = the stop distance (0.5 daily ATR). Costs round trip: 1 point CAC
equivalent (x the market factor of frozen_15m_calls_trend.py) and 3 points.

Random baseline: the same trades with a random direction (coin flip),
2000 draws (seed 0), pooled net R at 1 point.

Decision rule (fixed before running): worth live tracking WITHOUT money
only if ALL of:
  - at least 300 trades;
  - pooled net R > 0 at 1 point AND at 3 points;
  - both halves (each market's sessions split at its middle session,
    halves summed) > 0 at 1 point;
  - at least 6 of the 10 markets > 0 at 1 point;
  - pooled net R at 1 point above the 95th percentile of the random
    baseline.
Otherwise REJETE, no re-tuning.

Result (run on 2026-11-05, 874 trades on the 10 markets): REJETE. 43 %
winners, net -32.2R at 1pt (-0.037R/trade), -68.1R at 3pt; calls -23.7R
(492), puts -8.5R (382); halves -15.5R / -16.6R; 0 of 10 markets positive;
random direction 95th percentile -6.1R (median -17.6R): the published
effect does not show on these futures over these months, it is even
slightly reversed (the last half-hour tends to go against the morning).

Usage: python scripts/test_intraday_momentum.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from gap_fill_test import daily_ref, local_clock, session

END = "2026-11-05"
STOP_ATR, N_RANDOM, MIN_TRADES, MIN_MARKETS = 0.5, 2000, 300, 6


def trades(symbol, k):
    now = pd.Timestamp.now(tz="UTC")
    d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
    d.index = pd.to_datetime(d.index, utc=True)
    d = d[d.index < pd.Timestamp(END, tz="UTC")]
    _, open_h, end_h = session(symbol)
    h, date = local_clock(symbol, d)
    ref, datr = daily_ref(symbol, d)
    o, hi, lo, c = (d[x].to_numpy() for x in ("Open", "High", "Low", "Close"))
    rows = []
    for day in np.unique(date):
        idx = np.flatnonzero(date == day)
        a = idx[np.isclose(h[idx], open_h + 0.5)]
        e = idx[np.isclose(h[idx], end_h - 0.5)]
        x = idx[np.isclose(h[idx], end_h)]
        if not (len(a) and len(e) and len(x)) or not a[0] < e[0] < x[0]:
            continue
        a, e, x = a[0], e[0], x[0]
        if np.isnan(ref[a]) or np.isnan(datr[e]) or c[a] == ref[a]:
            continue
        side = 1 if c[a] > ref[a] else -1
        entry, risk = c[e], STOP_ATR * datr[e]
        stop, px = entry - side * risk, c[x]
        for j in range(e + 1, x + 1):
            if (side == 1 and lo[j] <= stop) or (side == -1 and hi[j] >= stop):
                px = o[j] if ((o[j] <= stop) if side == 1 else (o[j] >= stop)) else stop
                break
        rows.append({"day": day, "side": side, "r1": c[a] / ref[a] - 1, "move": side * (px - entry) / risk,
                     "cost1": 1.0 * k / risk, "stopped": px == stop})
    return pd.DataFrame(rows, columns=["day", "side", "r1", "move", "cost1", "stopped"])


def main():
    rng = np.random.default_rng(0)
    allt, per, halves = [], {}, [0.0, 0.0]
    print(f"Momentum de fin de seance, 15m, sessions closes jusqu'au {END} (exclu)")
    for symbol, (name, k) in MARKETS.items():
        t = trades(symbol, k)
        if t.empty:
            print(f"  {name:14s} aucune session exploitable")
            continue
        r1 = t.move - t.cost1
        per[name] = r1.sum()
        mid = len(t) // 2
        halves[0] += r1.iloc[:mid].sum()
        halves[1] += r1.iloc[mid:].sum()
        allt.append(t.assign(market=name))
        print(f"  {name:14s} {t.day.iloc[0]} -> {t.day.iloc[-1]} : {len(t):3d} trades, {(r1 > 0).mean():4.0%} gagnants, "
              f"net {r1.sum():+6.2f}R a 1pt, {(t.move - 3 * t.cost1).sum():+6.2f}R a 3pt, stops {t.stopped.sum()}")
    t = pd.concat(allt, ignore_index=True)
    n1, n3 = (t.move - t.cost1), (t.move - 3 * t.cost1)
    signs = rng.choice([-1.0, 1.0], size=(N_RANDOM, len(t)))
    rand = (signs * t.move.to_numpy()).sum(axis=1) - t.cost1.sum()
    p95 = np.percentile(rand, 95)
    pos = sum(v > 0 for v in per.values())
    print(f"\nTotal : {len(t)} trades, {(n1 > 0).mean():.0%} gagnants, net {n1.sum():+.2f}R a 1pt ({n1.mean():+.4f}R/trade), "
          f"{n3.sum():+.2f}R a 3pt")
    for s, lab in ((1, "calls (r1 > 0)"), (-1, "puts (r1 < 0)")):
        m = t.side == s
        print(f"  {lab:15s} {m.sum():4d} trades, net {n1[m].sum():+.2f}R a 1pt")
    print(f"Moities : {halves[0]:+.2f}R / {halves[1]:+.2f}R | marches positifs {pos}/10 | "
          f"hasard (sens tire au sort) 95e centile {p95:+.2f}R, mediane {np.median(rand):+.2f}R")
    ok = (len(t) >= MIN_TRADES and n1.sum() > 0 and n3.sum() > 0 and min(halves) > 0
          and pos >= MIN_MARKETS and n1.sum() > p95)
    print(f"\nRegle fixee avant : momentum de fin de seance {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
