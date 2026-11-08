"""TEST 6 of docs/test_6_rsi20_fige_2026-11-08.md (frozen on 2026-11-08 BEFORE
running, at the user's request: "Oui, fige le test 6"; moratorium of 06/11 lifted
by the user for tests 5 and 6 only).

Rule (the ONLY change to the reference swing): RSI(2) < 20 instead of
RSI(2) < 10 for the entry. Everything else identical: close > SMA200, entry at
the close, exit at the first later close > SMA5 or the 10th day, stop 2.5
ATR(14), 10 cash indices, one position per index, 5 positions at most, exits
first then signals of the same close by increasing RSI(2), cost 0.05 %.

Reference = the live rule (threshold 10). Measured exactly as test 5
(scripts/test_swing_rsi15.py, same functions): R per year, worst drawdown in R,
worst 3-month result in R, and the ADDED trades (in the threshold-20 book,
absent from the threshold-10 book, same index and same entry day): their number
and their weekly t-statistic.

Decision: ADOPTED only if, on the development period (2012-2021) THEN on the
reserved period (2022 -> last day), ALL of these hold:
  (a) R per year of the threshold-20 book >= 120 % of the reference's;
  (b) worst drawdown (in R) no deeper than 125 % of the reference's;
  (c) at least 150 added trades over the development period (at least 60 over
      the reserved period);
  (d) the weekly t-statistic of the added trades is >= 2.39 on the development
      period (Bonferroni 5 % / 6 tests, one-sided) THEN >= 1.65 on the
      reserved period.
Otherwise NOT ADOPTED, no re-tuning (no other threshold is tried). The reserved
period is run once, only after the development verdict.
Multiple-testing budget: 6 tests (tests 1-6 of 2026). This test was suggested
AFTER seeing the development result of test 5 (threshold 15: 117 % of the
reference R per year, t = 2.06), so it is not independent of it: hence the
stricter conditions (c) and (d) than for test 5.

Result: not run yet.

Usage: python scripts/test_swing_rsi20.py dev|reserved
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import swing_portfolio as sp
import test_swing_rsi15 as t5

THR_REF, THR_NEW = 10, 20
MIN_ADDED_DEV, MIN_ADDED_RES = 150, 60
T_DEV, T_RES = 2.39, 1.65


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    period = sp.DEV if which == "dev" else sp.RESERVED
    data = sp.load_all()
    ref_all = sp.select_book(sp.rsi2_candidates(data, ("2012-01-01", "2100-01-01")), 5)
    chk = t5.book(data, ("2012-01-01", "2100-01-01"), THR_REF)
    ok = len(ref_all) == len(chk) and abs(ref_all.r.sum() - chk.r.sum()) < 1e-9
    print(f"Reference seuil {THR_REF} identique a swing_portfolio : {'OK' if ok else 'DIFFERENT'}")
    if not ok:
        return
    ref, new = t5.book(data, period, THR_REF), t5.book(data, period, THR_NEW)
    key = lambda t: set(zip(t.sym, t.entry))
    added = new[[k not in key(ref) for k in zip(new.sym, new.entry)]]
    dd0, w0, ry0 = sp.risk_stats(ref, period)
    dd1, w1, ry1 = sp.risk_stats(new, period)
    na, ta = len(added), t5.weekly_t(added)
    print(f"Periode {which} : seuil {THR_REF} : {len(ref)} trades, {ry0:+.2f}R/an, pire baisse {dd0:+.1f}R, pire 3 mois {w0:+.1f}R")
    print(f"               seuil {THR_NEW} : {len(new)} trades, {ry1:+.2f}R/an, pire baisse {dd1:+.1f}R, pire 3 mois {w1:+.1f}R")
    print(f"  trades ajoutes : {na}, net {added.r.sum():+.1f}R ({added.r.mean() if na else 0:+.3f}R/trade), t hebdomadaire {ta:+.2f}")
    a_ok = ry1 >= 1.2 * ry0
    b_ok = dd1 >= 1.25 * dd0
    c_ok = na >= (MIN_ADDED_DEV if which == "dev" else MIN_ADDED_RES)
    d_ok = ta >= (T_DEV if which == "dev" else T_RES)
    print(f"  (a) R/an >= 120 % : {a_ok} | (b) baisse <= 125 % : {b_ok} | (c) trades ajoutes suffisants : {c_ok} | (d) t : {d_ok}")
    print(f"Regle fixee avant ({which}) : {'PASSE' if all((a_ok, b_ok, c_ok, d_ok)) else 'NON ADOPTEE'}")


if __name__ == "__main__":
    main()
