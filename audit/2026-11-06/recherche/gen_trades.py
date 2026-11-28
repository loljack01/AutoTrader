"""Génère (sans rien écrire dans le dépôt) les trades historiques + suivis de :
principale sma20 (1pt et 3pt), variante D, simple balayage, écart continue,
et refait les contrôles de référence. Sortie : /home/user/AutoTrader/audit/2026-11-06/recherche/trades_*.csv
Usage : PYTHONDONTWRITEBYTECODE=1 python3 gen_trades.py"""
import sys, os
sys.dont_write_bytecode = True
REPO = "/home/user/AutoTrader"
sys.path.insert(0, REPO + "/scripts"); sys.path.insert(0, REPO)
import numpy as np, pandas as pd
import backtest_liquidity_sweep_buy as bt
import frozen_15m_calls_trend as M
import frozen_15m_variants as V
import frozen_15m_single_sweep as S
import frozen_gap_continuation as G
OUT = "/home/user/AutoTrader/audit/2026-11-06/recherche/"
NOW = pd.Timestamp("2026-11-06 23:00", tz="UTC")
rows = []
for sym, (name, k) in M.MARKETS.items():
    d = bt.cache.closed_bars(bt.cache.load(sym, "15m"), "15m", NOW)
    # contrôle de référence principale
    for ver, n in M.VERSIONS.items():
        ref = M.run(sym, d[d.index < M.REFERENCE_END], n, 1.0); ref = ref[ref.result != "open"]
        got = (len(ref), round(float(ref.net_r.sum()), 1))
        print("REF principale", sym, ver, got, M.REFERENCE[(sym, ver)], "OK" if got == M.REFERENCE[(sym, ver)] else "DIFFERENT")
    ref = S.run(sym, d[d.index < S.REFERENCE_END], 1.0); ref = ref[ref.result != "open"]
    got = (len(ref), round(float(ref.net_r.sum()), 1)); print("REF simple", sym, got, S.REFERENCE.get(sym), "OK" if got == S.REFERENCE.get(sym) else "DIFFERENT")
    ref = G.trades(sym, d[d.index < G.REFERENCE_END], 1.0 * k); ref = ref[ref.result != "open"]
    got = (len(ref), round(float(ref.net_r.sum()), 1)); print("REF ecart", sym, got, G.REFERENCE.get(sym), "OK" if got == G.REFERENCE.get(sym) else "DIFFERENT")
    for strat, fn in (("principale", lambda c: M.run(sym, d, 20, c)),
                      ("D", lambda c: V.run(sym, d, c, entry_hours=(8, 21.5), session_exit=21.75)),
                      ("simple", lambda c: S.run(sym, d, c)),
                      ("ecart", lambda c: G.trades(sym, d, c * k))):
        t1, t3 = fn(1.0), fn(3.0)
        t1 = t1.reset_index(drop=True); t3 = t3.reset_index(drop=True)
        assert len(t1) == len(t3) or strat == "ecart" or True
        t1 = t1.assign(strat=strat, market=name, sym=sym)
        # coût 3pt : on apparie par heure d'entrée
        m3 = t3.set_index("entry_time").net_r
        m3 = m3[~m3.index.duplicated()]
        t1["net_r3"] = t1.entry_time.map(m3)
        rows.append(t1[["strat", "market", "sym", "entry_time", "exit_time", "entry", "stop", "take", "result", "net_r", "net_r3"]])
    print("ok", sym, len(d), d.index[0], d.index[-1])
allt = pd.concat(rows, ignore_index=True)
allt.to_csv(OUT + "trades_15m.csv", index=False)
print(allt.groupby("strat").size())
