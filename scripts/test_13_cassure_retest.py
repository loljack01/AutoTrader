"""Test 13 (B4, fiche validee par l'utilisateur le 28/11/2026 : « B4 » puis « OK ») : cassure puis retest
d'une borne du CAC 40 (FCE1!, 15m, seance 8h00-22h00). Fiche : docs/test_13_cassure_retest_fige_2026-11-28.md.

FIGE AVANT TOUT CALCUL. Regle 29 : calcul le dimanche 6/12/2026 au plus tot (le script refuse avant).

Regle :
- Bornes connues a 8h00 pour la seance J (rien du jour J) : plus haut et plus bas de J-1 ; SMA20
  journaliere (closes jusqu'a J-1) ; zones touchees au moins 3 fois dans les 3 seances precedentes = groupes
  d'au moins 3 sommets ou creux isoles 15m (2 bougies de chaque cote) a 3 points ou moins les uns des autres,
  niveau = moyenne du groupe. Bornes a 2 points ou moins fusionnees.
- Cassure (call) : la cloture 15m d'une bougie de J est >= L + 3 alors que la cloture precedente etait <= L,
  avec un volume > 1,5 fois la moyenne des 20 bougies 15m precedentes. Put : symetrique (cloture <= L - 3,
  cloture precedente >= L).
- Retest : dans les 16 bougies suivantes, une bougie dont le plus bas est <= L + 3 (put : plus haut >= L - 3)
  sans aucune cloture < L depuis la cassure (put : > L) ; une cloture de l'autre cote annule le montage.
- Entree : a la cloture de la premiere bougie de retest qui cloture dans le sens de la cassure
  (cloture > ouverture pour un call, < pour un put) et du bon cote de L.
- Stop : L - 2 (call), L + 2 (put). Cible : entree + 1,5 R ; si la borne suivante dans le sens du trade est
  plus proche mais a au moins 1 R, cible = cette borne. R = distance entree - stop.
- Heures : entrees sur les clotures de 8h15 a 21h30 ; sortie au plus tard a la cloture de 22h00. Une seule
  position a la fois. Stop et cible dans la meme bougie : stop compte en premier. Frais 3 points.
  Resultat en R = (sortie - entree - 3) / R pour un call (symetrique pour un put).
Periode jugee : tout le cache 15m du FCE1! jusqu'au vendredi 4/12/2026 inclus.
Verdict : < 30 trades non concluant ; total > 0 et t >= 3,25 (Bonferroni a 86 decisions, unilateral 5 %)
retenue pour un suivi en avant sans argent ; total > 0 et 2 <= t < 3,25 prometteuse (decision de
l'utilisateur un dimanche) ; sinon rejetee. Aucun argent reel.

Usage : python3 -W ignore scripts/test_13_cassure_retest.py
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

TZ = "Europe/Paris"
BREAK = 3.0
VOL_MULT = 1.5
RETEST_BARS = 16
RETEST_ZONE = 3.0
MARGIN = 2.0
RR = 1.5
MIN_RR_LEVEL = 1.0
COST = 3.0
ZONE_TOL = 3.0
ZONE_MIN = 3
MERGE = 2.0
FIRST_RUN = dt.date(2026, 12, 6)
LAST_DAY = dt.date(2026, 12, 4)
THRESH = 3.25
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "test_13_cassure_retest_trades.csv"


def fractals(d):
    h, l = d.High.to_numpy(), d.Low.to_numpy()
    pts = []
    for j in range(2, len(d) - 2):
        if h[j] > max(h[j - 2:j]) and h[j] > max(h[j + 1:j + 3]):
            pts.append(h[j])
        if l[j] < min(l[j - 2:j]) and l[j] < min(l[j + 1:j + 3]):
            pts.append(l[j])
    return sorted(pts)


def zones(pts):
    out, grp = [], []
    for p in pts:
        if grp and p - grp[0] > ZONE_TOL:
            if len(grp) >= ZONE_MIN:
                out.append(float(np.mean(grp)))
            grp = []
        grp.append(p)
    if len(grp) >= ZONE_MIN:
        out.append(float(np.mean(grp)))
    return out


def day_levels(daily, d15, day):
    done = daily[daily.index.tz_convert(TZ).date < day]
    if len(done) < 20:
        return None
    prev = done.iloc[-1]
    lv = [prev.High, prev.Low, done.Close.tail(20).mean()]
    days = sorted({x for x in d15.index.tz_convert(TZ).date if x < day})[-3:]
    past = d15[pd.Index(d15.index.tz_convert(TZ).date).isin(days)]
    lv += zones(fractals(past))
    merged = []
    for v in sorted(lv):
        if merged and v - merged[-1] <= MERGE:
            continue
        merged.append(v)
    return merged


def target_for(side, entry, risk, levels):
    tgt = entry + RR * risk if side == "call" else entry - RR * risk
    if side == "call":
        nxt = [L for L in levels if L > entry and (L - entry) >= MIN_RR_LEVEL * risk]
        if nxt and min(nxt) < tgt:
            tgt = min(nxt)
    else:
        nxt = [L for L in levels if L < entry and (entry - L) >= MIN_RR_LEVEL * risk]
        if nxt and max(nxt) > tgt:
            tgt = max(nxt)
    return tgt


def run_day(bars, vol_avg, levels):
    """bars: 15m bars of the day (8h-22h, Paris start times), vol_avg: mean volume of the 20 previous bars."""
    trades, pos, setups = [], None, []
    times = list(bars.index)
    for i, t in enumerate(times):
        b = bars.loc[t]
        close_hm = (t + pd.Timedelta(minutes=15)).tz_convert(TZ).strftime("%H:%M")
        last = i == len(times) - 1
        busy = pos is not None  # a position open at the start of this bar blocks any entry on this bar
        if pos is not None:
            side, entry, stop, tgt, t_in, L = pos
            hit_stop = b.Low <= stop if side == "call" else b.High >= stop
            hit_tgt = b.High >= tgt if side == "call" else b.Low <= tgt
            if hit_stop or hit_tgt or last:
                px = stop if hit_stop else tgt if hit_tgt else b.Close
                why = "stop" if hit_stop else "objectif" if hit_tgt else "fin 22h"
                pnl = (px - entry) if side == "call" else (entry - px)
                trades.append(dict(entree=t_in, sortie=close_hm, sens=side, borne=round(L, 2), prix_entree=entry,
                                   stop=stop, objectif=round(tgt, 2), prix_sortie=px, raison=why, points=pnl,
                                   r=(pnl - COST) / abs(entry - stop)))
                pos = None
        # update / trigger existing setups (retest); setups keep living while a position is open
        alive = []
        for s in setups:
            side, L, k0 = s
            if i - k0 > RETEST_BARS:
                continue
            if (side == "call" and b.Close < L) or (side == "put" and b.Close > L):
                continue  # cancelled
            touched = b.Low <= L + RETEST_ZONE if side == "call" else b.High >= L - RETEST_ZONE
            good = (b.Close > b.Open and b.Close > L) if side == "call" else (b.Close < b.Open and b.Close < L)
            if touched and good and not busy and pos is None and "08:15" <= close_hm <= "21:30" and not last:
                entry = b.Close
                stop = L - MARGIN if side == "call" else L + MARGIN
                risk = abs(entry - stop)
                pos = (side, entry, stop, target_for(side, entry, risk, levels), close_hm, L)
                continue  # setup used
            alive.append(s)
        setups = alive
        # new breakouts on this bar's close
        if i == 0:
            continue
        pc = bars.iloc[i - 1].Close
        va = vol_avg.loc[t]
        if not (va > 0 and b.Volume > VOL_MULT * va):
            continue
        for L in levels:
            if pc <= L and b.Close >= L + BREAK:
                setups.append(("call", L, i))
            if pc >= L and b.Close <= L - BREAK:
                setups.append(("put", L, i))
    return trades


def main():
    if dt.date.today() < FIRST_RUN:
        sys.exit(f"Regle 29 : calcul autorise a partir du dimanche {FIRST_RUN:%d/%m/%Y} seulement.")
    from data import cache
    d15 = cache.load("FCE1!", "15m")
    daily = cache.load("FCE1!", "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    vol_avg = d15.Volume.shift(1).rolling(20).mean()
    paris = d15.index.tz_convert(TZ)
    sess = d15[(paris.hour >= 8) & (paris.hour < 22)]
    rows = []
    for day in sorted(set(sess.index.tz_convert(TZ).date)):
        if day > LAST_DAY:
            continue
        levels = day_levels(daily, d15, day)
        if not levels:
            continue
        bars = sess[sess.index.tz_convert(TZ).date == day]
        for tr in run_day(bars, vol_avg, levels):
            tr["jour"] = day
            rows.append(tr)
    t = pd.DataFrame(rows)
    t.to_csv(OUT, index=False)
    if t.empty:
        print("Test 13 : 0 trade. VERDICT (fixe avant calcul) : NON CONCLUANT (moins de 30 trades)")
        return
    r = t.r.to_numpy()
    n = len(r)
    t_stat = r.mean() / r.std(ddof=1) * np.sqrt(n) if n > 1 else float("nan")
    cum = np.cumsum(r)
    dd = (cum - np.maximum.accumulate(cum)).min()
    print(f"Test 13, FCE1! 15m, {t.jour.min()} au {t.jour.max()} ({t.jour.nunique()} jours avec trade) : {n} trades, "
          f"{int((r > 0).sum())} gagnants, net {r.sum():+.2f}R a 3 pts, moyenne {r.mean():+.3f}R, t {t_stat:.2f}, "
          f"pire ecart {dd:+.2f}R")
    for s in ("call", "put"):
        x = t[t.sens == s].r
        print(f"  {s}s : {len(x)} trades, {x.sum():+.2f}R")
    print(f"  avant frais : {((t.points) / (t.prix_entree - t.stop).abs()).sum():+.2f}R | sans les 3 meilleurs : "
          f"{np.sort(r)[::-1][3:].sum():+.2f}R")
    print("  sorties : " + ", ".join(f"{k} {v}" for k, v in t.raison.value_counts().items()))
    if n < 30:
        verdict = "NON CONCLUANT (moins de 30 trades)"
    elif r.sum() > 0 and t_stat >= THRESH:
        verdict = "RETENUE pour un suivi en avant sans argent"
    elif r.sum() > 0 and t_stat >= 2.0:
        verdict = "PROMETTEUSE, NON PROUVEE (t entre 2 et 3,25) : decision de l'utilisateur un dimanche"
    else:
        verdict = "REJETEE"
    print(f"VERDICT (fixe avant calcul) : {verdict}")


if __name__ == "__main__":
    main()
