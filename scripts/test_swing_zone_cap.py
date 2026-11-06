"""TEST 1 of docs/tests_figes_2026-11-06.md (frozen on 2026-11-06 BEFORE
running, at the user's request): zone limit on the swing (R3).

Rule: at most 5 positions, of which at most 2 in the euro zone (CAC 40, DAX,
Euro Stoxx 50, FTSE MIB), 2 in the United States (S&P 500, Nasdaq 100, Dow
Jones, Russell 2000) and 1 other (FTSE 100, SMI). Exits first, then signals
of the same close by increasing RSI(2); a signal finding its zone or the book
full is skipped. Trade rule unchanged (test_swing_rsi2.py).

Measured against the reference swing capped at 5 positions
(test_swing_rsi2_cap5.py): worst drawdown in R (cumulative in exit order),
worst 3-month result in R, R per year, at 0.05 %.

Decision: ADOPTED only if, on the development period (2012-2021) THEN on the
reserved period (2022 -> last day): worst drawdown reduced by at least 20 %
AND R per year >= 90 % of the reference. Otherwise NOT ADOPTED. The reserved
period is run once, only after the development verdict.
Multiple-testing budget: 4 tests (tests 1-4).

Result (run on 2026-11-06, development 2012-2021): NON ADOPTE. Reference
757 trades +56.1R (+5.62R/year, worst drawdown -31.3R, worst 3 months -13.0R);
zone limit 637 trades +43.9R (+4.41R/year, -24.9R, -9.3R): drawdown reduced by
20 % but only 78 % of the R per year (threshold 90 %). Reserved period not run.

Usage: python scripts/test_swing_zone_cap.py dev|reserved
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import swing_portfolio as sp


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    period = sp.DEV if which == "dev" else sp.RESERVED
    data = sp.load_all()
    print(f"Reference identique a test_swing_rsi2_cap5 : {'OK' if sp.check_reference(data) else 'DIFFERENT'}")
    cands = sp.rsi2_candidates(data, period)
    ref, zone = sp.select_book(cands, 5), sp.select_book(cands, 5, sp.ZONE_CAPS)
    (d0, w0, y0), (d1, w1, y1) = sp.risk_stats(ref, period), sp.risk_stats(zone, period)
    print(f"Periode {which} {period[0]} -> {min(period[1], str(ref.exit.max().date()))}")
    print(f"  reference 5 positions : {len(ref)} trades, {ref.r.sum():+.1f}R, {y0:+.2f}R/an, pire baisse {d0:+.1f}R, "
          f"pire 3 mois {w0:+.1f}R")
    print(f"  limite par zone       : {len(zone)} trades, {zone.r.sum():+.1f}R, {y1:+.2f}R/an, pire baisse {d1:+.1f}R, "
          f"pire 3 mois {w1:+.1f}R")
    red = 1 - d1 / d0 if d0 < 0 else 0.0
    ok = red >= 0.20 and y1 >= 0.90 * y0
    print(f"  baisse reduite de {red:.0%} (seuil 20 %), R/an {y1 / y0:.0%} de la reference (seuil 90 %) -> "
          f"{'PASSE' if ok else 'NON ADOPTE'} sur la periode {which}")


if __name__ == "__main__":
    main()
