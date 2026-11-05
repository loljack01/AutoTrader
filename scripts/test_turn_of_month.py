"""SWING / calendar strategy "Fin de mois" (turn-of-the-month effect:
Lakonishok & Smidt 1988, McConnell & Xu 2008 - equity index returns are
concentrated from the last trading day of a month to the third trading day
of the next, in most countries), rules fixed on 2026-11-05 BEFORE running,
at the user's request ("you can do much better"). 22nd idea. Chosen
because it is one of the most replicated effects across countries AND fits
the user's constraints (one 4-day trade a month: one order of >= 500 EUR at
a time). Standard window from the literature, nothing tuned.

NEW METHOD (first use): a reserved period. The decision uses 2012-2021
only; 2022 -> last day is looked at once, afterwards, as a confirmation.

Data: daily bars of the 18 cash indices in data/cache (the 10 of the main
strategy + the 8 of test_swing_rsi2_validation.py).

Rule (calls only), per index and per month:
  entry  close of the trading day BEFORE the last trading day of the month
  exit   close of the 3rd trading day of the next month (4 days held)
  stop   2.5 x ATR(14) daily under the entry (as the swing rule; an open
         beyond the stop exits at the open)
R = the stop distance. Costs round trip 0.05 % and 0.10 % of the price.

Baseline: the same 4-day trade (same stop) entered on random closes of the
same index that are NOT turn-of-month entries, as many as the real trades
in the period, 1000 draws (seed 0), pooled net R at 0.05 %.

Decision rule (fixed before running):
  development 2012-2021, ALL of: at least 1000 trades; pooled net R > 0 at
    0.05 % and 0.10 %; at least 14 of the 18 indices > 0 at 0.05 %; pooled
    net R at 0.05 % above the 95th percentile of the random baseline;
  confirmation 2022 -> last day, ALL of: pooled net R > 0 at 0.05 %; at
    least 9 of the 18 indices > 0; pooled net R above the MEDIAN of its
    random baseline.
  A SUIVRE EN REEL SANS ARGENT only if both pass; otherwise REJETE, no
  re-tuning (no other window, stop or market list).

Usage: python scripts/test_turn_of_month.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import test_swing_rsi2 as sw
from test_swing_rsi2_validation import NEW

INDICES = {**sw.INDICES, **NEW}
DEV, CONF_START, START = ("2012-01-01", "2022-01-01"), "2022-01-01", "2012-01-01"
COSTS, STOP_ATR, HOLD, N_RANDOM = (0.0005, 0.0010), 2.5, 4, 1000


def all_trades(d):
    """4-day trade result (move in R, cost fraction) for an entry at every close."""
    o, h, l, c, atr = (d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "atr"))
    n = len(d)
    move, frac = np.full(n, np.nan), np.full(n, np.nan)
    for i in range(n - HOLD):
        risk = STOP_ATR * atr[i]
        if not risk > 0:
            continue
        stop, px = c[i] - risk, c[i + HOLD]
        for j in range(i + 1, i + HOLD + 1):
            if l[j] <= stop:
                px = o[j] if o[j] <= stop else stop
                break
        move[i], frac[i] = (px - c[i]) / risk, c[i] / risk
    return move, frac


TZ = {"ASX:XJO": "Australia/Sydney", "TVC:NI225": "Asia/Tokyo", "HSI:HSI": "Asia/Hong_Kong",
      "SP:SPX": "America/New_York", "NASDAQ:NDX": "America/New_York", "TVC:DJI": "America/New_York",
      "TVC:RUT": "America/New_York", "TSX:TSX": "America/Toronto"}


def tom_entries(d, symbol):
    """Entry bars: the day before the last trading day of each month (local exchange calendar)."""
    m = np.asarray(d.index.tz_convert(TZ.get(symbol, "Europe/Paris")).strftime("%Y-%m"))
    last = np.flatnonzero(m[:-1] != m[1:])  # last trading day of each month
    return last - 1


def main():
    rng = np.random.default_rng(0)
    res = {}
    for s, name in INDICES.items():
        d = sw.load(s)
        move, frac = all_trades(d)
        e = tom_entries(d, s)
        e = e[(e >= 0) & ~np.isnan(move[e])]
        res[name] = (d.index, move, frac, e)
    for label, (a, b) in (("DEVELOPPEMENT 2012-2021", DEV), ("CONFIRMATION 2022 -> fin (periode reservee)", (CONF_START, "2100"))):
        print(f"\n=== {label}")
        tot1, tot2, n, pos, rand = 0.0, 0.0, 0, 0, np.zeros(N_RANDOM)
        for name, (idx, move, frac, e) in res.items():
            inp = (idx >= a) & (idx < b)
            ee = e[inp[e]]
            r1 = move[ee] - COSTS[0] * frac[ee]
            r2 = move[ee] - COSTS[1] * frac[ee]
            other = np.setdiff1d(np.flatnonzero(inp & ~np.isnan(move)), e)
            if len(ee) and len(other):
                pick = rng.choice(other, size=(N_RANDOM, len(ee)), replace=True)
                rand += (move[pick] - COSTS[0] * frac[pick]).sum(axis=1)
            tot1, tot2, n, pos = tot1 + r1.sum(), tot2 + r2.sum(), n + len(ee), pos + (r1.sum() > 0)
            print(f"  {name:14s} {len(ee):4d} trades, {(r1 > 0).mean() if len(r1) else 0:4.0%} gagnants, "
                  f"net {r1.sum():+6.1f}R a 0,05 %")
        p50, p95 = np.median(rand), np.percentile(rand, 95)
        print(f"  Total : {n} trades, net {tot1:+.1f}R a 0,05 % ({tot1 / max(n, 1):+.3f}R/trade), {tot2:+.1f}R a 0,10 % | "
              f"indices positifs {pos}/18 | hasard (4 jours ordinaires) mediane {p50:+.1f}R, 95e centile {p95:+.1f}R")
        if a == DEV[0]:
            ok_dev = n >= 1000 and tot1 > 0 and tot2 > 0 and pos >= 14 and tot1 > p95
            print(f"  Developpement : {'PASSE' if ok_dev else 'ECHOUE'}")
        else:
            ok_conf = tot1 > 0 and pos >= 9 and tot1 > p50
            print(f"  Confirmation : {'PASSE' if ok_conf else 'ECHOUE'}")
    ok = ok_dev and ok_conf
    print(f"\nRegle fixee avant : fin de mois {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
