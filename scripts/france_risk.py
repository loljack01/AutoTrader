"""Bloc "Risque France" du plan de journee (information, aucun signal).

Ecart de taux France - Allemagne a 10 ans (en points de base) a partir des
clotures journalieres TradingView TVC:FR10Y et TVC:DE10Y (et TVC:IT10Y pour
la comparaison France - Italie) : niveau, variation sur 1 et 5 seances,
plus haut des 21 dernieres seances (environ un mois). Prudence signalee
quand l'ecart du jour atteint ou depasse ce plus haut : la tension sur la
dette francaise s'aggrave (banques francaises et CAC sous pression
possible). Seuil non teste : simple repere de risque, comme les horaires
bloques.

Usage: python scripts/france_risk.py fichier_FR10Y.json fichier_DE10Y.json [fichier_IT10Y.json]
"""

import json
import sys

import pandas as pd


def closes(path):
    j = json.load(open(path))
    b = j["bars"]
    if isinstance(b, dict):
        b = [dict(zip(b.keys(), row)) for row in zip(*b.values())]
    s = pd.Series({pd.Timestamp(x["t"], unit="s", tz="UTC").tz_convert("Europe/Paris").date(): x["c"] for x in b})
    return j["symbol"], s.sort_index()


def main():
    series = dict(closes(p) for p in sys.argv[1:])
    fr, de = series["TVC:FR10Y"], series["TVC:DE10Y"]
    spread = ((fr - de).dropna() * 100).round(1)
    now, high = spread.iloc[-1], spread.iloc[-22:-1].max()
    d1 = now - spread.iloc[-2]
    d5 = now - spread.iloc[-6]
    print(f"Ecart France-Allemagne 10 ans : {now:.1f} pb ({d1:+.1f} pb sur 1 seance, {d5:+.1f} pb sur 5) | "
          f"plus haut des 21 seances precedentes {high:.1f} pb")
    if now >= high:
        print("  PRUDENCE : l'ecart est a son plus haut sur un mois (tension sur la dette francaise qui s'aggrave)")
    print(f"Taux 10 ans : France {fr.iloc[-1]:.3f} %, Allemagne {de.iloc[-1]:.3f} %", end="")
    if "TVC:IT10Y" in series:
        it = series["TVC:IT10Y"]
        gap = (fr.iloc[-1] - it.iloc[-1]) * 100
        print(f", Italie {it.iloc[-1]:.3f} % -> France {'au-dessus' if gap > 0 else 'en dessous'} de l'Italie de "
              f"{abs(gap):.0f} pb", end="")
    print()


if __name__ == "__main__":
    main()
