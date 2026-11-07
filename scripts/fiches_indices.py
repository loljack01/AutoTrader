"""Practical sheet per index for the swing (07/11/2026, at the user's request).
Operational only: no rule is tested or changed (moratorium of 06/11).

For each of the 10 cash indices of the swing it prints, from data/cache:
  last close, SMA200 and trend, ATR(14), stop of the rule (2.5 ATR) in points
  and %, exposure for 25 EUR of risk, order = max(500 EUR, exposure / 2.85)
  and leverage, and, from the reference book (5 positions, 2012 -> last day,
  0.05 % cost, descriptive only): signals per year and R per trade.
Static notes (closing time, auction, holidays, products) are in
docs/fiches_indices.md.

Usage: python scripts/fiches_indices.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import swing_portfolio as sp
import test_swing_rsi2 as sw

RISK_EUR, MIN_ORDER, MAX_LEV = 25.0, 500.0, 2.85


def main():
    data = sp.load_all()
    book = sp.select_book(sp.rsi2_candidates(data, ("2012-01-01", "2100-01-01")), 5)
    years = (book.exit.max() - sp.ts("2012-01-01")).days / 365.25
    rows = []
    for s, name in sw.INDICES.items():
        d = data[s]
        c, atr, s200 = d.Close.iloc[-1], d.atr.iloc[-1], d.sma200.iloc[-1]
        stop = sw.STOP_ATR * atr
        expo = RISK_EUR * c / stop
        b = book[book.sym == s]
        rows.append({"indice": name, "date": f"{d.index[-1]:%d/%m}", "cloture": round(c, 2),
                     "tendance": "au-dessus SMA200" if c > s200 else "SOUS SMA200 (pas de call)",
                     "atr14": round(atr, 1), "stop_pts": round(stop, 1), "stop_pct": f"{stop / c:.1%}",
                     "expo_pour_25eur": round(expo),
                     "perte_stop_500eur_lev2_8": round(500 * 2.8 * stop / c),
                     "trades_par_an": round(len(b) / years, 1),
                     "r_par_trade": round(b.r.mean(), 3) if len(b) else np.nan})
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
    print(f"\nCarnet de reference : {len(book)} trades sur {years:.1f} ans ; choix du 07/11 : ordre de 500 EUR en turbo "
          f"call au levier le plus bas (~2,8) -> perte au stop = 500 x 2,8 x stop %.")


if __name__ == "__main__":
    main()
