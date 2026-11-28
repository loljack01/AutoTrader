"""Lecture technique d'une seance du FCE1 a partir des barres 1 minute (outillage, regle 37).

Ce script ne calcule AUCUN trade et ne teste aucune regle : il decrit une seance (8h00-22h00) pour les
tableaux de puts et calls apres coup, et fait le double controle demande par l'utilisateur.

Sortie :
- seance : ouverture, plus haut et plus bas (avec l'heure), dernier cours ;
- bougies 15m : OHLC, volume (rapport a la moyenne des 20 bougies precedentes), RSI(14), moyenne
  exponentielle 20, moyenne simple 50 (historique du cache 15m pour l'amorce), prix moyen pondere par les
  volumes depuis 8h00, motif de bougie (doji, marteau, etoile filante, avalement, grande bougie pleine) ;
- sommets et creux 1m par zigzag (seuil 12 points) ;
- sommets et creux 15m (2 bougies de chaque cote) ;
- trous de cotation (FVG) 15m et 5m (>= 3 points en 5m) ;
- DOUBLE CONTROLE : un second calcul independant (module csv, sans pandas) des OHLC 15m, du plus haut, du
  plus bas et du prix moyen pondere ; le script dit si les deux calculs concordent.

Usage :
  python3 -W ignore scripts/lecture_fce1_jour.py <barres_1m.csv|.json> [--date AAAA-MM-JJ]
Le fichier est un CSV (colonnes t,o,h,l,c,v ; t en secondes UTC) ou le JSON de get-ohlcv
(format rows ou columns). Plusieurs fichiers peuvent etre donnes : ils sont fusionnes (le plus recent gagne).
"""

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from data import cache

TZ = "Europe/Paris"


def load(paths):
    frames = []
    for p in paths:
        if p.endswith(".csv"):
            frames.append(pd.read_csv(p, index_col=0))
            continue
        js = json.load(open(p))
        bars = js.get("bars", js)
        frames.append(pd.DataFrame(bars).set_index("t"))
    m = pd.concat(frames)
    m = m[~m.index.duplicated(keep="last")].sort_index()
    return m


def candle(r, p):
    rng = r.h - r.l
    body = abs(r.c - r.o)
    uw = r.h - max(r.o, r.c)
    lw = min(r.o, r.c) - r.l
    s = []
    if rng and body / rng < 0.25:
        s.append("doji")
    if lw >= 2 * body and lw >= 0.5 * rng:
        s.append("marteau")
    if uw >= 2 * body and uw >= 0.5 * rng:
        s.append("etoile filante")
    if r.c > r.o and p.c < p.o and r.c >= p.o and r.o <= p.c:
        s.append("avalement haussier")
    if r.c < r.o and p.c > p.o and r.c <= p.o and r.o >= p.c:
        s.append("avalement baissier")
    if rng and body / rng >= 0.7:
        s.append("grande bougie " + ("verte" if r.c > r.o else "rouge"))
    return f"corps {body:.1f} mh {uw:.1f} mb {lw:.1f} " + ", ".join(s)


def zigzag(t, th):
    pts, mode = [], None
    hi = (t.h.iloc[0], t.index[0])
    lo = (t.l.iloc[0], t.index[0])
    for ts, r in t.iterrows():
        if r.h > hi[0]:
            hi = (r.h, ts)
        if r.l < lo[0]:
            lo = (r.l, ts)
        if mode in (None, "up") and hi[0] - r.l >= th and hi[1] < ts:
            pts.append(("SOMMET",) + hi)
            mode, lo = "down", (r.l, ts)
        elif mode in (None, "down") and r.h - lo[0] >= th and lo[1] < ts:
            pts.append(("CREUX",) + lo)
            mode, hi = "up", (r.h, ts)
    return pts


