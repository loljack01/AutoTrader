"""Positions ouvertes dont l'indice cloture sous sa SMA200 pendant la detention (livre a 5, 2012-2026).
La regle ne sort pas sur la SMA200 (exit_trade : SMA5, stop, 10 jours) ; swing_preclose traite la position avant le
test de tendance (branche 'position ouverte'), mais le bilan du soir affiche 'sous SMA200 (pas de call)' sur la meme ligne.
Usage : python3 trend_check.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_all, cap5_trades

data = load_all()
t = cap5_trades(data)
flag = []
for x in t.itertuples():
    d = data[x.sym]
    seg = d[(d.index.normalize() > x.entry) & (d.index.normalize() < x.exit)]
    flag.append(bool((seg.Close < seg.sma200).any()))
t["sous200"] = flag
g = t.groupby("sous200").net005.agg(["count", "mean", "sum"])
print(f"Trades dont l'indice cloture sous la SMA200 pendant la detention (hors jour de sortie) : {t.sous200.sum()} "
      f"({t.sous200.mean():.1%}) ; net {g.loc[True, 'sum']:+.1f}R ({g.loc[True, 'mean']:+.3f}R/trade) contre "
      f"{g.loc[False, 'mean']:+.3f}R/trade pour les autres")
