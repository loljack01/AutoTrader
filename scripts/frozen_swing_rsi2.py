"""Live tracking of the swing strategy "Repli en tendance" (calls only),
frozen on 2026-11-05 after scripts/test_swing_rsi2.py passed its rule fixed
before running (puts rejected, not tracked).

Rules (identical to test_swing_rsi2.py, imported from it, never changed):
10 cash indices, daily close > SMA(200) and RSI(2) < 10 -> call at the
close; exit at the first close > SMA(5), stop 2.5 x ATR(14) daily from the
entry (an open beyond the stop exits at the open), at most 10 days; one
position per index. R = stop distance; cost 0.05 % (base) and 0.10 %.
The backtest is checked first (reference: calls entered before 2026-10-01
= 1317 trades, +96.49R at 0.05 %).

Amended on 2026-11-05 evening (before any live trade), at the user's
request, after the working group's review and two confirmations made the
SAME day: out of time on 1991-2011 (test_swing_rsi2_1990.py, 1613 trades,
+0.066R/trade, weekly t 2.72) and the 5-position cap
(test_swing_rsi2_cap5.py, 85-86 % of the edge kept in both periods).
The edge is considered established by 35 years of history; the live phase
now checks the EXECUTION, not the edge (50 trades cannot test the edge:
44 % false positives). Capital 5 000 EUR.
  book          at most 5 open positions; signals of the same close by
                lowest RSI(2); a signal finding 5 positions open is skipped
  size          phase 1 (the first 30 live trades): 0.5 % of the capital
                per trade (25 EUR at the stop); phase 2: up to 1 % only if
                the execution check passes and the user agrees
                (recommended 0.5-0.75 %: the worst historical drawdown is
                -40R)
  product       exposure = risk EUR x price / stop distance (about 860 EUR
                for 25 EUR); one order >= 500 EUR: turbo of leverage
                exposure / 500 (about 1.7), or an ETF / tracker
  execution     every real fill is written in data/journal_swing.csv
  check         (indice, entree YYYY-MM-DD, prix_entree, sortie, prix_sortie);
                at 30 closed live trades phase 2 is allowed only if 100 %
                of the signals were taken as given and the mean slippage
                (real minus model, in R) is >= -0.03R
  brake         if the cumulative live net R (0.05 %) reaches -10R, stop
                and review (5th percentile at 50 trades if the edge is real)

Amended on 2026-11-06 (still before any live trade), at the user's request
("applique D"): capital raised to 10 000 EUR. The trade rule, the 5-position
cap, the brake and the execution check are unchanged. The risk per trade is
NOT doubled: the user's loss tolerance (500 EUR over 3 months, given on
06/11) and the worst 3-month period of the capped swing (-13R, 2012-2026)
cap it at about 38 EUR. Phase 1 stays at 25 EUR (0.25 % of 10 000 EUR);
phase 2 up to 0.375 % (37.5 EUR), more only if the user raises the
tolerance. The larger capital lets the 5 positions be held with little or
no leverage (about 700-900 EUR of exposure each, ETF/tracker or turbo
leverage <= 1.5), which limits the knock-out risk of a gap at the open.

Tooling amended on 2026-11-06 after the full audit (trade rule, book, size,
brake and execution check UNCHANGED): the journal is checked for duplicates,
lines that are not a signal of the model (out of system), signals executed
although the model skipped them, and prices far below the model's (a turbo
price instead of the index level: the journal must hold the INDEX level at
the time of the order, otherwise the slippage check is wrong).

Amended on 2026-11-07 (still before any live trade), user's choice: every
order is 500 EUR in the call turbo with the lowest leverage available
(about 2.8 at Boursomarkets), so 1R in euros = 500 x 2.8 x stop distance,
about 45 EUR (0.45 % of 10 000 EUR) instead of 25 EUR. Rule, book, brake
(-10R) and execution check unchanged; no phase-2 increase on top of it.

Usage: python scripts/frozen_swing_rsi2.py [tool-results JSON files of the
10 cash indices, 1D, any format] (merged into data/cache first)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from other_markets_test import ingest
from test_swing_rsi2 import COSTS, INDICES, MAX_DAYS, exit_trade, load, net, run

FREEZE = pd.Timestamp("2026-11-05", tz="UTC")
REF_END, REF = "2026-10-01", (1317, 96.49)
CAP, CAPITAL, PHASE1_PCT, PHASE1_TRADES, BRAKE, MAX_SLIP = 5, 10000.0, 0.0045, 30, -10.0, -0.03
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "backtests" / "frozen_swing_rsi2_trades.csv"
JOURNAL = ROOT / "data" / "journal_swing.csv"


def main():
    for f in sys.argv[1:]:
        ingest(f)
    data = {s: load(s) for s in INDICES}
    n, tot = 0, 0.0
    for s in INDICES:
        t = run(data[s], 1)
        t = t[t.entry < REF_END]
        n, tot = n + len(t), tot + net(t, COSTS[0]).sum()
    ok = n == REF[0] and abs(tot - REF[1]) < 0.05
    print(f"Controle de reference : {n} trades, {tot:+.2f}R -> {'OK' if ok else 'DIFFERENT'}")

    cands = []
    for s, name in INDICES.items():
        d = data[s]
        a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
        c, rsi, sma200 = a[3], d.rsi2.to_numpy(), d.sma200.to_numpy()
        free = -1
        for i in np.flatnonzero((c > sma200) & (rsi < 10) & (d.index >= "2025-06-01")):
            if i < free:
                continue
            j, px, risk = exit_trade(a, i, 1)
            free = len(d) if j is None else j
            if d.index[i] >= FREEZE:
                cands.append({"marche": name, "entree": d.index[i].normalize(), "rsi2": rsi[i], "prix_entree": c[i],
                              "risque_pts": risk, "sortie": None if j is None else d.index[j].normalize(),
                              "prix_sortie": px, "cours": c[-1], "sma5": a[4][-1], "dernier": d.index[-1]})
        print(f"  {name:14s} {d.index[-1]:%d/%m} close {c[-1]:.2f} SMA200 {sma200[-1]:.2f} RSI2 {rsi[-1]:.1f} -> "
              f"{'tendance OK' if c[-1] > sma200[-1] else 'sous SMA200 (pas de call)'}")

    book, rows = [], []
    for x in sorted(cands, key=lambda x: (x["entree"], x["rsi2"])):
        book = [p for p in book if p["sortie"] is None or p["sortie"] > x["entree"]]
        taken = len(book) < CAP
        if taken:
            book.append(x)
        move = None if x["sortie"] is None else (x["prix_sortie"] - x["prix_entree"]) / x["risque_pts"]
        frac = x["prix_entree"] / x["risque_pts"]
        rows.append({"marche": x["marche"], "entree": x["entree"].date(), "prix_entree": round(x["prix_entree"], 2),
                     "stop": round(x["prix_entree"] - x["risque_pts"], 2), "pris": taken,
                     "sortie": None if x["sortie"] is None else x["sortie"].date(),
                     "prix_sortie": None if x["sortie"] is None else round(x["prix_sortie"], 2),
                     "r_brut": None if move is None else round(move, 3),
                     "net_r_005": None if move is None else round(move - COSTS[0] * frac, 3),
                     "net_r_010": None if move is None else round(move - COSTS[1] * frac, 3)})
        if x["entree"] == x["dernier"].normalize():
            print(f"\n  SIGNAL a la cloture du jour : {x['marche']} {'A PRENDRE' if taken else 'IGNORE (5 positions ouvertes)'}"
                  f", entree {x['prix_entree']:.2f}")
    t = pd.DataFrame(rows)
    t.to_csv(OUT, index=False)
    risk_eur = CAPITAL * PHASE1_PCT
    opened = [x for x in book if x["sortie"] is None]
    print(f"\nPositions ouvertes (limite {CAP}) : {len(opened) if opened else 'aucune'}")
    for x in opened:
        expo = risk_eur * x["prix_entree"] / x["risque_pts"]
        print(f"  {x['marche']:14s} entree {x['entree']:%d/%m} a {x['prix_entree']:.2f}, stop {x['prix_entree'] - x['risque_pts']:.2f}, "
              f"sortie a la 1re cloture > SMA5 ({x['sma5']:.2f} ce soir) ou au {MAX_DAYS}e jour | cours {x['cours']:.2f}, "
              f"latent {(x['cours'] - x['prix_entree']) / x['risque_pts']:+.2f}R | {risk_eur:.0f} EUR de risque : exposition "
              f"{expo:.0f} EUR, levier pour 500 EUR {expo / 500:.1f}")
    closed = t[t.pris & t.net_r_005.notna()] if len(t) else t
    cum = closed.net_r_005.sum() if len(closed) else 0.0
    print(f"\nDepuis le 05/11 (positions prises) : {len(closed)} trades clos, {(closed.net_r_005 > 0).sum() if len(closed) else 0} "
          f"gagnants, net {cum:+.2f}R a 0,05 %, {closed.net_r_010.sum() if len(closed) else 0:+.2f}R a 0,10 % "
          f"(soit {cum * risk_eur:+.0f} EUR a {risk_eur:.0f} EUR par trade)")
    if cum <= BRAKE:
        print(f"  FREIN : {cum:+.1f}R <= {BRAKE:+.0f}R -> arret et revision")
    if JOURNAL.exists():
        try:
            jr = pd.read_csv(JOURNAL, parse_dates=["entree"])
        except Exception:
            jr = pd.DataFrame(columns=["marche", "entree", "prix_entree", "sortie", "prix_sortie"])
        # tooling checks added on 06/11/2026 after the full audit (reporting only, rules unchanged)
        if len(jr):
            dup = jr.duplicated(["marche", "entree"], keep=False)
            if dup.any():
                print(f"  ATTENTION journal : {int(dup.sum())} lignes en double (meme indice et meme date) -> a corriger")
            ref = (t.assign(entree=pd.to_datetime(t.entree))[["marche", "entree", "prix_entree", "pris"]] if len(t) else
                   pd.DataFrame({"marche": pd.Series(dtype=str), "entree": pd.Series(dtype="datetime64[ns]"),
                                 "prix_entree": pd.Series(dtype=float), "pris": pd.Series(dtype=bool)}))
            if True:
                mm = jr.merge(ref, on=["marche", "entree"], how="left", suffixes=("", "_modele"))
                out = mm[mm.prix_entree_modele.isna()]
                for x in out.itertuples():
                    print(f"  ATTENTION journal : {x.marche} {x.entree:%d/%m} n'est pas un signal du modele "
                          f"(hors systeme ? a noter dans data/journal_hors_systeme.csv)")
                low = mm[mm.prix_entree < 0.2 * mm.prix_entree_modele]
                for x in low.itertuples():
                    print(f"  ATTENTION journal : {x.marche} {x.entree:%d/%m} prix {x.prix_entree} tres loin du modele "
                          f"({x.prix_entree_modele}) : prix de turbo ? Noter le COURS DE L'INDICE au moment de l'ordre")
                skipped = mm[mm.pris == False]  # noqa: E712
                for x in skipped.itertuples():
                    print(f"  ATTENTION journal : {x.marche} {x.entree:%d/%m} execute alors que le modele l'ignore "
                          f"(5 positions) -> hors systeme")
    if JOURNAL.exists() and len(closed):
        j = pd.read_csv(JOURNAL, parse_dates=["entree"])
        m = closed.assign(entree=pd.to_datetime(closed.entree)).merge(j, on=["marche", "entree"], how="left",
                                                                         suffixes=("", "_reel"))
        done = m.prix_sortie_reel.notna()
        slip = ((m.prix_sortie_reel - m.prix_entree_reel) - (m.prix_sortie - m.prix_entree))[done] / (
            (m.prix_entree - m.stop)[done])
        print(f"  Execution : {done.sum()}/{len(m)} trades au journal, glissement moyen "
              f"{slip.mean() if done.any() else 0:+.3f}R (limite {MAX_SLIP:+.2f}R)")
        if len(closed) >= PHASE1_TRADES:
            good = done.all() and slip.mean() >= MAX_SLIP
            print(f"  Controle d'execution ({len(closed)} trades) : {'PHASE 2 POSSIBLE' if good else 'RESTER EN PHASE 1'}")
    print(f"Phase 1 : {risk_eur:.0f} EUR de risque par trade, controle d'execution a {PHASE1_TRADES} trades "
          f"(encore {max(0, PHASE1_TRADES - len(closed))})")


if __name__ == "__main__":
    main()
