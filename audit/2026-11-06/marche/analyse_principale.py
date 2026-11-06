"""Audit marche 06/11/2026 - sections 1, 2 et 5 (principale), DESCRIPTIF.
Lit trades_principale.csv (produit par main_trades.py). Pour chaque decoupage :
n, R moyen (1 pt), R moyen plafonne a +5R, total, t du groupe, t de Welch groupe
contre le reste, et p de permutation (10 000 tirages, graine 0) de l'ecart des moyennes
plafonnees, a lire avec la correction de Bonferroni du nombre de groupes.

Usage: python3 /home/user/AutoTrader/audit/2026-11-06/marche/analyse_principale.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RNG = np.random.default_rng(0)


def perm_p(x, rest, draws=10000):
    allv = np.r_[x, rest]
    obs = abs(x.mean() - rest.mean())
    n = len(x)
    cnt = 0
    for _ in range(draws):
        p = RNG.permutation(allv)
        cnt += abs(p[:n].mean() - p[n:].mean()) >= obs
    return (cnt + 1) / (draws + 1)


def table(t, col, label, order=None):
    print(f"\n--- {label}")
    groups = order if order is not None else sorted(t[col].dropna().unique())
    k = len(groups)
    for g in groups:
        m = t[col] == g
        x, rest = t.net_r[m].to_numpy(), t.net_r[~m].to_numpy()
        xc, rc = np.minimum(x, 5), np.minimum(rest, 5)
        if len(x) < 2:
            print(f"  {str(g):22s} n={len(x):3d}")
            continue
        tg = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
        p = perm_p(xc, rc, 4000)
        print(f"  {str(g):22s} n={len(x):3d} moy {x.mean():+.3f}R plaf5 {xc.mean():+.3f}R total {x.sum():+6.1f}R "
              f"(plaf {xc.sum():+6.1f}) gagn {np.mean(x > 0):.0%} t={tg:+.2f} | p perm (plaf, vs reste) {p:.3f}"
              f"{'  *' if p < 0.05 / k else ''}")
    print(f"  (* = p < 0,05/{k}, Bonferroni)")


def main():
    t = pd.read_csv(HERE / "trades_principale.csv", parse_dates=["entry_time", "exit_time", "sweep_time"])
    print(f"Principale sma20, {len(t)} trades clos, 1 pt CAC-eq : moy {t.net_r.mean():+.3f}R, total {t.net_r.sum():+.1f}R, "
          f"plafonne 5R {np.minimum(t.net_r, 5).sum():+.1f}R ; 3 pt {t.net_r3.sum():+.1f}R")
    # ---------- section 1
    h = t.hour
    t["tranche"] = np.select([(h >= 22) | (h < 8), h < 9, h < 12, h < 15.5, h < 17.5], ["1 nuit 22h-8h", "2 8h-9h", "3 9h-12h", "4 12h-15h30", "5 15h30-17h30"], "6 17h30-22h")
    table(t, "tranche", "Tranche horaire Paris (entree)")
    t["jour"] = t.weekday.map(dict(enumerate(["1 lun", "2 mar", "3 mer", "4 jeu", "5 ven", "6 sam", "7 dim"])))
    table(t, "jour", "Jour de la semaine (entree, Paris)")
    table(t, "market", "Marche")
    table(t, "side", "Sens")
    t["duree"] = pd.cut(t.hold_h, [0, 2, 8, 24, 1e9], right=False, labels=["1 <2h", "2 2-8h", "3 8-24h", "4 >24h"]).astype(str)
    table(t, "duree", "Duree de detention")
    t["we"] = np.where(t.weekend, "passe un week-end", "sans week-end")
    table(t, "we", "Week-end")
    t["atr_regime"] = np.where(t.atr_rank >= 0.5, "ATR j haut (>= mediane 1 an)", "ATR j bas")
    table(t, "atr_regime", "Regime ATR journalier du future (rang sur 250 j, veille)")
    t["vix_regime"] = np.where(t.vix_prev >= 20, "VIX veille >= 20", "VIX veille < 20")
    table(t, "vix_regime", f"VIX de la veille (mediane des trades {t.vix_prev.median():.1f})")
    t["vix_med"] = np.where(t.vix_prev >= t.vix_prev.median(), "VIX >= mediane", "VIX < mediane")
    table(t, "vix_med", "VIX veille, coupure a la mediane")
    t["ann"] = np.where(t.event_day, "jour d'annonce", "autre jour")
    table(t, "ann", "Jour d'annonce majeure (NFP, CPI, FOMC, BCE ; calendrier TradingView)")
    for typ in ("NFP", "CPI", "FOMC", "BCE"):
        m = t["day_" + typ]
        print(f"    {typ}: n={m.sum()} moy {t.net_r[m].mean():+.3f}R total {t.net_r[m].sum():+.1f}R")
    t["pend"] = np.where(t.event_during, "annonce pendant le trade", "aucune")
    table(t, "pend", "Annonce pendant le trade")

    # ---------- section 2
    print("\n=== SECTION 2 : lecture graphique")
    b = t.sweep_broken_all.astype(str).str.lower() == "true"
    a = t.sweep_broken_any.astype(str).str.lower() == "true"
    print(f"balayage sur niveau deja casse en cloture : tous les pools balayes {b.mean():.1%} ({b.sum()}/{len(t)}), "
          f"au moins un {a.mean():.1%} ({a.sum()})")
    for lab, m in (("deja casse (tous)", b), ("niveau intact", ~a)):
        x = t.net_r[m]
        print(f"  {lab:20s} n={m.sum()} moy {x.mean():+.3f}R plaf {np.minimum(x, 5).mean():+.3f}R total {x.sum():+.1f}R")
    print(f"  p perm (plafonne) casse vs intact : {perm_p(np.minimum(t.net_r[b], 5).to_numpy(), np.minimum(t.net_r[~a], 5).to_numpy()):.3f}")
    print(f"  par sens : " + ", ".join(f"{s} {b[t.side == s].mean():.0%}" for s in ("call", "put")))
    print(f"  suivi (>=28/10) : {b[t.live].mean():.0%} ; reference : {b[~t.live].mean():.0%}")
    q = t.risk_atr15
    print(f"distance entree-stop en ATR15m (14) : moyenne {q.mean():.2f}, mediane {q.median():.2f}, "
          f"p10 {q.quantile(.1):.2f}, p90 {q.quantile(.9):.2f} ; part au plancher 2 ATR (<= 2,01) {(q <= 2.01).mean():.0%}")
    print(f"  en points CAC-eq : mediane {t.risk_cac.median():.1f}, p10 {t.risk_cac.quantile(.1):.1f}, p90 {t.risk_cac.quantile(.9):.1f}")
    take = t.result == "take"
    print(f"R:R vise (brut) : moyenne {t.rr_target.mean():.2f}, mediane {t.rr_target.median():.2f} ; "
          f"R:R obtenu : moy {t.net_r.mean():+.3f}R ; taux de cible {take.mean():.1%} ; "
          f"seuil de rentabilite implicite 1/(1+RR median) {1 / (1 + t.rr_target.median()):.1%}")
    t["rr_bin"] = pd.cut(t.rr_target, [0, 2, 3, 5, 10, 1e9], right=False, labels=["1 1,3-2", "2 2-3", "3 3-5", "4 5-10", "5 >10"]).astype(str)
    for g, x in t.groupby("rr_bin"):
        exp = 1 / (1 + x.rr_target.mean())
        print(f"  cible {g:8s} n={len(x):3d} atteinte {np.mean(x.result == 'take'):5.1%} (seuil {exp:.0%}) "
              f"moy {x.net_r.mean():+.3f}R total {x.net_r.sum():+.1f}R, detention mediane {x.hold_h.median():.1f} h")
    big = t[t.net_r > 5].copy()
    print(f"\ngagnants > 5R : {len(big)} trades, {big.net_r.sum():+.1f}R sur {t.net_r.sum():+.1f}R "
          f"(reste {t.net_r.sum() - big.net_r.sum():+.1f}R)")
    print(f"  tranche : {big.tranche.value_counts().to_dict()}")
    print(f"  sens : {big.side.value_counts().to_dict()} ; tendance SMA20 haussiere {big.above20.mean():.0%} "
          f"(tous {t.above20.mean():.0%}) ; au-dessus SMA50 {big.above50.mean():.0%} (tous {t.above50.mean():.0%})")
    print(f"  stop CAC-eq median {big.risk_cac.median():.1f} (tous {t.risk_cac.median():.1f}) ; detention mediane "
          f"{big.hold_h.median():.1f} h (tous {t.hold_h.median():.1f}) ; week-end {big.weekend.mean():.0%} (tous {t.weekend.mean():.0%})")
    cols = ["market", "side", "entry_paris", "exit_paris", "risk_cac", "rr_target", "net_r", "above20", "hold_h"]
    print(big[cols].sort_values("net_r", ascending=False).round(1).to_string(index=False))

    # ---------- section 5 : suivi reel
    print("\n=== SECTION 5 : suivi reel (entrees >= 28/10, trades clos du cache)")
    L = t[t.live].copy()
    L["hors_turbo"] = (L.hour >= 21.5) | (L.hour < 8)
    L["annonce"] = L.entry_near_event | L.event_during
    L["stop40"] = L.risk_cac < 40
    print(f"suivi : {len(L)} trades clos, total {L.net_r.sum():+.1f}R (1 pt), {L.net_r3.sum():+.1f}R (3 pt), moy {L.net_r.mean():+.3f}R")
    for c, lab in (("hors_turbo", "entree hors heures turbo (21h30-8h)"), ("annonce", "annonce +/-30 min de l'entree ou pendant le trade"),
                   ("stop40", "stop < 40 pts CAC-eq")):
        m = L[c]
        print(f"  {lab:52s} {m.sum():2d} trades, {L.net_r[m].sum():+.1f}R")
    m = L.hors_turbo | L.annonce | L.stop40
    print(f"  au moins un des trois : {m.sum()} trades ({L.net_r[m].sum():+.1f}R) ; RESTE {(~m).sum()} trades, "
          f"{L.net_r[~m].sum():+.1f}R a 1 pt, {L.net_r3[~m].sum():+.1f}R a 3 pt, moy {L.net_r[~m].mean():+.3f}R")
    m2 = L.hors_turbo | L.stop40
    print(f"  sans le critere annonce : retires {m2.sum()}, reste {(~m2).sum()} trades {L.net_r[~m2].sum():+.1f}R")
    print(f"  (historique complet, meme filtre descriptif : reste "
          f"{(~(((t.hour >= 21.5) | (t.hour < 8)) | t.entry_near_event | t.event_during | (t.risk_cac < 40))).sum()} trades, "
          f"{t.net_r[~(((t.hour >= 21.5) | (t.hour < 8)) | t.entry_near_event | t.event_during | (t.risk_cac < 40))].sum():+.1f}R)")
    print(L[["market", "side", "entry_paris", "risk_cac", "net_r", "hors_turbo", "annonce", "stop40"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
