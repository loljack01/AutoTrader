"""TEST 2 of docs/tests_figes_2026-11-06.md (frozen on 2026-11-06 BEFORE
running, at the user's request): false break of the 20-day low (P1, chart
analysis expert), daily, 10 cash indices, calls.

Signal on day J: L20 = lowest low of sessions J-20 to J-1, set at least 4
sessions before J (its day <= J-4); Low(J) < L20; Close(J) > L20;
Close(J-1) > SMA200(J-1).
Entry at the close of J. Stop = Low(J) - 0.25 x ATR14(J) (EWM ATR, as the
swing). Exit at the first close > SMA5 after J, or at the close of the 10th
session; an open beyond the stop exits at the open. One position per index.
Book: P1 shares the 5 places of the RSI(2) swing; signals of the same close
by increasing RSI(2); if an index has both signals the same day, one trade
(the RSI(2) rule).

Immediate rejection if more than 50 % of the P1 signals fall on the same day
as an RSI(2) signal on the same index.
Development (2012-2021): at least 100 P1 trades alone; net > 0 at 0.10 %;
weekly-clustered t >= 2.24 at 0.05 %; at least 7 of the 10 indices positive
at 0.05 %; combined book (RSI(2) + P1, 5 places) >= RSI(2) alone + 1R per
year. Reserved period (2022 -> last day): net > 0 at 0.05 %, weekly t >= 1.65,
combined >= RSI(2) alone + 1R per year. Then 1991-2011 (files of
test_swing_rsi2_1990.py): t >= 1.65. Adopted only if all three pass.
Multiple-testing budget: 4 tests (tests 1-4), development threshold t >= 2.24.
Only descriptive count done before (205 signals, 30 % same day as RSI(2)).

Result (run on 2026-11-06, development 2012-2021): REJETE. 205 signals,
30 % the same day as RSI(2); P1 alone 205 trades, 54 % winners, +34.6R at
0.05 % (+0.169R/trade), +23.5R at 0.10 %, weekly t 1.66 (threshold 2.24),
6/10 indices positive (threshold 7); combined +7.09R/year vs +5.62R/year
(+1.47, threshold +1). Two criteria failed: not adopted, no re-tuning.
Reserved period not run.

Usage: python scripts/test_swing_p1_false_break.py dev|reserved
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import swing_portfolio as sp
import test_swing_rsi2 as sw

T_DEV, T_RES = 2.24, 1.65


def p1_signals(d):
    lo, c = d.Low.to_numpy(), d.Close.to_numpy()
    s200 = d.sma200.to_numpy()
    out = []
    for j in range(21, len(d)):
        w = lo[j - 20:j]
        k = int(np.argmin(w)) + j - 20
        l20 = lo[k]
        if k <= j - 4 and lo[j] < l20 and c[j] > l20 and c[j - 1] > s200[j - 1]:
            out.append(j)
    return np.array(out, dtype=int)


def exit_with_stop(a, i, stop):
    o, h, l, c, s5, _ = a
    last = min(i + sw.MAX_DAYS, len(c) - 1)
    for j in range(i + 1, last + 1):
        if l[j] <= stop:
            return j, (o[j] if o[j] <= stop else stop)
        if c[j] > s5[j]:
            return j, c[j]
    return (last, c[last]) if last == i + sw.MAX_DAYS else (None, None)


def p1_trades(sym, d, period):
    """All P1 candidates (closed) as (entry, exit, rsi2, sym, r005, r010)."""
    a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
    c, rsi = a[3], d.rsi2.to_numpy()
    lo, atr = a[2], a[5]
    a0, b0 = sp.ts(period[0]), sp.ts(period[1])
    out = []
    for i in p1_signals(d):
        if not (a0 <= d.index[i] < b0):
            continue
        stop = lo[i] - 0.25 * atr[i]
        risk = c[i] - stop
        if not risk > 0:
            continue
        j, px = exit_with_stop(a, i, stop)
        if j is None:
            continue
        move = (px - c[i]) / risk
        out.append((d.index[i].normalize(), d.index[j].normalize(), rsi[i], sym,
                    move - sw.COSTS[0] * c[i] / risk, move - sw.COSTS[1] * c[i] / risk))
    return out


def alone(trades):
    """One position per index, in time order (as test_swing_rsi2.run)."""
    rows, free = [], {}
    for t in sorted(trades, key=lambda x: x[0]):
        if free.get(t[3], t[0]) > t[0]:
            continue
        free[t[3]] = t[1]
        rows.append(t)
    return pd.DataFrame(rows, columns=["entry", "exit", "rsi2", "sym", "r", "r010"])


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    period = sp.DEV if which == "dev" else sp.RESERVED
    data = sp.load_all()
    print(f"Reference identique a test_swing_rsi2_cap5 : {'OK' if sp.check_reference(data) else 'DIFFERENT'}")
    a0, b0 = sp.ts(period[0]), sp.ts(period[1])
    n_sig = same = 0
    p1 = []
    for s, d in data.items():
        sig = p1_signals(d)
        sig = sig[(d.index[sig] >= a0) & (d.index[sig] < b0)]
        rs = (d.Close.to_numpy() > d.sma200.to_numpy()) & (d.rsi2.to_numpy() < 10)
        n_sig += len(sig)
        same += int(rs[sig].sum())
        p1 += p1_trades(s, d, period)
    share = same / n_sig if n_sig else 0
    print(f"Periode {which} : {n_sig} signaux P1, dont {share:.0%} le meme jour qu'un signal RSI(2) (rejet si > 50 %)")
    if share > 0.5:
        print("Regle fixee avant : P1 REJETE (doublon du RSI(2))")
        return
    t = alone(p1)
    tw = sp.tweek(t)
    per = t.groupby("sym").r.sum()
    pos = int((per > 0).sum())
    print(f"  P1 seul : {len(t)} trades, {(t.r > 0).mean():.0%} gagnants, net {t.r.sum():+.1f}R a 0,05 % "
          f"({t.r.mean():+.3f}R/trade), {t.r010.sum():+.1f}R a 0,10 %, t semaine {tw:+.2f}, indices positifs {pos}/10")
    for s, v in per.items():
        print(f"     {sw.INDICES[s]:14s} {v:+6.1f}R")
    rsi_c = sp.rsi2_candidates(data, period)
    keys = {(x[0], x[3]) for x in rsi_c}
    comb_c = rsi_c + [x[:5] for x in p1 if (x[0], x[3]) not in keys]
    ref, comb = sp.select_book(rsi_c, 5), sp.select_book(comb_c, 5)
    y0, y1 = sp.risk_stats(ref, period)[2], sp.risk_stats(comb, period)[2]
    print(f"  RSI(2) seul (5 places) : {len(ref)} trades {y0:+.2f}R/an | RSI(2) + P1 : {len(comb)} trades {y1:+.2f}R/an "
          f"(ecart {y1 - y0:+.2f}R/an, seuil +1R/an)")
    if which == "dev":
        ok = len(t) >= 100 and t.r010.sum() > 0 and tw >= T_DEV and pos >= 7 and y1 - y0 >= 1.0
    else:
        ok = t.r.sum() > 0 and tw >= T_RES and y1 - y0 >= 1.0
    print(f"Regle fixee avant ({which}) : P1 {'PASSE' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
