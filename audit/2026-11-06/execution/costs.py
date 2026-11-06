"""Couts reels et produit, swing livre a 5 positions, 2012-2026, 25 EUR de risque par trade.
Exposition E = 25 x cours / distance du stop (EUR, quel que soit l'indice). Ordre >= 500 EUR.
Spread 0,01 EUR sur le prix du turbo = 0,01 x parite points (x EURUSD / EURGBP / EURCHF hors zone euro, turbo non quanto) ;
cout en R = 0,01 x parite x fx / distance du stop (paye une fois par aller-retour).
Financement (hypothese a verifier sur la fiche produit) : 4,5 %/an (EUR) ou 6,5 %/an (USD, GBP, CHF : 5,5 %) sur le
montant finance E x (1 - 1/levier), par jour calendaire de detention ; levier 1,5 (point 9 des regles).
Impot : PFU 31,4 % (12,8 % IR + 18,6 % prelevements sociaux, LFSS 2026) sur le gain net annuel, pertes reportables 10 ans.
Usage : python3 costs.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_all, cap5_trades
import numpy as np
import pandas as pd

RISK = 25.0
FX = {"SP:SPX": 1.15, "NASDAQ:NDX": 1.15, "TVC:DJI": 1.15, "TVC:RUT": 1.15, "TVC:UKX": 0.87, "SIX:SMI": 0.93}
RATE = {s: 0.065 for s in ("SP:SPX", "NASDAQ:NDX", "TVC:DJI", "TVC:RUT")} | {"TVC:UKX": 0.055, "SIX:SMI": 0.055}
PFU = 0.314
t = cap5_trades(load_all())
years = (t.exit.max() - t.entry.min()).days / 365.25
E = RISK * t.cost_frac
q = E.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
print(f"{len(t)} trades, {years:.1f} ans. Exposition pour 25 EUR : mediane {q[0.5]:.0f} EUR (5e-95e centiles {q[0.05]:.0f}-{q[0.95]:.0f}, "
      f"quartiles {q[0.25]:.0f}-{q[0.75]:.0f})")
print(f"  E < 500 EUR (ordre de 500 EUR impossible sans sur-risque) : {(E < 500).mean():.1%} ; "
      f"E > 800 EUR (levier > 1,6 a 500 EUR) : {(E > 800).mean():.1%} ; 700-900 EUR : {E.between(700, 900).mean():.1%} ; "
      f"E < 750 EUR (levier <= 1,5 impossible avec un ordre de 500 EUR) : {(E < 750).mean():.1%}")
print("  par indice, part E < 500 / mediane : " + ", ".join(f"{m} {(E[t.market == m] < 500).mean():.0%}/{E[t.market == m].median():.0f}"
                                                         for m in t.market.unique()))
ev = pd.concat([pd.Series(E.values, index=t.entry), pd.Series(-E.values, index=t.exit)]).groupby(level=0).sum().cumsum()
print(f"  exposition totale simultanee max {ev.max():.0f} EUR ; argent place au levier 1,5 max {ev.max() / 1.5:.0f} EUR (capital 10 000)")
print(f"  stop en % du cours : mediane {(1 / t.cost_frac).median():.2%} (levier 1,5 => barriere a 33 % sous le cours)")
fx = t.sym.map(FX).fillna(1.0)
model005, model010 = 0.0005 * t.cost_frac, 0.0010 * t.cost_frac
print(f"Couts par trade en R : modele 0,05 % moy {model005.mean():.4f}R, 0,10 % {model010.mean():.4f}R")
for par in (10, 100, 1000):
    s = 0.01 * par * fx / t.risk
    print(f"  spread 0,01 EUR parite {par:>4} : moyenne {s.mean():.4f}R, 95e centile {s.quantile(.95):.4f}R")
spread = 0.01 * np.where(t.market == "FTSE MIB", 1000, 100) * fx / t.risk  # parite 100 (1000 pour le FTSE MIB)
cal = (t.exit - t.entry).dt.days
rate = t.sym.map(RATE).fillna(0.045)
fin = lambda lev: rate * cal / 365 * (1 - 1 / lev) * t.cost_frac  # en R (E x taux x jours / 25)
print(f"  spread parite 100 (FTSE MIB 1000) : moy {spread.mean():.4f}R ; financement levier 1,5 : moy {fin(1.5).mean():.4f}R "
      f"(levier 3 : {fin(3).mean():.4f}R) ; detention moyenne {cal.mean():.1f} jours calendaires")
real = t.move_r - spread - fin(1.5)
for lab, r in (("brut", t.move_r), ("modele 0,05 %", t.net005), ("modele 0,10 %", t.net010), ("couts reels estimes", real)):
    print(f"  {lab:20s} : {r.mean():+.4f}R/trade, {r.sum() / years:+.2f}R/an = {r.sum() / years * RISK:+.0f} EUR/an")
# impot
yr = (real * RISK).groupby(t.exit.dt.year).sum()
carry, tax = [], []
for y, g in yr.items():
    carry = [(yy, v) for yy, v in carry if y - yy <= 10]
    base = g
    if base > 0:
        while carry and base > 0:
            yy, v = carry.pop(0)
            use = min(v, base)
            base -= use
            if v - use > 0:
                carry.insert(0, (yy, v - use))
        tax.append(PFU * base)
    else:
        carry.append((y, -g))
        tax.append(0.0)
tax = pd.Series(tax, index=yr.index)
full = yr[(yr.index >= 2012) & (yr.index <= 2025)]
print(f"Par annee (couts reels, EUR) : " + ", ".join(f"{y} {v:+.0f}" for y, v in yr.items()))
print(f"  annees 2012-2025 : avant impot {full.mean():+.0f} EUR/an ({(full < 0).sum()} annees negatives) ; impot moyen "
      f"{tax[full.index].mean():.0f} EUR/an ; apres impot {(full - tax[full.index]).mean():+.0f} EUR/an "
      f"= {(full - tax[full.index]).mean() / 10000:.2%} des 10 000 EUR")
print(f"  sans report des pertes (impot sur chaque annee positive) : apres impot {(full - PFU * full.clip(lower=0)).mean():+.0f} EUR/an")
