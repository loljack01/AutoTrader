"""Swing "Repli en tendance" (calls) adapted to the user's account: 1000 EUR
capital, orders of at least 500 EUR (no brokerage fee from 500 EUR), so at
most 2 positions at a time. Rules fixed on 2026-11-05 BEFORE running, at
the user's request. The trade rule itself is the frozen one of
test_swing_rsi2.py (RSI(2) < 10 above SMA200, exit close > SMA5, stop 2.5
ATR, 10 days); only WHICH signals are taken changes:

  universe  the 6 indices with common turbos/ETFs at the user's broker:
            CAC 40, DAX, Euro Stoxx 50, S&P 500, Nasdaq 100, Dow Jones
  capacity  at most 2 open positions, one per index; exits are processed
            first (a position closed at a close frees its slot for a signal
            at that same close)
  priority  when several signals compete for the free slots on a close,
            lowest RSI(2) first; signals that find no slot are skipped
R and costs as test_swing_rsi2.py (0.05 % and 0.10 %).

Random baseline: same capacity rule, but each index's signal days replaced
by as many random closes of that index where the trend holds (no RSI
condition), random priority; 200 draws (seed 0).

Decision (reserved-period method):
  development 2012-2021, ALL of: at least 300 trades; net R > 0 at 0.05 %
    and 0.10 %; mean net R per trade at 0.05 % >= +0.037R; net R at 0.05 %
    above the 95th percentile of the random baseline;
  confirmation 2022 -> last day: net R > 0 at 0.05 % and above the random
    median.
  A SUIVRE EN REEL SANS ARGENT (as the account-sized version) only if both
  pass; otherwise REJETE, no re-tuning (no other capacity, priority or list).

Usage: python scripts/test_swing_rsi2_2pos.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import test_swing_rsi2 as sw

SIX = ["EURONEXT:PX1", "XETR:DAX", "TVC:SX5E", "SP:SPX", "NASDAQ:NDX", "TVC:DJI"]
CAP, N_RANDOM = 2, 200
PERIODS = (("DEVELOPPEMENT 2012-2021", "2012-01-01", "2022-01-01"),
           ("CONFIRMATION 2022 -> fin (periode reservee)", "2022-01-01", "2100-01-01"))


def candidates(symbol, d, entries, prio):
    """One candidate trade per entry bar (no overlap rule yet)."""
    a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
    out = []
    for i in entries:
        j, px, risk = sw.exit_trade(a, i, 1)
        if j is None or not risk > 0:
            continue
        c = a[3][i]
        out.append((d.index[i].normalize(), d.index[j].normalize(), prio[i], symbol, (px - c) / risk, c / risk))
    return out


def simulate(cands, a, b):
    cands = sorted((x for x in cands if a <= x[0] < pd.Timestamp(b, tz="UTC")), key=lambda x: (x[0], x[2]))
    open_, taken = [], []
    for day, exit_day, _, sym, move, frac in cands:
        open_ = [p for p in open_ if p[0] > day]
        if len(open_) >= CAP or any(p[1] == sym for p in open_):
            continue
        open_.append((exit_day, sym))
        taken.append((move, frac))
    t = np.array(taken) if taken else np.zeros((0, 2))
    return t[:, 0] - sw.COSTS[0] * t[:, 1], t[:, 0] - sw.COSTS[1] * t[:, 1]


def main():
    rng = np.random.default_rng(0)
    data = {s: sw.load(s) for s in SIX}
    real, pools = [], {}
    for s, d in data.items():
        c, rsi = d.Close.to_numpy(), d.rsi2.to_numpy()
        trend = (c > d.sma200.to_numpy()) & (d.index >= sw.START)
        sig = np.flatnonzero(trend & (rsi < 10))
        real += candidates(s, d, sig, rsi)
        pools[s] = (np.flatnonzero(trend), len(sig))
    rand_c = []
    for k in range(N_RANDOM):
        cs = []
        for s, d in data.items():
            pool, n = pools[s]
            pick = np.sort(rng.choice(pool, n, replace=False))
            cs += candidates(s, d, pick, rng.random(len(d)))
        rand_c.append(cs)
    ok = {}
    for label, a, b in PERIODS:
        a = pd.Timestamp(a, tz="UTC")
        r1, r2 = simulate(real, a, b)
        rnd = np.array([simulate(cs, a, b)[0].sum() for cs in rand_c])
        p50, p95 = np.median(rnd), np.percentile(rnd, 95)
        years = (min(pd.Timestamp(b, tz="UTC"), max(d.index[-1] for d in data.values())) - a).days / 365.25
        print(f"\n=== {label}")
        print(f"  {len(r1)} trades ({len(r1) / years:.0f}/an), {(r1 > 0).mean():.0%} gagnants, net {r1.sum():+.1f}R a 0,05 % "
              f"({r1.mean():+.3f}R/trade), {r2.sum():+.1f}R a 0,10 % | hasard mediane {p50:+.1f}R, 95e centile {p95:+.1f}R")
        if label.startswith("DEV"):
            ok["dev"] = len(r1) >= 300 and r1.sum() > 0 and r2.sum() > 0 and r1.mean() >= 0.037 and r1.sum() > p95
            print(f"  Developpement : {'PASSE' if ok['dev'] else 'ECHOUE'}")
        else:
            ok["conf"] = r1.sum() > 0 and r1.sum() > p50
            print(f"  Confirmation : {'PASSE' if ok['conf'] else 'ECHOUE'}")
            eq = np.cumsum(r1)
            print(f"  En euros (10 EUR de risque) : {r1.sum() * 10:+.0f} EUR, pire baisse {(eq - np.maximum.accumulate(eq)).min() * 10:+.0f} EUR")
    print(f"\nRegle fixee avant : swing 2 positions (compte 1000 EUR) "
          f"{'A SUIVRE EN REEL SANS ARGENT' if ok['dev'] and ok['conf'] else 'REJETE'}")


if __name__ == "__main__":
    main()
