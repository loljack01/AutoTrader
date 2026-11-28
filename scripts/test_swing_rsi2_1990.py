"""OUT-OF-TIME test of the swing rule "Repli en tendance" (calls) on
1991-2011, a period never used, rules fixed on 2026-11-05 BEFORE fetching
the data, at the suggestion of the working group's statistician: the 8
"unseen" indices were mostly the same weeks as the original ones
(weekly results correlated 0.74), so only another PERIOD is a real
out-of-sample test. The frozen rule is applied unchanged.

Data: daily bars of the same 10 cash indices from TradingView,
1990-01-01 -> 2011-12-31, read from the tool-result files given as
arguments (NOT written to data/cache, so the frozen scripts' references
do not move). Signals from 1991-01-01 (one year of warm-up) to 2011-12-31;
a trade still open on 2011-12-31 is dropped.

Rule: exactly test_swing_rsi2.py (RSI(2) < 10 and close > SMA200 -> call at
the close; exit first close > SMA5; stop 2.5 ATR(14); 10 days max; one
position per index). Costs 0.05 % and 0.10 %.

Statistics are clustered by WEEK (trades of all indices exiting in the
same week are summed) because the indices buy the same dips.

Decision (fixed before running): CONFIRME EN DEHORS DE LA PERIODE only if
ALL of: weekly-clustered t-stat of net R at 0.05 % >= 2.0; net R > 0 at
0.05 % AND 0.10 %; at least 7 of the indices with data > 0 at 0.05 %;
mean net R per trade at 0.05 % >= +0.037R. Otherwise NON CONFIRME (the
live tracking goes on but the swing's evidence is downgraded).

Result (run on 2026-11-05): CONFIRME EN DEHORS DE LA PERIODE. 1991-2011:
1613 trades, 68 % winners, net +106.5R at 0.05 % (+0.066R/trade), +76.8R at
0.10 %; 502 weeks, weekly-clustered t = +2.72; 8/10 indices positive
(Russell 2000 -7.6R, FTSE MIB -4.9R); every sub-period positive: 1991-97
+49.9R, 1998-2004 +29.3R, 2005-11 +27.3R. Same edge per trade as
2012-2026 (+0.074R).

Usage: python scripts/test_swing_rsi2_1990.py <tool-result JSON files, 1D>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import test_swing_rsi2 as sw

START, END = "1991-01-01", "2012-01-01"


def frame(path):
    j = json.load(open(path))
    b = j["bars"]
    if isinstance(b, list):
        b = {k: [x[k] for x in b] for k in ("t", "o", "h", "l", "c")}
    d = pd.DataFrame({"Open": b["o"], "High": b["h"], "Low": b["l"], "Close": b["c"]},
                     index=pd.to_datetime(b["t"], unit="s", utc=True))
    d = d[~d.index.duplicated(keep="last")].sort_index()
    c = d.Close
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    d["rsi2"] = 100 - 100 / (1 + up / dn)
    d["sma200"] = c.rolling(200).mean()
    d["sma5"] = c.rolling(5).mean()
    tr = pd.concat([d.High - d.Low, (d.High - c.shift()).abs(), (d.Low - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return j["symbol"], d[d.index < END]


def main():
    rows, per = [], {}
    for f in sys.argv[1:]:
        sym, d = frame(f)
        name = sw.INDICES.get(sym, sym)
        c, rsi = d.Close.to_numpy(), d.rsi2.to_numpy()
        sig = np.flatnonzero((c > d.sma200.to_numpy()) & (rsi < 10) & (d.index >= START))
        t = sw.run(d, 1, sig)
        r1 = sw.net(t, sw.COSTS[0])
        per[name] = r1.sum()
        rows.append(t.assign(market=name, r1=r1, r2=sw.net(t, sw.COSTS[1])))
        print(f"  {name:14s} {d.index[0]:%Y} -> {d.index[-1]:%Y} : {len(t):4d} trades, {(r1 > 0).mean():4.0%} gagnants, "
              f"net {r1.sum():+6.1f}R a 0,05 %")
    t = pd.concat(rows, ignore_index=True)
    wk = t.groupby(t.exit.dt.to_period("W")).r1.sum()
    tw = wk.mean() / (wk.std(ddof=1) / np.sqrt(len(wk)))
    pos = sum(v > 0 for v in per.values())
    print(f"\nTotal {START[:4]}-2011 : {len(t)} trades, {(t.r1 > 0).mean():.0%} gagnants, net {t.r1.sum():+.1f}R a 0,05 % "
          f"({t.r1.mean():+.3f}R/trade), {t.r2.sum():+.1f}R a 0,10 % | {len(wk)} semaines, t par semaine {tw:+.2f} | "
          f"indices positifs {pos}/{len(per)}")
    for a, b in (("1991", "1998"), ("1998", "2005"), ("2005", "2012")):
        m = (t.entry >= a) & (t.entry < b)
        print(f"  {a}-{int(b) - 1} : {m.sum()} trades, net {t.r1[m].sum():+.1f}R")
    ok = tw >= 2.0 and t.r1.sum() > 0 and t.r2.sum() > 0 and pos >= 7 and t.r1.mean() >= 0.037
    print(f"\nRegle fixee avant : swing repli en tendance {'CONFIRME EN DEHORS DE LA PERIODE' if ok else 'NON CONFIRME'}")


if __name__ == "__main__":
    main()
