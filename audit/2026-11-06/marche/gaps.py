"""Audit marche 06/11/2026 - section 4 : ecarts d'ouverture des futures (journalier),
DESCRIPTIF. FCE1!, ES1!, NQ1! (data/cache/*_1D.csv, 2012 -> 05/11/2026).
Ecart = Ouverture(J) / Cloture(J-1) - 1, en % et en ATR14 journalier (J-1).
Les semaines de roulement sont exclues (FCE1 : semaine de l'echeance mensuelle ;
ES/NQ : les deux semaines finissant au 3e vendredi de mars, juin, sept., dec.), car la
serie continue non ajustee y saute d'un contrat a l'autre.
Groupes : lundi (week-end), autres jours, lendemain d'emploi US / CPI / FOMC / BCE
(calendrier TradingView, events.py). Puis : turbo garde le week-end (principale et swing).

Usage: PYTHONDONTWRITEBYTECODE=1 python3 /home/user/AutoTrader/audit/2026-11-06/marche/gaps.py
"""
import sys
from datetime import timedelta
from pathlib import Path

REPO = Path("/home/user/AutoTrader")
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from data.roll import third_friday
from events import load_events

HERE = Path(__file__).resolve().parent


def roll_days(kind, years):
    out = set()
    for y in years:
        for m in range(1, 13):
            if kind == "quarterly" and m not in (3, 6, 9, 12):
                continue
            f = third_friday(y, m)
            span = 12 if kind == "quarterly" else 5
            out |= {f - timedelta(days=k) for k in range(span)}
    return out


def load(sym, kind):
    d = pd.read_csv(REPO / f"data/cache/{sym}_1D.csv", index_col=0, parse_dates=True)
    d.index = pd.to_datetime(d.index, utc=True)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    # date de seance : bougie ES/NQ ouverte a 23:00 UTC la veille -> seance du lendemain
    sess = (d.index + pd.Timedelta(hours=2)).normalize().tz_localize(None).date
    d["sess"] = sess
    tr = pd.concat([d.High - d.Low, (d.High - d.Close.shift()).abs(), (d.Low - d.Close.shift()).abs()], axis=1).max(axis=1)
    d["atr_prev"] = tr.ewm(alpha=1 / 14, adjust=False).mean().shift()
    d["gap"] = d.Open / d.Close.shift() - 1
    d["gap_atr"] = (d.Open - d.Close.shift()) / d.atr_prev
    d["gap_pts"] = d.Open - d.Close.shift()
    d["prev_sess"] = pd.Series(sess, index=d.index).shift()
    rd = roll_days(kind, range(2007, 2027))
    d = d[~pd.Series(d.sess, index=d.index).isin(rd) & (d.index >= pd.Timestamp("2012-01-01", tz="UTC"))].dropna(subset=["gap", "atr_prev"])
    return d


def describe(lab, g, unit="%"):
    a = g.abs()
    f = (lambda v: f"{v:.2%}") if unit == "%" else (lambda v: f"{v:.2f}")
    print(f"    {lab:22s} n={len(g):4d} |ecart| median {f(a.median())} p95 {f(a.quantile(.95))} p99 {f(a.quantile(.99))} "
          f"max {f(a.max())}")


def main():
    ev = load_events()
    ev["day"] = ev.time.dt.tz_convert("Europe/Paris").dt.date
    for sym, kind, cac_k in (("FCE1", "monthly", 1.0), ("ES1", "quarterly", 0.9799), ("NQ1", "quarterly", 3.7619)):
        d = load(sym, kind)
        mon = pd.to_datetime(d.sess).dt.dayofweek == 0
        print(f"\n=== {sym} ({d.sess.iloc[0]} -> {d.sess.iloc[-1]}, {len(d)} seances hors roulement)")
        for unit, col in (("%", "gap"), ("ATR", "gap_atr")):
            print(f"  en {unit}")
            describe("lundi (week-end)", d[col][mon], unit)
            describe("mardi-vendredi", d[col][~mon], unit)
            for typ in ("NFP", "CPI", "FOMC", "BCE"):
                days = set(ev.day[ev.type == typ])
                m = pd.Series(d.prev_sess, index=d.index).isin(days)
                describe(f"lendemain {typ}", d[col][m], unit)
        pts = d.gap_pts / cac_k
        print(f"  en points CAC-eq : |ecart| du lundi > 26 pts (stop median principale) {(pts[mon].abs() > 26.4).mean():.0%}, "
              f"> 40 pts {(pts[mon].abs() > 40).mean():.0%} ; autres jours > 26 pts {(pts[~mon].abs() > 26.4).mean():.0%}")
        print(f"  lundis : ecart > 2,5 ATR (stop swing) {(d.gap_atr[mon].abs() > 2.5).sum()} ; baisse > 1 ATR {(d.gap_atr[mon] < -1).mean():.1%} ; "
              f"baisse > 2 % {(d.gap[mon] < -0.02).sum()}")
        worst = d.loc[mon].nsmallest(5, "gap")
        print("  5 pires ecarts du lundi : " + ", ".join(f"{s} {g:+.2%} ({a:+.1f} ATR)" for s, g, a in zip(worst.sess, worst.gap, worst.gap_atr)))
        worst = d.nsmallest(5, "gap")
        print("  5 pires ecarts tous jours : " + ", ".join(f"{s} {g:+.2%} ({a:+.1f} ATR)" for s, g, a in zip(worst.sess, worst.gap, worst.gap_atr)))
        if sym == "FCE1":
            # turbo de swing a levier L : desactivation si l'ecart depasse ~1/L du sous-jacent (barriere ~ financement)
            for lev in (1.5, 3, 5, 10):
                print(f"  levier {lev:>4} : lundis avec baisse > {1 / lev:.1%} : {(d.gap[mon] < -1 / lev).sum()} sur {mon.sum()}")

    # principale : trades passant un week-end, remplissage reel a l'ouverture (option gap_fill du moteur)
    t = pd.read_csv(HERE / "trades_principale.csv", parse_dates=["entry_time", "exit_time"])
    w = t[t.weekend]
    print(f"\n=== Principale : {len(w)} trades passent un week-end, {w.net_r.sum():+.1f}R (plafonne {np.minimum(w.net_r, 5).sum():+.1f}R), "
          f"stops {(w.result == 'stop').sum()} ; stop median {w.risk_cac.median():.1f} pts CAC-eq")
    print(f"  dont trades sortis le lundi : {(w.exit_time.dt.tz_convert('Europe/Paris').dt.dayofweek == 0).sum()}")


if __name__ == "__main__":
    main()
