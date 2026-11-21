"""Section 4 - principale : effet d'un remplissage realiste quand une bougie 15m ouvre
au-dela du stop ou de la cible (option d'audit existante gap_fill=True du moteur ; les
regles ne changent pas, seul le prix de sortie change). Compare, trade par trade, au R du
moteur officiel (trades_principale.csv), selon que le trade passe une nuit / un week-end.

Usage: PYTHONDONTWRITEBYTECODE=1 python3 /home/user/AutoTrader/audit/2026-11-06/marche/gapfill_principale.py
"""
import sys
from pathlib import Path

REPO = Path("/home/user/AutoTrader")
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
import frozen_15m_calls_trend as fc
from ma_grid_test import trend_up

HERE = Path(__file__).resolve().parent
NOW = pd.Timestamp("2026-11-06 07:00", tz="UTC")


def main():
    t = pd.read_csv(HERE / "trades_principale.csv", parse_dates=["entry_time", "exit_time"])
    out = []
    for sym, (name, k) in fc.MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(sym, "15m"), "15m", NOW)
        d.index = pd.to_datetime(d.index, utc=True)
        d = d[~d.index.duplicated(keep="last")].sort_index()
        bt.ROUND_TRIP_COST, bt.MIN_RISK_ATR_MULT, bt.STOP_MARGIN = 1.0 * k, 2.0, 8.0 * k
        bt.SWING_N, bt.MIN_NET_RR, bt.CHOCH_WINDOW = 2, 1.3, pd.Timedelta(hours=4)
        up = trend_up(sym, d, "SMA", 20)
        g = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up, gap_fill=True),
                       bt.backtest(d, True, False, direction="sell", gap_fill=True)])
        out.append(g[g.result != "open"].assign(symbol=sym))
    g = pd.concat(out)[["symbol", "entry_time", "net_r"]].rename(columns={"net_r": "r_gapfill"})
    m = t.merge(g, on=["symbol", "entry_time"], how="left")
    print(f"appariement : {m.r_gapfill.notna().sum()}/{len(t)} trades")
    m["d"] = m.r_gapfill - m.net_r
    for lab, x in (("tous", m), ("passe un week-end", m[m.weekend]), ("sans week-end", m[~m.weekend])):
        print(f"  {lab:18s} n={len(x):3d} R officiel {x.net_r.sum():+6.1f} | R avec remplissage a l'ouverture {x.r_gapfill.sum():+6.1f} "
              f"| ecart {x.d.sum():+.1f}R ; pire trade {x.r_gapfill.min():+.2f}R")
    w = m[m.weekend & (m.result == "stop")]
    print(f"  stops des trades de week-end : {len(w)}, perte moyenne {w.r_gapfill.mean():+.2f}R avec remplissage (officiel {w.net_r.mean():+.2f}R)")


if __name__ == "__main__":
    main()
