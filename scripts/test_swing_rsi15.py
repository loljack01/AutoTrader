"""TEST 5 of docs/test_5_rsi15_fige_2026-11-08.md (frozen on 2026-11-08 BEFORE
running, at the user's request, Sunday decision): more swing signals through a
looser entry threshold. Run on 2026-11-08 at the user's explicit request ("Fais le test"), which lifted
the moratorium of 06/11 (rule 12 of docs/regles_execution.md) for this test only.

Rule (the ONLY change to the reference swing): RSI(2) < 15 instead of
RSI(2) < 10 for the entry. Everything else identical: close > SMA200, entry at
the close, exit at the first later close > SMA5 or the 10th day, stop 2.5
ATR(14), 10 cash indices, one position per index, 5 positions at most, exits
first then signals of the same close by increasing RSI(2), cost 0.05 %.

Measured on the 5-position book (swing_portfolio.select_book), threshold 15
against the reference threshold 10: R per year, worst drawdown in R (cumulative
in exit order), worst 3-month result in R; and the ADDED trades (trades of the
threshold-15 book absent from the threshold-10 book, same index and same entry
day): their number and their weekly t-statistic (trades of all indices that
exit the same week are added, as in the tests of 06/11).

Decision: ADOPTED only if, on the development period (2012-2021) THEN on the
reserved period (2022 -> last day), ALL of these hold:
  (a) R per year of the threshold-15 book >= 120 % of the reference's;
  (b) worst drawdown (in R) of the threshold-15 book no deeper than 125 % of
      the reference's;
  (c) at least 100 added trades over the development period (at least 40 over
      the reserved period);
  (d) the weekly t-statistic of the added trades is >= 2.33 on the development
      period (Bonferroni 5 % / 5 tests, one-sided) THEN >= 1.65 on the
      reserved period.
Otherwise NOT ADOPTED, no re-tuning (no other threshold is tried). The reserved
period is run once, only after the development verdict.
Multiple-testing budget: 5 tests (tests 1-5 of 2026).

Result (run on 2026-11-08, development 2012-2021): NON ADOPTE. Reference threshold 10:
757 trades, +5.62R/year, worst drawdown -31.3R, worst 3 months -13.0R; threshold 15:
1032 trades, +6.56R/year (117 % of the reference, 120 % required), worst drawdown
-36.9R (118 %, OK), worst 3 months -13.2R; 507 added trades, +34.7R (+0.068R/trade),
weekly t = +2.06 (2.33 required). Conditions (a) and (d) fail. Reserved period not run.

Usage: python scripts/test_swing_rsi15.py dev|reserved
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import swing_portfolio as sp
import test_swing_rsi2 as sw

THR_REF, THR_NEW = 10, 15
MIN_ADDED_DEV, MIN_ADDED_RES = 100, 40
T_DEV, T_RES = 2.33, 1.65


def candidates_thr(sym, d, start, end, thr):
    """Same as test_swing_rsi2_cap5.candidates with a configurable RSI(2) threshold."""
    a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
    c, rsi = a[3], d.rsi2.to_numpy()
    sig = np.flatnonzero((c > d.sma200.to_numpy()) & (rsi < thr) & (d.index >= start) & (d.index < end))
    out = []
    for i in sig:
        j, px, risk = sw.exit_trade(a, i, 1)
        if j is None or not risk > 0:
            continue
        out.append((d.index[i].normalize(), d.index[j].normalize(), rsi[i], sym,
                    (px - c[i]) / risk - sw.COSTS[0] * c[i] / risk))
    return out


def book(data, period, thr):
    cands = []
    for s, d in data.items():
        cands += candidates_thr(s, d, sp.ts(period[0]), sp.ts(period[1]), thr)
    return sp.select_book(cands, 5)


def weekly_t(t):
    w = t.groupby(t.exit.dt.tz_localize(None).dt.to_period("W")).r.sum()
    return w.mean() / (w.std(ddof=1) / np.sqrt(len(w))) if len(w) > 2 else float("nan")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    period = sp.DEV if which == "dev" else sp.RESERVED
    data = sp.load_all()
    ref_all = sp.select_book(sp.rsi2_candidates(data, ("2012-01-01", "2100-01-01")), 5)
    chk = book(data, ("2012-01-01", "2100-01-01"), THR_REF)
    ok = len(ref_all) == len(chk) and abs(ref_all.r.sum() - chk.r.sum()) < 1e-9
    print(f"Reference seuil {THR_REF} identique a swing_portfolio : {'OK' if ok else 'DIFFERENT'}")
    if not ok:
        return
    ref, new = book(data, period, THR_REF), book(data, period, THR_NEW)
    key = lambda t: set(zip(t.sym, t.entry))
    added = new[[k not in key(ref) for k in zip(new.sym, new.entry)]]
    dd0, w0, ry0 = sp.risk_stats(ref, period)
    dd1, w1, ry1 = sp.risk_stats(new, period)
    na, ta = len(added), weekly_t(added)
    print(f"Periode {which} : seuil {THR_REF} : {len(ref)} trades, {ry0:+.2f}R/an, pire baisse {dd0:+.1f}R, pire 3 mois {w0:+.1f}R")
    print(f"               seuil {THR_NEW} : {len(new)} trades, {ry1:+.2f}R/an, pire baisse {dd1:+.1f}R, pire 3 mois {w1:+.1f}R")
    print(f"  trades ajoutes : {na}, net {added.r.sum():+.1f}R ({added.r.mean() if na else 0:+.3f}R/trade), t hebdomadaire {ta:+.2f}")
    a_ok = ry1 >= 1.2 * ry0
    b_ok = dd1 >= 1.25 * dd0  # drawdowns are negative: no deeper than 125 % of the reference
    c_ok = na >= (MIN_ADDED_DEV if which == "dev" else MIN_ADDED_RES)
    d_ok = ta >= (T_DEV if which == "dev" else T_RES)
    print(f"  (a) R/an >= 120 % : {a_ok} | (b) baisse <= 125 % : {b_ok} | (c) trades ajoutes suffisants : {c_ok} | (d) t : {d_ok}")
    print(f"Regle fixee avant ({which}) : {'PASSE' if all((a_ok, b_ok, c_ok, d_ok)) else 'NON ADOPTEE'}")


if __name__ == "__main__":
    main()
