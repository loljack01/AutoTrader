"""Live tracking WITHOUT money of the swing strategy "Repli en tendance"
(calls only), frozen on 2026-11-05 after scripts/test_swing_rsi2.py passed
its rule fixed before running (puts rejected, not tracked).

Rules (identical to test_swing_rsi2.py, imported from it, never changed):
10 cash indices, daily close > SMA(200) and RSI(2) < 10 -> call at the
close; exit at the first close > SMA(5), stop 2.5 x ATR(14) daily from the
entry (an open beyond the stop exits at the open), at most 10 days; one
position per index. R = stop distance; cost 0.05 % (base) and 0.10 %.

Live trades = entries from 2026-11-05 (that day's close included).
Verdict at 50 closed live trades (rule fixed now): worth trading with money
only if the net R at 0.10 % is > 0 AND the mean R per trade at 0.05 % is
not below half the backtest mean (+0.074R / 2 = +0.037R); otherwise the
live result is too far from the backtest and the strategy stays without
money. The backtest is checked first (reference: calls entered before
2026-10-01 = 1317 trades, +96.49R at 0.05 %).

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
from test_swing_rsi2 import COSTS, INDICES, MAX_DAYS, STOP_ATR, exit_trade, load, net, run

FREEZE = pd.Timestamp("2026-11-05", tz="UTC")
REF_END, REF = "2026-10-01", (1317, 96.49)
VERDICT_TRADES, BACKTEST_MEAN = 50, 0.074
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_swing_rsi2_trades.csv"


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

    rows, opened, signals = [], [], []
    for s, name in INDICES.items():
        d = data[s]
        a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
        c, rsi, sma200 = a[3], d.rsi2.to_numpy(), d.sma200.to_numpy()
        last = d.index[-1]
        free = -1
        for i in np.flatnonzero((c > sma200) & (rsi < 10) & (d.index >= "2025-06-01")):
            if i < free:
                continue
            j, px, risk = exit_trade(a, i, 1)
            if j is None:  # still open
                free = len(d)
                if d.index[i] >= FREEZE:
                    stop = c[i] - risk
                    lat = (c[-1] - c[i]) / risk
                    opened.append(f"  {name:14s} entree {d.index[i]:%d/%m} a {c[i]:.2f}, stop {stop:.2f}, "
                                  f"sortie a la 1re cloture > SMA5 ({a[4][-1]:.2f} ce soir), au plus tard le "
                                  f"{MAX_DAYS}e jour | cours {c[-1]:.2f}, latent {lat:+.2f}R")
                    if i == len(d) - 1:
                        signals.append(name)
                continue
            free = j
            if d.index[i] >= FREEZE:
                move = (px - c[i]) / risk
                rows.append({"marche": name, "entree": d.index[i].date(), "prix_entree": round(c[i], 2),
                             "sortie": d.index[j].date(), "prix_sortie": round(px, 2), "r_brut": round(move, 3),
                             "net_r_005": round(move - COSTS[0] * c[i] / risk, 3),
                             "net_r_010": round(move - COSTS[1] * c[i] / risk, 3)})
        info = f"close {c[-1]:.2f} SMA200 {sma200[-1]:.2f} RSI2 {rsi[-1]:.1f}"
        state = "tendance OK" if c[-1] > sma200[-1] else "sous SMA200 (pas de call)"
        print(f"  {name:14s} {last:%d/%m} {info} -> {state}")
    t = pd.DataFrame(rows, columns=["marche", "entree", "prix_entree", "sortie", "prix_sortie", "r_brut",
                                    "net_r_005", "net_r_010"])
    t.to_csv(OUT, index=False)
    print(f"\nSignaux a la cloture du jour : {', '.join(signals) if signals else 'aucun'}")
    print("Positions ouvertes (suivi sans argent) :" if opened else "Positions ouvertes : aucune")
    for line in opened:
        print(line)
    print(f"\nDepuis le {FREEZE:%d/%m/%Y} : {len(t)} trades clos, {(t.net_r_005 > 0).sum()} gagnants, "
          f"net {t.net_r_005.sum():+.2f}R a 0,05 %, {t.net_r_010.sum():+.2f}R a 0,10 %")
    if len(t) >= VERDICT_TRADES:
        good = t.net_r_010.sum() > 0 and t.net_r_005.mean() >= BACKTEST_MEAN / 2
        print(f"Verdict ({len(t)} trades) : {'PEUT PASSER EN REEL' if good else 'RESTE SANS ARGENT'}")
    else:
        print(f"Verdict a {VERDICT_TRADES} trades clos (encore {VERDICT_TRADES - len(t)})")


if __name__ == "__main__":
    main()
