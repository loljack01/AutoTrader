"""Swing "Repli en tendance" (calls) with at most 5 open positions, the risk
cap recommended by the working group's statistician (5 000 EUR capital,
orders >= 500 EUR). Rules fixed on 2026-11-05 BEFORE running. Trade rule
unchanged (test_swing_rsi2.py); only the selection when more than 5
positions would be open: exits first, then signals of the same close by
lowest RSI(2), skip when 5 are open (one position per index), 10 indices.

Tested on BOTH periods: 1991-2011 (tool-result files given as arguments,
as test_swing_rsi2_1990.py) and 2012 -> last day (data/cache).

Decision (fixed before running): the cap is ADOPTED for real money only if,
in EACH period, the capped version keeps a mean net R per trade at 0.05 %
>= 80 % of the uncapped version's AND a weekly-clustered t >= 2.0.
Otherwise the cap is not used (positions are then sized down instead).

Result (run on 2026-11-05): ADOPTEE. 1991-2011: 1374 trades +77.8R
(+0.057R/trade, 86 % of the uncapped +0.066R, weekly t 2.42); 2012-2026:
1121 trades +70.2R (+0.063R/trade, 85 %, weekly t 2.25).

Usage: python scripts/test_swing_rsi2_cap5.py <1990-2011 tool-result files>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import test_swing_rsi2 as sw
from test_swing_rsi2_1990 import frame

CAP = 5


def candidates(sym, d, start, end):
    a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
    c, rsi = a[3], d.rsi2.to_numpy()
    sig = np.flatnonzero((c > d.sma200.to_numpy()) & (rsi < 10) & (d.index >= start) & (d.index < end))
    out = []
    for i in sig:
        j, px, risk = sw.exit_trade(a, i, 1)
        if j is None or not risk > 0:
            continue
        out.append((d.index[i].normalize(), d.index[j].normalize(), rsi[i], sym,
                    (px - c[i]) / risk - sw.COSTS[0] * c[i] / risk))
    return out


def select(cands, cap):
    cands = sorted(cands, key=lambda x: (x[0], x[2]))
    open_, taken, busy = [], [], {}
    for day, ex, _, sym, r in cands:
        open_ = [p for p in open_ if p[0] > day]
        if busy.get(sym, day) > day:  # one position per index (as the frozen rule)
            continue
        busy[sym] = ex
        if len(open_) >= cap:
            continue
        open_.append((ex, sym))
        taken.append((ex, r))
    return pd.DataFrame(taken, columns=["exit", "r"])


def tweek(t):
    w = t.groupby(t.exit.dt.to_period("W")).r.sum()
    return w.mean() / (w.std(ddof=1) / np.sqrt(len(w)))


def main():
    old = {}
    for f in sys.argv[1:]:
        sym, d = frame(f)
        old[sym] = d
    periods = {"1991-2011": ({s: old[s] for s in old}, "1991-01-01", "2012-01-01"),
               "2012-2026": ({s: sw.load(s) for s in sw.INDICES}, "2012-01-01", "2100-01-01")}
    ok = True
    for name, (data, a, b) in periods.items():
        cands = []
        for s, d in data.items():
            cands += candidates(s, d, pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC"))
        full, capped = select(cands, 99), select(cands, CAP)
        ratio = capped.r.mean() / full.r.mean()
        tw = tweek(capped)
        good = ratio >= 0.8 and tw >= 2.0
        ok &= good
        print(f"{name} : sans limite {len(full)} trades {full.r.sum():+.1f}R ({full.r.mean():+.3f}R/trade, t semaine "
              f"{tweek(full):+.2f}) | limite 5 positions {len(capped)} trades {capped.r.sum():+.1f}R "
              f"({capped.r.mean():+.3f}R/trade, {ratio:.0%} de la moyenne, t semaine {tw:+.2f}) -> {'OK' if good else 'NON'}")
    print(f"\nRegle fixee avant : limite de 5 positions {'ADOPTEE' if ok else 'NON ADOPTEE'}")


if __name__ == "__main__":
    main()
