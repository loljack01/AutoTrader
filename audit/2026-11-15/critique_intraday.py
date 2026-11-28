"""Audit critique de l'intraday du 15/11/2026 (demande de l'utilisateur : "Refais audit et sois
critique sur l'intraday"). AUCUNE regle nouvelle n'est testee (regle 29 : un nouveau test par
mois) : le script relit les trades des strategies intraday deja figees, avec leurs propres
fonctions, et les decoupe (frais, periodes, heures, duree, sens, marche, mois, plus gros trades).

Deux periodes pour la principale et sa forme executable en turbo (D) : avant le 28/10/2026
(historique, qui a servi a construire les regles) et depuis le 28/10 (suivi sans argent).

Usage : python3 -W ignore audit/2026-11-15/critique_intraday.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
import frozen_15m_oil as oil
import frozen_15m_single_sweep as single
import frozen_gap_continuation as gap
from frozen_15m_calls_trend import FREEZE_START, MARKETS, run as run_main
from frozen_15m_variants import run as run_variant

START = pd.Timestamp(FREEZE_START, tz="UTC")
D_KW = {"entry_hours": (8, 21.5), "session_exit": 21.75}
SEQ_PASS = 72.0


def closed(t):
    return t[~t.result.isin(["open", "pending", "missed"])]


def line(t):
    r = closed(t).net_r.to_numpy(float)
    if not len(r):
        return "0 trade"
    w, l = r[r > 0], r[r <= 0]
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    t_stat = r.mean() / (sd / np.sqrt(len(r))) if sd > 0 else 0.0
    cum = np.cumsum(closed(t).sort_values("exit_time").net_r.to_numpy(float))
    dd = (cum - np.maximum.accumulate(np.maximum(cum, 0))).min()
    return (f"{len(r):4d} trades, {len(w) / len(r):4.0%} gagnants, net {r.sum():+7.2f}R, moy {r.mean():+.3f}R, t {t_stat:+.2f}, "
            f"plafond 5R {np.minimum(r, 5).sum():+7.2f}R, pire creux {dd:+.1f}R")


def boot(r, n=5000, seed=0):
    rng = np.random.default_rng(seed)
    m = rng.choice(r, size=(n, len(r)), replace=True).mean(axis=1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5), float((m <= 0).mean())


def main():
    now = pd.Timestamp.now(tz="UTC")
    data = {s: bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now) for s in MARKETS}
    first = {MARKETS[s][0]: d.index[0] for s, d in data.items()}
    runs = {}
    for s, d in data.items():
        for cost in (1.0, 3.0):
            for name, t in (("principale", run_main(s, d, 20, cost)), ("D", run_variant(s, d, cost, **D_KW)),
                            ("simple balayage", single.run(s, d, cost)),
                            ("ecart continue", gap.trades(s, d, cost * MARKETS[s][1]))):
                t = t.assign(marche=MARKETS[s][0])
                if "side" not in t.columns:
                    t["side"] = np.where(t["take"] > t["entry"], 1, -1)
                runs.setdefault((name, cost), []).append(t)
    for s in oil.OIL:
        d = bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now)
        for cost in (1.0, 3.0):
            runs.setdefault(("petrole", cost), []).append(oil.run(s, d, cost).assign(marche=oil.OIL[s][0]))
    runs = {k: pd.concat(v, ignore_index=True) for k, v in runs.items()}
    hist = lambda t: t[t.entry_time < START]
    live = lambda t: t[t.entry_time >= START]
    last = max(d.index[-1] for d in data.values()) + pd.Timedelta(minutes=15)
    print(f"Donnees 15 minutes jusqu'au {last.tz_convert('Europe/Paris'):%d/%m/%Y %H:%M} (Paris) ; historique depuis "
          f"{min(first.values()).tz_convert('Europe/Paris'):%d/%m/%Y} (CAC) a {max(first.values()).tz_convert('Europe/Paris'):%d/%m/%Y} selon le marche")

    print("\n== 1. Tableau de bord : tout l'intraday en suivi, depuis le debut de chaque suivi ==")
    starts = {"principale": START, "D": pd.Timestamp("2026-11-06", tz="UTC"),
              "simple balayage": pd.Timestamp(single.FREEZE_START, tz="UTC"),
              "ecart continue": pd.Timestamp(gap.FREEZE_START, tz="UTC"), "petrole": pd.Timestamp(oil.FREEZE_START, tz="UTC")}
    for name, st in starts.items():
        for cost in (1.0, 3.0):
            t = runs[name, cost]
            print(f"  {name:16s} depuis le {st:%d/%m} a {cost:.0f} pt : {line(t[t.entry_time >= st])}")
    p2 = pd.read_csv(ROOT / "data" / "backtests" / "frozen_p2_trades.csv")
    p2 = p2[p2.resultat != "open"]
    print(f"  P2 (rejet du plus haut / plus bas de la veille) depuis le 09/11 : {len(p2)} trades, net {p2.net_r_1pt.sum():+.2f}R a 1 pt, "
          f"{p2.net_r_3pt.sum():+.2f}R a 3 pts")

    for name in ("principale", "D"):
        print(f"\n== 2. {name} : les chiffres de base ==")
        for cost in (1.0, 3.0):
            t = runs[name, cost]
            print(f"  {cost:.0f} pt, avant le 28/10  : {line(hist(t))}")
            print(f"  {cost:.0f} pt, depuis le 28/10 : {line(live(t))}")
            for label, f in (("avant le 28/10", hist), ("depuis le 28/10", live)):
                r = closed(f(t)).net_r.to_numpy(float)
                lo, hi, p0 = boot(r)
                w, l = r[r > 0], r[r <= 0]
                be = -l.mean() / (w.mean() - l.mean())
                print(f"      {label} : moyenne par trade entre {lo:+.3f}R et {hi:+.3f}R (intervalle a 95 % par reechantillonnage), "
                      f"probabilite d'une moyenne <= 0 : {p0:.0%} ; gain moyen {w.mean():+.2f}R, perte moyenne {l.mean():+.2f}R, "
                      f"reussite necessaire {be:.0%}, obtenue {len(w) / len(r):.0%}")

    t1, t3 = runs["principale", 1.0], runs["principale", 3.0]
    print("\n== 3. Principale : d'ou vient le resultat (frais 1 pt) ==")
    for label, f in (("avant le 28/10", hist), ("depuis le 28/10", live)):
        c = closed(f(t1)).sort_values("net_r", ascending=False)
        r = c.net_r.to_numpy(float)
        print(f"  {label} : total {r.sum():+.1f}R ; les 5 meilleurs trades {r[:5].sum():+.1f}R ; les 10 meilleurs {r[:10].sum():+.1f}R ; "
              f"sans les 5 meilleurs {r[5:].sum():+.1f}R ; sans les 10 meilleurs {r[10:].sum():+.1f}R ; trades au-dela de +5R : "
              f"{int((r > 5).sum())} ({r[r > 5].sum():+.1f}R)")
        ph = c.entry_time.dt.tz_convert("Europe/Paris")
        h = ph.dt.hour + ph.dt.minute / 60
        day = (c.exit_time.dt.tz_convert("Europe/Paris").dt.date == ph.dt.date)
        hours = (c.exit_time - c.entry_time).dt.total_seconds() / 3600
        turbo = (h >= 8) & (h < 21.5)
        print(f"      entrees 8h-21h30 (heures des turbos) : {line(c[turbo])}")
        print(f"      entrees 21h30-8h (turbos fermes)     : {line(c[~turbo])}")
        print(f"      sortis le jour meme                  : {line(c[day])}")
        print(f"      gardes au moins une nuit             : {line(c[~day])}")
        print(f"      duree : mediane {hours.median():.1f} h ; part des trades de plus de 24 h {float((hours > 24).mean()):.0%}")
        print(f"      calls : {line(c[c['take'] > c.entry])}")
        print(f"      puts  : {line(c[c['take'] < c.entry])}")
    c = closed(t1)
    print("  par marche (toute la periode, 1 pt puis 3 pts) :")
    c3 = closed(t3)
    for m in sorted(c.marche.unique()):
        a, b = c[c.marche == m].net_r, c3[c3.marche == m].net_r
        print(f"      {m:14s} {len(a):3d} trades {a.sum():+7.2f}R | a 3 pts {len(b):3d} trades {b.sum():+7.2f}R")
    pos1 = int((c.groupby("marche").net_r.sum() > 0).sum())
    pos3 = int((c3.groupby("marche").net_r.sum() > 0).sum())
    print(f"      marches positifs : {pos1} sur 10 a 1 pt, {pos3} sur 10 a 3 pts")
    print("  par mois de sortie (1 pt) : " + ", ".join(
        f"{k} {v:+.1f}R" for k, v in c.groupby(c.exit_time.dt.tz_convert('Europe/Paris').dt.strftime('%m/%Y')).net_r.sum().sort_index(
            key=lambda x: pd.to_datetime(x, format='%m/%Y')).items()))

    print("\n== 4. Rarete des signaux (principale, 1 pt) ==")
    allt = t1.assign(jour=t1.entry_time.dt.tz_convert("Europe/Paris").dt.date)
    for s, d in data.items():
        m = MARKETS[s][0]
        days = pd.Series(d.index.tz_convert("Europe/Paris").date).nunique()
        x = allt[allt.marche == m]
        print(f"      {m:14s} {days:3d} jours de cotation, {len(x):3d} trades, jours avec au moins un trade {x.jour.nunique() / days:4.0%}, "
              f"un trade tous les {days / max(len(x), 1):.1f} jours")

    print("\n== 5. En euros (ordre de 500 EUR, levier 2,8) et regle de passage ==")
    stop = (t1.entry - t1.stop).abs() / t1.entry
    eur = 500 * 2.8 * stop.median()
    for label, f in (("avant le 28/10", hist), ("depuis le 28/10", live)):
        for name in ("principale", "D"):
            a, b = closed(f(runs[name, 1.0])).net_r, closed(f(runs[name, 3.0])).net_r
            print(f"  {name:10s} {label} : {len(a)} ordres ({len(a) * 500 / 1000:.0f} 000 EUR d'ordres passes), "
                  f"{a.sum() * eur:+.0f} EUR a 1 pt, {b.sum() * eur:+.0f} EUR a 3 pts (1R = {eur:.1f} EUR)")
    print(f"  regle de passage (+{SEQ_PASS:.0f}R plafonnes a un controle de 100 en 100 trades, 600 au plus) : moyenne plafonnee necessaire par trade "
          + ", ".join(f"{SEQ_PASS / n:.2f}R a {n}" for n in (100, 200, 300, 400, 500, 600)))
    for name, cost in (("principale", 1.0), ("D", 3.0)):
        for label, f in (("avant le 28/10", hist), ("depuis le 28/10", live)):
            r = closed(f(runs[name, cost])).net_r.to_numpy(float)
            print(f"      {name} a {cost:.0f} pt, {label} : moyenne plafonnee obtenue {np.minimum(r, 5).mean():+.3f}R par trade")


if __name__ == "__main__":
    main()
