"""Full simulation of the swing with the user's sizing of 07/11/2026 (descriptive,
no rule tested or changed, moratorium of 06/11): every order is 500 EUR in the
call turbo of leverage 2.8 (lowest at Boursomarkets), i.e. a constant exposure
of 1 400 EUR; result of a trade = 1 400 EUR x index move (entry to exit, model
exit incl. stops and gaps) - 0.05 % cost, i.e. r x stop % x 1 400.
Reference book: 5 positions, 10 indices, 2012 -> last day of data/cache.
Also: the user's total stop of -500 EUR (07/11), checked from every possible
start month; tax at the 2026 flat rate (31.4 %) on positive years.

Usage: python scripts/simulation_500eur.py
"""

import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import swing_portfolio as sp
import test_swing_rsi2 as sw

ORDER, LEV, STOP_TOTAL, TAX = 500.0, 2.8, -500.0, 0.314


def main():
    data = sp.load_all()
    book = sp.select_book(sp.rsi2_candidates(data, ("2012-01-01", "2100-01-01")), 5)
    pct = []
    for x in book.itertuples():
        d = data[x.sym]
        k = np.flatnonzero(d.index.normalize() == x.entry)[0]
        pct.append(sw.STOP_ATR * d.atr.iloc[k] / d.Close.iloc[k])
    book["stop_pct"] = pct
    book["eur"] = book.r * book.stop_pct * ORDER * LEV
    book["perte_stop"] = book.stop_pct * ORDER * LEV
    book["name"] = book.sym.map(sw.INDICES)
    book = book.sort_values("exit").reset_index(drop=True)
    years = (book.exit.max() - sp.ts("2012-01-01")).days / 365.25
    eq = book.set_index("exit").eur.cumsum()
    daily = eq.resample("D").last().ffill()
    dd = (eq - np.maximum(eq.cummax(), 0))
    w3 = daily - daily.shift(91)

    print(f"SWING, 500 EUR par ordre au levier {LEV} (exposition {ORDER * LEV:.0f} EUR), {len(book)} trades, "
          f"{book.entry.min():%d/%m/%Y} -> {book.exit.max():%d/%m/%Y} ({years:.1f} ans), cout 0,05 % inclus")
    print(f"  resultat total {book.eur.sum():+.0f} EUR, soit {book.eur.sum() / years:+.0f} EUR/an avant impot ; "
          f"{(book.eur > 0).mean():.0%} de trades gagnants ; gain moyen {book.eur[book.eur > 0].mean():+.0f} EUR, "
          f"perte moyenne {book.eur[book.eur <= 0].mean():+.0f} EUR ; {len(book) / years:.0f} trades/an")
    print(f"  perte au stop par trade : mediane {book.perte_stop.median():.0f} EUR, 90e centile "
          f"{book.perte_stop.quantile(.9):.0f}, max {book.perte_stop.max():.0f} ; pire trade {book.eur.min():+.0f} EUR "
          f"({book.name[book.eur.idxmin()]}, {book.exit[book.eur.idxmin()]:%d/%m/%Y}) ; meilleur {book.eur.max():+.0f} EUR")
    i = dd.idxmin()
    print(f"  pire baisse {dd.min():+.0f} EUR (creux le {i:%d/%m/%Y}) ; pire periode de 3 mois {w3.min():+.0f} EUR ; "
          f"plus longue serie de pertes : {max(len(list(g)) for k, g in itertools.groupby(book.eur <= 0) if k)} trades")

    print("\nPar annee (EUR) :")
    yr = book.groupby(book.exit.dt.year).agg(trades=("eur", "size"), resultat=("eur", "sum"),
                                             gagnants=("eur", lambda s: (s > 0).mean()))
    yr["apres_impot"] = np.where(yr.resultat > 0, yr.resultat * (1 - TAX), yr.resultat)
    yr["cumul"] = yr.resultat.cumsum()
    for y, r in yr.iterrows():
        print(f"  {y}  {int(r.trades):3d} trades  {r.resultat:+6.0f}  (apres impot {r.apres_impot:+6.0f})  "
              f"gagnants {r.gagnants:.0%}  cumul {r.cumul:+6.0f}")
    print(f"  annees negatives : {(yr.resultat < 0).sum()} sur {len(yr)} ; apres impot (PFU 31,4 % les annees "
          f"positives, sans report des pertes) : {yr.apres_impot.sum() / years:+.0f} EUR/an")

    print("\nPar indice (EUR, 2012 -> fin) :")
    for n, g in book.groupby("name").eur:
        print(f"  {n:14s} {len(g):4d} trades  {g.sum():+6.0f}  ({g.mean():+.1f} EUR/trade)")

    print(f"\nArret total a {STOP_TOTAL:.0f} EUR (regle du 07/11), en partant au debut de chaque mois :")
    starts = pd.date_range(sp.ts("2012-01-01"), book.exit.max() - pd.Timedelta(days=365), freq="MS")
    hit1, hit_any, res1 = 0, 0, []
    for s in starts:
        t = book[book.entry >= s]
        c = t.eur.cumsum()
        one = t[t.exit < s + pd.Timedelta(days=365)].eur.cumsum()
        res1.append(one.iloc[-1] if len(one) else 0.0)
        if len(one) and one.min() <= STOP_TOTAL:
            hit1 += 1
        if len(c) and c.min() <= STOP_TOTAL:
            hit_any += 1
    res1 = np.array(res1)
    print(f"  {len(starts)} departs : arret atteint dans la 1re annee {hit1} fois ({hit1 / len(starts):.0%}), "
          f"a un moment quelconque {hit_any} fois ({hit_any / len(starts):.0%})")
    print(f"  resultat de la 1re annee selon le mois de depart : mediane {np.median(res1):+.0f} EUR, "
          f"pire {res1.min():+.0f}, meilleur {res1.max():+.0f}, negative {np.mean(res1 < 0):.0%} des departs")
    print("\nDescriptif : historique, pas une promesse ; avantage statistique faible (t = 0,27 depuis 2018, audit du 06/11).")


if __name__ == "__main__":
    main()
