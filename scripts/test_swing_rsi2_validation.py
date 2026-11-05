"""Validation of the swing rule "Repli en tendance" (calls), rules fixed on
2026-11-05 BEFORE fetching any new data or running, at the user's request
("give it your all"). The rule passed on 10 indices (test_swing_rsi2.py);
this asks whether that was luck, in two independent ways. The frozen rule
itself is NOT changed by anything below, whatever the result.

A. OUT OF SAMPLE - 8 indices never used before (daily cash index bars from
   TradingView, fetched AFTER this file is committed, from 2011, signals
   2012-01-01 -> last day): EURONEXT:AEX, BME:IBC (IBEX 35), OMXSTO:OMXS30,
   TVC:NI225, HSI:HSI, ASX:XJO, TSX:TSX, EURONEXT:BEL20.
   Exactly the frozen rule (RSI(2) < 10 above SMA200, exit close > SMA5,
   stop 2.5 ATR, 10 days max). Passes only if ALL of:
     - at least 300 trades in total;
     - pooled net R > 0 at 0.05 % AND at 0.10 %;
     - at least 6 of the 8 indices with net R > 0 at 0.05 %;
     - mean net R per trade at 0.05 % >= +0.037R (half the original
       +0.074R).
   An index whose data cannot be fetched is reported and left out (the
   6-of-8 rule then becomes 75 % of the indices available, rounded up).

B. PLATEAU - on the original 10 indices, 27 neighbouring versions:
   RSI(2) threshold 5 / 10 / 15 x trend average 150 / 200 / 250 days x exit
   average 3 / 5 / 7 days (stop, time limit, costs unchanged). Passes only
   if at least 22 of the 27 (about 80 %) have pooled net R > 0 at 0.10 %.
   This only checks the result is not a lucky point; no version is chosen.

Verdict: CONFIRME if A and B pass; FRAGILE if only one passes; DOUTEUX if
neither (then the live tracking goes on, but no money even after its 50
trades without a new discussion).

Usage: python scripts/test_swing_rsi2_validation.py [tool-results JSON files
of the 8 new indices, 1D] (merged into data/cache first)
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import test_swing_rsi2 as sw
from data import cache
from other_markets_test import ingest

NEW = {"EURONEXT:AEX": "AEX", "BME:IBC": "IBEX 35", "OMXSTO:OMXS30": "OMX 30", "TVC:NI225": "Nikkei 225",
       "HSI:HSI": "Hang Seng", "ASX:XJO": "ASX 200", "TSX:TSX": "TSX", "EURONEXT:BEL20": "BEL 20"}
MIN_TRADES, MEAN_MIN, PLATEAU_MIN = 300, 0.037, 22


def load(symbol, trend=200, exit_n=5):
    d = sw.load(symbol)
    d["sma200"] = d.Close.rolling(trend).mean()
    d["sma5"] = d.Close.rolling(exit_n).mean()
    return d


def calls(d, thr=10):
    """Frozen run() with another RSI threshold (thr=10 is the frozen rule)."""
    if thr == 10:
        return sw.run(d, 1)
    c, rsi = d.Close.to_numpy(), d.rsi2.to_numpy()
    sig = (c > d.sma200.to_numpy()) & (rsi < thr) & (d.index >= sw.START)
    return sw.run(d, 1, np.flatnonzero(sig))


def main():
    for f in sys.argv[1:]:
        ingest(f)
    print("A. Hors echantillon (8 indices jamais utilises, regle figee inchangee)")
    tots, per, n = [], {}, 0
    for s, name in NEW.items():
        try:
            d = load(s)
        except Exception:
            d = None
        if d is None or len(d) < 400:
            print(f"  {name:12s} donnees indisponibles, ecarte")
            continue
        t = calls(d)
        r1, r2 = sw.net(t, sw.COSTS[0]), sw.net(t, sw.COSTS[1])
        per[name] = r1.sum()
        tots.append((r1, r2))
        print(f"  {name:12s} {d.index[0]:%Y} -> {d.index[-1]:%d/%m/%Y} : {len(t):4d} trades, "
              f"{(r1 > 0).mean():4.0%} gagnants, net {r1.sum():+6.1f}R a 0,05 %, {r2.sum():+6.1f}R a 0,10 %")
    r1 = pd.concat([a for a, _ in tots]) if tots else pd.Series(dtype=float)
    r2 = pd.concat([b for _, b in tots]) if tots else pd.Series(dtype=float)
    need = math.ceil(0.75 * len(per))
    pos = sum(v > 0 for v in per.values())
    okA = (len(r1) >= MIN_TRADES and r1.sum() > 0 and r2.sum() > 0 and pos >= need
           and len(r1) and r1.mean() >= MEAN_MIN)
    print(f"  Total : {len(r1)} trades, net {r1.sum():+.1f}R a 0,05 % ({r1.mean() if len(r1) else 0:+.3f}R/trade), "
          f"{r2.sum():+.1f}R a 0,10 % | indices positifs {pos}/{len(per)} (il en faut {need}) -> "
          f"{'PASSE' if okA else 'ECHOUE'}")

    print("\nB. Plateau (10 indices d'origine, 27 versions voisines, net a 0,10 %)")
    good, lines = 0, []
    for trend in (150, 200, 250):
        for exit_n in (3, 5, 7):
            data = {s: load(s, trend, exit_n) for s in sw.INDICES}
            row = []
            for thr in (5, 10, 15):
                tot = sum(sw.net(calls(d, thr), sw.COSTS[1]).sum() for d in data.values())
                good += tot > 0
                row.append(f"RSI<{thr:2d} {tot:+7.1f}R")
            lines.append(f"  SMA{trend} sortie SMA{exit_n} : " + " | ".join(row))
    print("\n".join(lines))
    okB = good >= PLATEAU_MIN
    print(f"  {good}/27 versions positives (il en faut {PLATEAU_MIN}) -> {'PASSE' if okB else 'ECHOUE'}")
    verdict = "CONFIRME" if okA and okB else "FRAGILE" if okA or okB else "DOUTEUX"
    print(f"\nRegle fixee avant : swing repli en tendance {verdict}")


if __name__ == "__main__":
    main()
