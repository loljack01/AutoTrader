"""Cumul plafonné 5R (1pt) des trades suivis de la principale au moment des
changements de règle de passage en réel (8 trades le 29/10, 34 trades le 05/11).
Usage : python3 cumul_au_changement_de_regle.py"""
import numpy as np, pandas as pd
t = pd.read_csv("/home/user/AutoTrader/audit/2026-11-06/recherche/trades_15m.csv", parse_dates=["entry_time", "exit_time"])
l = t[(t.strat == "principale") & (t.entry_time >= pd.Timestamp("2026-10-28", tz="UTC")) & (t.result != "open")].sort_values("exit_time")
cum = np.cumsum(np.minimum(l.net_r.to_numpy(), 5)); raw = np.cumsum(l.net_r.to_numpy())
for k in (8, 34, len(l)):
    print(f"apres {k} trades : cumul plafonne {cum[k-1]:+.1f}R, brut {raw[k-1]:+.1f}R")
