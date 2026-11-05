"""INTRADAY strategy "Cassure apres journee etroite" (Toby Crabel, "Day
Trading with Short Term Price Patterns and Opening Range Breakout", 1990:
after an NR7 day - the narrowest daily range of the last 7 - the next
session tends to trend; trade the breakout of the open by the "stretch"),
rules fixed on 2026-11-05 BEFORE running, at the user's request (second
intraday idea of the day, after the end-of-session momentum was rejected).
21st idea; from the literature, with Crabel's own definitions, nothing
tuned (no other NR length, stretch average, multiple or exit is tried).

Data: daily bars of the 10 cash indices in data/cache (same as
test_swing_rsi2.py): the cash session's open, high, low, close is the
trading day of a turbo. Sessions from 2012-01-01 to the last cached day.

Rule, for the session D following an NR7 day (D-1 range = High - Low is
the smallest of D-7 .. D-1):
  stretch S = average over the 10 sessions before D of
              min(High - Open, Open - Low)                       (Crabel)
  call      buy stop at Open(D) + S ; put sell stop at Open(D) - S
  stop      the opposite trigger (call: Open - S ; put: Open + S), so
            R = 2 S
  exit      close of session D (never held overnight)
  daily bars do not give the order of the moves: if the session reaches
  BOTH triggers, the trade is counted as the first trigger then stopped
  (-1R, conservative); a session that reaches one trigger only is the
  trade on that side, exit at the close (or the stop is impossible since
  the other trigger was not reached)
Costs round trip: 0.05 % (turbo spread, base) and 0.10 % of the price.

Random baseline: the same breakout rule on sessions NOT following an NR7
day, as many sessions per index as the real rule, 200 draws (seed 0):
measures whether the NR7 condition adds anything.

Decision rule (fixed before running): worth live tracking WITHOUT money
only if ALL of:
  - at least 300 trades;
  - pooled net R > 0 at 0.05 % AND at 0.10 %;
  - both halves (split 2019-01-01) > 0 at 0.05 %;
  - at least 7 of the 10 indices > 0 at 0.05 %;
  - pooled net R at 0.05 % above the 95th percentile of the random
    baseline.
Calls and puts are shown separately for information (one symmetric rule).
Otherwise REJETE, no re-tuning.

Usage: python scripts/test_intraday_nr7_orb.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache
from test_swing_rsi2 import INDICES

START, SPLIT = "2012-01-01", "2019-01-01"
COSTS = (0.0005, 0.0010)
N_RANDOM, MIN_TRADES, MIN_MARKETS = 200, 300, 7


def load(symbol):
    d = cache.load(symbol, "1D")
    d.index = pd.to_datetime(d.index, utc=True)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    rng = d.High - d.Low
    d["nr7"] = rng.shift(1) <= rng.shift(1).rolling(7).min()
    d["stretch"] = np.minimum(d.High - d.Open, d.Open - d.Low).rolling(10).mean().shift(1)
    return d


def trades(d, days):
    o, h, l, c, s = (d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "stretch"))
    rows = []
    for i in days:
        if not s[i] > 0:
            continue
        up, dn = o[i] + s[i], o[i] - s[i]
        hit_up, hit_dn = h[i] >= up, l[i] <= dn
        if not (hit_up or hit_dn):
            continue
        risk = 2 * s[i]
        if hit_up and hit_dn:
            side, move = (1 if c[i] >= o[i] else -1), -1.0
        elif hit_up:
            side, move = 1, (c[i] - up) / risk
        else:
            side, move = -1, (dn - c[i]) / risk
        rows.append({"day": d.index[i], "side": side, "move": move, "cost_frac": o[i] / risk})
    return pd.DataFrame(rows, columns=["day", "side", "move", "cost_frac"])


def net(t, cost):
    return t.move - cost * t.cost_frac if len(t) else pd.Series(dtype=float)


def main():
    rng = np.random.default_rng(0)
    allt, per, rand = [], {}, np.zeros(N_RANDOM)
    last = None
    for s, name in INDICES.items():
        d = load(s)
        last = d.index[-1] if last is None else min(last, d.index[-1])
        ok = d.stretch.notna().to_numpy() & (d.index >= START)
        nr7 = np.flatnonzero(ok & d.nr7.to_numpy())
        other = np.flatnonzero(ok & ~d.nr7.to_numpy())
        t = trades(d, nr7)
        r = net(t, COSTS[0])
        per[name] = r.sum()
        allt.append(t.assign(market=name))
        for k in range(N_RANDOM):
            rand[k] += net(trades(d, np.sort(rng.choice(other, len(nr7), replace=False))), COSTS[0]).sum()
        print(f"  {name:14s} {len(nr7):4d} seances NR7, {len(t):4d} trades, {(r > 0).mean():4.0%} gagnants, "
              f"net {r.sum():+7.1f}R")
    t = pd.concat(allt, ignore_index=True)
    r1, r2 = net(t, COSTS[0]), net(t, COSTS[1])
    h1, h2 = r1[t.day < SPLIT].sum(), r1[t.day >= SPLIT].sum()
    pos = sum(v > 0 for v in per.values())
    p95 = np.percentile(rand, 95)
    print(f"\nSeances {START} -> {last:%d/%m/%Y}")
    print(f"Total : {len(t)} trades, {(r1 > 0).mean():.0%} gagnants, net {r1.sum():+.1f}R a 0,05 % "
          f"({r1.mean():+.3f}R/trade), {r2.sum():+.1f}R a 0,10 %")
    for sd, lab in ((1, "calls"), (-1, "puts")):
        m = t.side == sd
        print(f"  {lab:6s} {m.sum():4d} trades, net {r1[m].sum():+.1f}R a 0,05 %")
    print(f"Moities (coupure {SPLIT[:4]}) : {h1:+.1f}R / {h2:+.1f}R | indices positifs {pos}/10 | "
          f"meme regle sans NR7 (hasard) 95e centile {p95:+.1f}R, mediane {np.median(rand):+.1f}R")
    ok = (len(t) >= MIN_TRADES and r1.sum() > 0 and r2.sum() > 0 and h1 > 0 and h2 > 0
          and pos >= MIN_MARKETS and r1.sum() > p95)
    print(f"\nRegle fixee avant : cassure apres journee etroite {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
