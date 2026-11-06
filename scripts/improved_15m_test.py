"""Improved 15m version ("v2"), rules fixed on 2026-10-27 BEFORE running,
one answer to each of the five losing situations found in the 225 trades
of the frozen 15m rules on CAC, DAX, Euro Stoxx 50, S&P 500, Nasdaq:

  1+2 trend / calls: calls only if the previous daily close is above its
      20-day SMA; puts always allowed (index futures fall faster than they
      rise: a swept high fails more reliably than a swept low)
  3   hours: entries only when the entry bar closes 08:00-12:00 or
      15:30-18:00 Paris (European open, US open; nothing at lunch or in
      the thin evening)
  4   freshness: the CHoCH must come within 1h of the sweep (instead of 4h)
  5   payoff: minimum net R:R 2.0 (instead of 1.3)
Everything else is the frozen 15m rule set; stop margin and cost scaled to
each market's price level (median 15m close / 7900).

Those five points were FOUND on the five markets above, so results there
are in-sample and shown for information only. The decision uses five index
futures never looked at before: FTSE 100 (ICEEUR:Z1!), SMI (FSMI1!), Dow
Jones (YM1!), Russell 2000 (RTY1!), FTSE MIB (FIB1!).

Decision rule (fixed before running): v2 is kept as a NEW candidate,
tracked live next to the frozen versions (which do not change), only if
on the five new markets pooled:
  - its net R is > 0 at 1pt-equivalent AND at 3pt-equivalent cost, and
  - it beats the frozen 15m "none" version at both costs, and
  - its net R is > 0 on at least 3 of the 5 new markets at 1pt-eq.
Each point alone (added to the frozen rules) is shown for information.

Usage: python scripts/improved_15m_test.py [tool_result.json ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from other_markets_test import CAC_LEVEL, ingest, tstat, trend_up

IN_SAMPLE = {"FCE1!": "CAC 40", "FDAX1!": "DAX", "FESX1!": "Euro Stoxx 50", "ES1!": "S&P 500", "NQ1!": "Nasdaq 100"}
NEW = {"ICEEUR:Z1!": "FTSE 100", "FSMI1!": "SMI", "YM1!": "Dow Jones", "RTY1!": "Russell 2000", "FIB1!": "FTSE MIB"}
BAR = pd.Timedelta(minutes=15)
VERSIONS = {
    "frozen none": {},
    "frozen sma20": {"trend": "both"},
    "1+2 calls avec tendance": {"trend": "calls"},
    "3 horaires": {"hours": True},
    "4 fraicheur 1h": {"window": 1},
    "5 R:R mini 2": {"rr": 2.0},
    "v2 (les 5)": {"trend": "calls", "hours": True, "window": 1, "rr": 2.0},
}


def hours_mask(d):
    t = (d.index + BAR).tz_convert("Europe/Paris")
    h = t.hour + t.minute / 60
    return ((h >= 8) & (h <= 12)) | ((h >= 15.5) & (h <= 18))


def run(symbol, d, k, cost, opts):
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = opts.get("rr", 1.3)
    bt.CHOCH_WINDOW = pd.Timedelta(hours=opts.get("window", 4))
    n = len(d)
    buy, sell = np.ones(n, bool), np.ones(n, bool)
    if opts.get("trend"):
        up = trend_up(symbol, d)
        buy &= up
        if opts["trend"] == "both":
            sell &= ~up
    if opts.get("hours"):
        hm = np.asarray(hours_mask(d))
        buy &= hm
        sell &= hm
    t = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=buy),
                   bt.backtest(d, True, False, direction="sell", entry_mask=sell)], ignore_index=True)
    return t[t.result != "open"]


def evaluate(markets, now, title):
    print(f"\n==================== {title}")
    res = {(v, c): [] for v in VERSIONS for c in (1.0, 3.0)}
    for symbol, name in markets.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        k = float(d[d.index < "2026-10-27"].Close.median()) / CAC_LEVEL
        print(f"\n## {name} ({symbol}) {d.index[0].date()} -> {d.index[-1].date()}, facteur {k:.2f}")
        for v, opts in VERSIONS.items():
            line = []
            for cost in (1.0, 3.0):
                r = run(symbol, d, k, cost, opts).net_r.to_numpy()
                res[(v, cost)].append(r)
                line.append(f"{len(r):3d} trades {(r > 0).mean() if len(r) else 0:4.0%} {r.sum():+6.1f}R")
            print(f"  {v:26s} 1pt-eq: {line[0]} | 3pt-eq: {line[1]}")
    print(f"\n## {title} - tous ensemble")
    for v in VERSIONS:
        r1, r3 = np.concatenate(res[(v, 1.0)]), np.concatenate(res[(v, 3.0)])
        pos = sum(x.sum() > 0 for x in res[(v, 1.0)])
        print(f"  {v:26s} 1pt-eq: n={len(r1):3d} gagnants={(r1 > 0).mean():4.0%} net={r1.sum():+6.1f}R moy={r1.mean():+.3f}R "
              f"t={tstat(r1):+.2f} | 3pt-eq net={r3.sum():+6.1f}R | marches positifs {pos}/{len(markets)}")
    return res


def main():
    for f in sys.argv[1:]:
        ingest(f)
    now = pd.Timestamp.now(tz="UTC")
    evaluate(IN_SAMPLE, now, "5 marches ou les points ont ete trouves (info seulement)")
    res = evaluate(NEW, now, "5 NOUVEAUX marches (decision)")
    v1, v3 = np.concatenate(res[("v2 (les 5)", 1.0)]), np.concatenate(res[("v2 (les 5)", 3.0)])
    b1, b3 = np.concatenate(res[("frozen none", 1.0)]), np.concatenate(res[("frozen none", 3.0)])
    pos = sum(x.sum() > 0 for x in res[("v2 (les 5)", 1.0)])
    ok = v1.sum() > 0 and v3.sum() > 0 and v1.sum() > b1.sum() and v3.sum() > b3.sum() and pos >= 3
    print(f"\nRegle fixee avant: v2 {'RETENUE comme nouvelle candidate' if ok else 'NON RETENUE'} "
          f"(nouveaux marches: {v1.sum():+.1f}R a 1pt-eq, {v3.sum():+.1f}R a 3pt-eq, "
          f"base {b1.sum():+.1f}/{b3.sum():+.1f}R, marches positifs {pos}/5)")


if __name__ == "__main__":
    main()
