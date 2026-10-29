"""Plan de journee CAC (FCE1!), a lire avant 9h00 Paris. Ne donne AUCUN
signal : il liste les niveaux ou observer la reaction du prix (methode
"reagir, pas predire" du 29/10) et rappelle les regles des versions
suivies. Les annonces economiques sont ajoutees par la tache du matin
(calendrier TradingView), pas par ce script.

Niveaux :
  veille       cloture officielle (1D), plus haut, plus bas
  semaine      plus haut / plus bas depuis lundi (jours clos)
  avant-ouv.   plus haut / plus bas du FCE1 depuis 8h00 Paris (provisoire)
  liquidite    doubles sommets (EQH) / doubles creux (EQL) en 15m, intacts
               (jamais balayes ni clotures au-dela), comme la strategie principale
  swings       sommets / creux isoles en 15m de la veille et du jour, encore
               intacts (version "simple balayage")
Les niveaux a moins de 2 points l'un de l'autre sont regroupes.
  ronds        multiples de 50 points
Seuils de "l'ecart continue" (cloture de la bougie 9h00-9h15) et etat du
filtre de tendance (cloture de la veille vs SMA20 journaliere).

Usage: python scripts/day_plan.py [fichier_15m.json fichier_1D.json ...]
  (fichiers tool-results TradingView de FCE1!, fusionnes en memoire avec le
  cache sans l'ecrire)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from finta import TA

from data import cache
from levels import liquidity, structure

SYMBOL = "FCE1!"
TZ = "Europe/Paris"
WINDOW_ATR = 1.2  # niveaux affiches a +/- 1.2 ATR journalier du dernier cours
TRADES = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_calls_trend_trades.csv"


def load(files):
    frames = {"15m": cache.load(SYMBOL, "15m"), "1D": cache.load(SYMBOL, "1D")}
    for f in files:
        j = json.load(open(f))
        if j.get("symbol") != SYMBOL or j.get("interval") not in frames:
            continue
        new = cache._bars_to_frame(j["bars"])
        d = pd.concat([frames[j["interval"]], new])
        frames[j["interval"]] = d[~d.index.duplicated(keep="last")].sort_index()
    return frames["15m"], frames["1D"]


def intact(pools, d, kind):
    """Unswept pools never closed through after confirmation."""
    out = []
    close = d.Close
    for p in pools:
        if p["swept_at"] is not None:
            continue
        after = close[close.index > p["members"][1][0]]
        beyond = (after > p["level"]).any() if kind == "high" else (after < p["level"]).any()
        if not beyond:
            out.append(p)
    return out


def main():
    now = pd.Timestamp.now(tz="UTC")
    d15, daily = load(sys.argv[1:])
    d15 = cache.closed_bars(d15, "15m", now)
    today = now.tz_convert(TZ).date()
    daily.index = pd.to_datetime(daily.index, utc=True)
    done = daily[daily.index.tz_convert(TZ).date < today]
    prev = done.iloc[-1]
    tr = pd.concat([done.High - done.Low, (done.High - done.Close.shift()).abs(),
                    (done.Low - done.Close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    sma20 = done.Close.rolling(20).mean().iloc[-1]
    monday = today - pd.Timedelta(days=today.weekday())
    week = done[done.index.tz_convert(TZ).date >= monday]

    paris = d15.index.tz_convert(TZ)
    pre = d15[(paris.date == today) & (paris.hour >= 8)]
    last = d15.Close.iloc[-1]
    last_t = (d15.index[-1] + pd.Timedelta(minutes=15)).tz_convert(TZ).strftime("%d/%m %H:%M")

    a15 = TA.ATR(d15, 14)
    is_hi, is_lo = structure.find_swings(d15, n=2)
    hi_m = structure.confirmed_marks(is_hi, d15.High, 2)
    lo_m = structure.confirmed_marks(is_lo, d15.Low, 2)
    eqh = intact(liquidity.find_sweeps(liquidity.find_pools(hi_m, a15), d15, "high"), d15, "high")
    eql = intact(liquidity.find_sweeps(liquidity.find_pools(lo_m, a15), d15, "low"), d15, "low")
    singles_h = intact(liquidity.find_sweeps([{"level": v, "members": [(t, v), (t, v)]} for t, v in hi_m.dropna().items()],
                                             d15, "high"), d15, "high")
    singles_l = intact(liquidity.find_sweeps([{"level": v, "members": [(t, v), (t, v)]} for t, v in lo_m.dropna().items()],
                                             d15, "low"), d15, "low")

    levels = [(prev.Close, "cloture veille (reglement)"), (prev.High, "plus haut veille"), (prev.Low, "plus bas veille")]
    if len(week) > 1:
        levels += [(week.High.max(), "plus haut semaine"), (week.Low.min(), "plus bas semaine")]
    if len(pre):
        levels += [(pre.High.max(), "plus haut depuis 8h"), (pre.Low.min(), "plus bas depuis 8h")]
    levels += [(p["level"], f"double sommet {p['members'][0][0].tz_convert(TZ):%d/%m %H:%M} (liquidite)") for p in eqh]
    levels += [(p["level"], f"double creux {p['members'][0][0].tz_convert(TZ):%d/%m %H:%M} (liquidite)") for p in eql]
    since = pd.Timestamp(done.index[-1].tz_convert(TZ).date(), tz=TZ)
    singles_h = [p for p in singles_h if p["members"][0][0] >= since]
    singles_l = [p for p in singles_l if p["members"][0][0] >= since]
    levels += [(p["level"], f"sommet isole {p['members'][0][0].tz_convert(TZ):%d/%m %H:%M}") for p in singles_h]
    levels += [(p["level"], f"creux isole {p['members'][0][0].tz_convert(TZ):%d/%m %H:%M}") for p in singles_l]
    base = np.floor(last / 50) * 50
    levels += [(base + k * 50, "chiffre rond") for k in (-2, -1, 0, 1, 2, 3)]
    lo, hi = last - WINDOW_ATR * atr, last + WINDOW_ATR * atr
    merged = []
    for v, lab in sorted(((round(v, 1), lab) for v, lab in levels if lo <= v <= hi), reverse=True):
        if merged and merged[-1][0] - v <= 2.0:
            if lab not in merged[-1][1]:
                merged[-1] = (merged[-1][0], merged[-1][1] + " + " + lab)
        else:
            merged.append((v, lab))
    levels = merged

    up = prev.Close > sma20
    print(f"PLAN DE JOURNEE FCE1! — {today:%d/%m/%Y}, dernier cours {last:.1f} (bougie close {last_t} Paris)")
    print(f"Veille : cloture {prev.Close:.1f}, haut {prev.High:.1f}, bas {prev.Low:.1f} | ATR journalier {atr:.1f} pts")
    print(f"Tendance : cloture veille {prev.Close:.1f} {'>' if up else '<'} SMA20 {sma20:.1f} -> "
          f"{'calls ET puts autorises' if up else 'PUTS seulement (calls interdits)'}")
    if len(pre):
        print(f"Depuis 8h00 : haut {pre.High.max():.1f}, bas {pre.Low.min():.1f} (provisoire, la bougie 8h45 n'est pas close)")
    print(f"\nNiveaux a +/- {WINDOW_ATR} ATR ({lo:.0f} - {hi:.0f}), du plus haut au plus bas :")
    shown = False
    for v, lab in levels:
        if not shown and v < last:
            print(f"   ---- {last:.1f} dernier cours ----")
            shown = True
        print(f"   {v:8.1f}  {lab}")
    if not shown:
        print(f"   ---- {last:.1f} dernier cours ----")
    above = [x for x in levels if x[0] > last]
    below = [x for x in levels if x[0] < last]
    print("\nScenarios (a valider sur CLOTURE 5m, jamais au contact) :")
    if below:
        v, lab = below[0]
        tgt = f"{above[-1][0]:.1f} ({above[-1][1]})" if above else "niveau suivant"
        print(f"  CALL{'' if up else ' (interdit : tendance baissiere)'} : balayage de {v:.1f} ({lab}) puis cloture 5m "
              f"revenue au-dessus -> stop sous la meche - 8 pts, premiere cible {tgt}")
    if above:
        v, lab = above[-1]
        tgt = f"{below[0][0]:.1f} ({below[0][1]})" if below else "niveau suivant"
        print(f"  PUT : depassement de {v:.1f} ({lab}) puis cloture 5m revenue en dessous -> stop au-dessus de la "
              f"meche + 8 pts, premiere cible {tgt}")
    c, g1, g2 = prev.Close, 0.25 * atr, 1.0 * atr
    print(f"  Ecart continue (bougie 9h00-9h15, version fragile suivie sans argent) : achat si cloture entre "
          f"{c + g1:.1f} et {c + g2:.1f}, vente si entre {c - g2:.1f} et {c - g1:.1f}, et la bougie ne touche pas {c:.1f} ; "
          f"stop {c:.1f}, cible 1:1, sortie 12h00")
    if TRADES.exists():
        t = pd.read_csv(TRADES)
        o = t[(t.marche == "CAC 40") & (t.version == "sma20") & (t.resultat == "open")]
        for x in o.itertuples():
            print(f"  Position ouverte de la principale (CAC) : {x.sens} {x.entree_paris} entree {x.entree} stop {x.stop} cible {x.cible}")
    print("\nRappels : rien entre 9h00 et 9h15 ni dans les 15 min autour d'une annonce ; la strategie principale (15m) "
          "reste la seule candidate au reel ; les trades de reaction se notent au journal, sans argent.")


if __name__ == "__main__":
    main()