def second_pass(m, day):
    """Independent check with the csv-like raw values, no pandas resampling."""
    P = ZoneInfo(TZ)
    rows = []
    for t, r in m.iterrows():
        ts = dt.datetime.fromtimestamp(int(t), P)
        if ts.date() == day and 8 <= ts.hour < 22:
            rows.append((ts, float(r.o), float(r.h), float(r.l), float(r.c), float(r.v)))
    b = {}
    s = n = 0.0
    for ts, o, h, l, c, v in rows:
        k = ts.replace(minute=ts.minute // 15 * 15)
        if k not in b:
            b[k] = [o, h, l, c]
        else:
            x = b[k]
            x[1], x[2], x[3] = max(x[1], h), min(x[2], l), c
        s += (h + l + c) / 3 * v
        n += v
    hi = max(rows, key=lambda x: x[2])
    lo = min(rows, key=lambda x: x[3])
    return b, (hi[2], hi[0].strftime("%H:%M")), (lo[3], lo[0].strftime("%H:%M")), round(s / n, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--date")
    a = ap.parse_args()
    raw = load(a.files)
    m = raw.copy()
    m.index = pd.to_datetime(m.index, unit="s", utc=True).tz_convert(TZ)
    day = pd.Timestamp(a.date).date() if a.date else m.index[-1].date()
    t = m[(m.index.date == day) & (m.index.hour >= 8) & (m.index.hour < 22)]
    if t.empty:
        sys.exit(f"aucune barre 1m le {day}")
    print(f"FCE1! {day} : {len(t)} minutes de {t.index[0]:%H:%M} a {t.index[-1]:%H:%M} "
          f"(la derniere barre peut etre en formation)")
    print(f"ouverture {t.o.iloc[0]} | plus haut {t.h.max()} a {t.h.idxmax():%H:%M} | plus bas {t.l.min()} a "
          f"{t.l.idxmin():%H:%M} | dernier {t.c.iloc[-1]}")
    tp = (t.h + t.l + t.c) / 3
    vwap = (tp * t.v).cumsum() / t.v.cumsum()
    q = t.resample("15min").agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()
    c15 = cache.load("FCE1!", "15m")[["Open", "High", "Low", "Close", "Volume"]]
    c15.columns = ["o", "h", "l", "c", "v"]
    c15.index = c15.index.tz_convert(TZ)
    x = pd.concat([c15[c15.index < q.index[0]], q])
    x["ema20"] = x.c.ewm(span=20, adjust=False).mean()
    x["sma50"] = x.c.rolling(50).mean()
    d = x.c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    x["rsi"] = 100 - 100 / (1 + up / dn)
    x["vavg"] = x.v.rolling(20).mean().shift()
    prev = x.shift()
    print("\nBougies 15m (heure de debut) :")
    for ts in q.index:
        r = x.loc[ts]
        vw = vwap[:ts + pd.Timedelta(minutes=14)].iloc[-1]
        print(f"{ts:%H:%M} O{r.o:.1f} H{r.h:.1f} B{r.l:.1f} C{r.c:.1f} v{int(r.v)} ({r.v / r.vavg:.1f}x) "
              f"RSI {r.rsi:.0f} EMA20 {r.ema20:.1f} SMA50 {r.sma50:.1f} VWAP {vw:.1f} | {candle(r, prev.loc[ts])}")
    print("\nSommets et creux 1m (zigzag 12 points) :")
    print("  " + " ; ".join(f"{k} {v} {ts:%H:%M}" for k, v, ts in zigzag(t, 12)))
    qq = q.reset_index()
    sw = []
    for j in range(2, len(qq) - 2):
        if qq.h[j] > max(qq.h[j - 2:j]) and qq.h[j] >= max(qq.h[j + 1:j + 3]):
            sw.append(f"S {qq.h[j]} {qq.iloc[j, 0]:%H:%M}")
        if qq.l[j] < min(qq.l[j - 2:j]) and qq.l[j] <= min(qq.l[j + 1:j + 3]):
            sw.append(f"C {qq.l[j]} {qq.iloc[j, 0]:%H:%M}")
    print("Sommets (S) et creux (C) 15m : " + " ; ".join(sw))
    for name, f, th in (("15m", q, 0.0), ("5m", t.resample("5min").agg(
            {"o": "first", "h": "max", "l": "min", "c": "last"}).dropna(), 3.0)):
        out = []
        for i in range(2, len(f)):
            b0, b2 = f.iloc[i - 2], f.iloc[i]
            if b2.l - b0.h > th or (th and b2.l - b0.h >= th):
                out.append(f"haussier {f.index[i - 1]:%H:%M} {b0.h}-{b2.l}")
            if b0.l - b2.h > th or (th and b0.l - b2.h >= th):
                out.append(f"baissier {f.index[i - 1]:%H:%M} {b2.h}-{b0.l}")
        print(f"Trous de cotation {name} : " + " ; ".join(out))
    print("\nTop volumes 1m : " + ", ".join(f"{ts:%H:%M} {int(v)}" for ts, v in t.v.nlargest(6).items()))
    # double controle
    b, hi2, lo2, vw2 = second_pass(raw, day)
    ok = (hi2[0] == t.h.max() and lo2[0] == t.l.min() and abs(vw2 - round(vwap.iloc[-1], 1)) < 0.06
          and all(abs(b[k][i] - q.loc[pd.Timestamp(k)].iloc[i]) < 1e-9 for k in b for i in range(4))
          and len(b) == len(q))
    print(f"\nDOUBLE CONTROLE (second calcul independant) : {'CONCORDE' if ok else 'DIFFERENT, verifier'} "
          f"(plus haut {hi2[0]} a {hi2[1]}, plus bas {lo2[0]} a {lo2[1]}, VWAP {vw2}, {len(b)} bougies 15m)")


if __name__ == "__main__":
    main()
