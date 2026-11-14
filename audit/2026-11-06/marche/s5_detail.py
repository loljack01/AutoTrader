"""Section 5 - detail du suivi reel (entrees >= 28/10/2026, sma20) : signaux hors heures
turbo (22h-8h demande, et 21h30-8h du test 0), annonces (entree a +/-30 min, ou annonce
pendant le trade), stop < 40 pts CAC-eq ; R du suivi sans ces cas. Inclut le compte des
signaux encore ouverts du CSV officiel. Descriptif, aucune regle.

Usage: python3 /home/user/AutoTrader/audit/2026-11-06/marche/s5_detail.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = Path("/home/user/AutoTrader")


def main():
    t = pd.read_csv(HERE / "trades_principale.csv")
    L = t[t.live].copy()
    csv = pd.read_csv(REPO / "data/backtests/frozen_15m_calls_trend_trades.csv")
    op = csv[(csv.version == "sma20") & (csv.resultat == "open")]
    print(f"signaux sma20 depuis le 28/10 : {len(L)} clos + {len(op)} ouverts au CSV ({', '.join(op.marche + ' ' + op.entree_paris)})")
    h = L.hour
    crit = {"nuit 22h-8h": (h >= 22) | (h < 8), "nuit 21h30-8h (test 0)": (h >= 21.5) | (h < 8),
            "entree a +/-30 min d'une annonce": L.entry_near_event, "annonce pendant le trade": L.event_during,
            "stop < 40 pts CAC-eq": L.risk_cac < 40, "stop < 20 pts CAC-eq": L.risk_cac < 20}
    for k, m in crit.items():
        print(f"  {k:34s} {m.sum():2d}/{len(L)} trades, {L.net_r[m].sum():+5.1f}R ; reste {(~m).sum():2d} trades {L.net_r[~m].sum():+5.1f}R")
    combos = {"nuit 22h-8h + entree pres annonce": crit["nuit 22h-8h"] | crit["entree a +/-30 min d'une annonce"],
              "nuit 22h-8h + annonce (entree ou pendant) + stop<40": crit["nuit 22h-8h"] | L.entry_near_event | L.event_during | crit["stop < 40 pts CAC-eq"],
              "nuit 22h-8h + entree pres annonce + stop<20": crit["nuit 22h-8h"] | L.entry_near_event | crit["stop < 20 pts CAC-eq"]}
    for k, m in combos.items():
        x = L[~m]
        print(f"  RETIRE {k:52s} : retires {m.sum():2d}, reste {len(x):2d} trades {x.net_r.sum():+5.1f}R (1 pt) {x.net_r3.sum():+5.1f}R (3 pt)")
    from events import load_events
    tm = load_events().time.dt.tz_convert("UTC")
    et = pd.to_datetime(t.entry_time)
    for w in (15, 30):
        m = np.array([bool((abs((tm - a).dt.total_seconds()) <= w * 60).any()) for a in et])
        print(f"  entree a +/-{w} min d'une annonce (regle SPEC 3.5, jamais appliquee par le moteur) : historique {m.sum()} trades "
              f"{t.net_r[m].sum():+.1f}R ; suivi {(m & t.live).sum()}")
    print(f"  stop CAC-eq du suivi : mediane {L.risk_cac.median():.1f}, min {L.risk_cac.min():.1f}, max {L.risk_cac.max():.1f}")
    print(f"  ouverts : stops CAC-eq " + ", ".join(f"{r.marche} {abs(r.entree - r.stop) / k:.0f}" for (_, r), k in
          zip(op.iterrows(), [{"CAC 40": 1, "DAX": 3.2397, "FTSE 100": 1.362, "SMI": 1.7999}[m] for m in op.marche])))


if __name__ == "__main__":
    main()
