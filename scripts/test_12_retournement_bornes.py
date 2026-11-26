"""Test 12 (fige le 26/11/2026 avant calcul, docs/test_12_retournement_bornes_fige_2026-11-26.md) :
retournement confirme sur une borne du CAC 40 (FCE1!, 15m, seance 8h00-22h00), stop derriere le point de
retournement, vente au premier niveau connu qui donne au moins 1,5 R net.

Regle (fixee avant tout calcul, ne pas modifier apres le premier lancement) :
- Niveaux connus a 8h00 pour la seance J (rien du jour J) : reglement, plus haut et plus bas de J-1 ;
  plus haut et plus bas de la semaine (jours clos) ; SMA20 journaliere ; sommets et creux isoles 15m
  (2 bougies de chaque cote) des 3 seances precedentes ; chiffres ronds de 50 points. Niveaux a moins de
  2 points fusionnes ; gardes s'ils sont a +/- 1,5 ATR14 journalier du reglement de J-1.
- Borne et balayage (call) : une bougie 15m de J fait le plus bas des 16 dernieres bougies (4 h) ET passe
  sous un niveau L. Confirmation : une cloture 15m revient au-dessus de L sur cette bougie ou l'une des
  2 suivantes. Entree a cette cloture. Put : symetrique (plus haut des 16 dernieres, passage au-dessus
  de L, cloture revenue en dessous). Un seul niveau balaye puis repris suffit. Si un call et un put se
  presentent sur la meme cloture, le call est pris.
- Stop : 2 points au-dela de l'extreme du balayage (plus bas pour un call, plus haut pour un put).
- Objectif : le premier niveau connu dans le sens du trade a une distance telle que (objectif - entree -
  3 points de frais) >= 1,5 x (entree - stop). Pas d'objectif dans la liste : pas de trade.
- Heures : entree seulement sur les clotures de 8h15 a 21h30, jamais aux clotures de 9h00, 15h30, 15h45,
  17h15 et 17h30. Sortie au plus tard a la cloture de 22h00. Une seule position a la fois. Stop et objectif
  dans la meme bougie : stop compte en premier.
- Frais : 3 points par trade. Resultat en R = (sortie - entree - 3) / (entree - stop) pour un call.
Les annonces economiques ne sont pas filtrees (pas de calendrier historique dans le cache).

Periode jugee : tout le cache 15m du FCE1! jusqu'au 25/11/2026 inclus (le 26/11, jour d'ou vient l'idee,
est exclu du verdict et montre a part s'il est en cache).

Usage : python3 -W ignore scripts/test_12_retournement_bornes.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache

TZ = "Europe/Paris"
COST = 3.0
MARGIN = 2.0
RR = 1.5
LOOK = 16
CONFIRM = 2
NO_ENTRY = {"09:00", "15:30", "15:45", "17:15", "17:30"}
LAST_DAY = pd.Timestamp("2026-11-25").date()
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "test_12_retournement_bornes_trades.csv"


def swings(d):
    h, l = d.High.to_numpy(), d.Low.to_numpy()
    hi, lo = [], []
    for j in range(2, len(d) - 2):
        if h[j] > max(h[j - 2:j]) and h[j] > max(h[j + 1:j + 3]):
            hi.append(h[j])
        if l[j] < min(l[j - 2:j]) and l[j] < min(l[j + 1:j + 3]):
            lo.append(l[j])
    return hi + lo


def day_levels(daily, d15, day):
    done = daily[daily.index.tz_convert(TZ).date < day]
    if len(done) < 21:
        return None
    prev = done.iloc[-1]
    tr = pd.concat([done.High - done.Low, (done.High - done.Close.shift()).abs(),
                    (done.Low - done.Close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    sma20 = done.Close.rolling(20).mean().iloc[-1]
    monday = day - pd.Timedelta(days=day.weekday())
    week = done[done.index.tz_convert(TZ).date >= monday]
    lv = [prev.Close, prev.High, prev.Low, sma20]
    if len(week):
        lv += [week.High.max(), week.Low.min()]
    days = sorted({x for x in d15.index.tz_convert(TZ).date if x < day})[-3:]
    past = d15[pd.Index(d15.index.tz_convert(TZ).date).isin(days)]
    lv += swings(past)
    base = np.floor(prev.Close / 50) * 50
    lv += [base + k * 50 for k in range(-6, 8)]
    lo, hi = prev.Close - 1.5 * atr, prev.Close + 1.5 * atr
    merged = []
    for v in sorted(x for x in lv if lo <= x <= hi):
        if merged and v - merged[-1] <= 2.0:
            continue
        merged.append(v)
    return merged


def run_day(bars, hist, levels):
    """bars: 15m bars of the day (8h-22h), hist: all bars up to the end of the day (for the 16-bar extremes)."""
    trades, pos = [], None
    times = list(bars.index)
    for i, t in enumerate(times):
        b = bars.loc[t]
        close_hm = (t + pd.Timedelta(minutes=15)).tz_convert(TZ).strftime("%H:%M")
        if pos is not None:
            side, entry, stop, target, t_in = pos
            hit_stop = b.Low <= stop if side == "call" else b.High >= stop
            hit_tgt = b.High >= target if side == "call" else b.Low <= target
            last = i == len(times) - 1
            if hit_stop or hit_tgt or last:
                px = stop if hit_stop else target if hit_tgt else b.Close
                why = "stop" if hit_stop else "objectif" if hit_tgt else "fin 22h"
                risk = abs(entry - stop)
                pnl = (px - entry) if side == "call" else (entry - px)
                trades.append(dict(entree=t_in, sortie=close_hm if why == "fin 22h" else t.tz_convert(TZ).strftime("%H:%M"),
                                   sens=side, prix_entree=entry, stop=stop, objectif=target, prix_sortie=px,
                                   raison=why, points=pnl, r=(pnl - COST) / risk))
                pos = None
            continue
        if close_hm < "08:15" or close_hm > "21:30" or close_hm in NO_ENTRY:
            continue
        # look for a sweep bar among this bar and the 2 previous ones, confirmed by this bar's close
        k = hist.index.get_loc(t)
        for back in range(0, CONFIRM + 1):
            s = k - back
            if s < LOOK or hist.index[s].tz_convert(TZ).date() != t.tz_convert(TZ).date():
                continue
            sb = hist.iloc[s]
            win = hist.iloc[s - LOOK + 1:s + 1]
            if sb.Low <= win.Low.min():
                swept = [L for L in levels if sb.Low < L < b.Close]
                ext = hist.iloc[s:k + 1].Low.min()
                if swept:
                    entry, stop = b.Close, ext - MARGIN
                    risk = entry - stop
                    tg = [L for L in levels if L - entry - COST >= RR * risk]
                    if risk > 0 and tg:
                        pos = ("call", entry, stop, min(tg), close_hm)
                        break
            if sb.High >= win.High.max():
                swept = [L for L in levels if b.Close < L < sb.High]
                ext = hist.iloc[s:k + 1].High.max()
                if swept:
                    entry, stop = b.Close, ext + MARGIN
                    risk = stop - entry
                    tg = [L for L in levels if entry - L - COST >= RR * risk]
                    if risk > 0 and tg:
                        pos = ("put", entry, stop, max(tg), close_hm)
                        break
    return trades


def main():
    d15 = cache.load("FCE1!", "15m")
    daily = cache.load("FCE1!", "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    paris = d15.index.tz_convert(TZ)
    sess = d15[(paris.hour >= 8) & (paris.hour < 22)]
    days = sorted(set(sess.index.tz_convert(TZ).date))
    rows = []
    for day in days:
        levels = day_levels(daily, d15, day)
        if not levels:
            continue
        bars = sess[sess.index.tz_convert(TZ).date == day]
        hist = sess[sess.index.tz_convert(TZ).date <= day]
        for tr in run_day(bars, hist, levels):
            tr["jour"] = day
            rows.append(tr)
    t = pd.DataFrame(rows)
    t.to_csv(OUT, index=False)
    j = t[t.jour <= LAST_DAY]
    r = j.r.to_numpy()
    n = len(r)
    t_stat = r.mean() / r.std(ddof=1) * np.sqrt(n) if n > 1 else float("nan")
    cum = np.cumsum(r)
    dd = (cum - np.maximum.accumulate(cum)).min() if n else 0
    print(f"Test 12, FCE1! 15m, {j.jour.min()} au {j.jour.max()} ({len(set(j.jour))} jours avec trade) : "
          f"{n} trades, {int((r > 0).sum())} gagnants, net {r.sum():+.2f}R a 3 pts, moyenne {r.mean():+.3f}R, "
          f"t {t_stat:.2f}, pire ecart {dd:+.2f}R")
    for s in ("call", "put"):
        x = j[j.sens == s].r
        print(f"  {s}s : {len(x)} trades, {x.sum():+.2f}R, moyenne {x.mean():+.3f}R")
    srt = np.sort(r)[::-1]
    print(f"  sans les 3 meilleurs : {srt[3:].sum():+.2f}R | avant le 28/10 : "
          f"{j[j.jour < pd.Timestamp('2026-10-28').date()].r.sum():+.2f}R "
          f"({(j.jour < pd.Timestamp('2026-10-28').date()).sum()} trades), depuis : "
          f"{j[j.jour >= pd.Timestamp('2026-10-28').date()].r.sum():+.2f}R")
    print(f"  sorties : " + ", ".join(f"{k} {v}" for k, v in j.raison.value_counts().items()))
    if n < 30:
        verdict = "NON CONCLUANT (moins de 30 trades)"
    elif r.sum() > 0 and t_stat >= 3.24:
        verdict = "RETENUE pour un suivi en avant sans argent"
    elif r.sum() > 0 and t_stat >= 2.0:
        verdict = "PROMETTEUSE, NON PROUVEE (t entre 2 et 3,24) : decision de l'utilisateur"
    else:
        verdict = "REJETEE"
    print(f"VERDICT (fixe avant calcul) : {verdict}")
    extra = t[t.jour > LAST_DAY]
    if len(extra):
        print("Hors verdict (jour de l'idee et apres) :")
        for x in extra.itertuples():
            print(f"  {x.jour} {x.entree} {x.sens} {x.prix_entree} stop {x.stop} obj {x.objectif} -> {x.raison} "
                  f"{x.sortie} {x.prix_sortie} {x.r:+.2f}R")


if __name__ == "__main__":
    main()
