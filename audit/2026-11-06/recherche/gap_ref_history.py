"""Rejoue le contrôle de référence de frozen_gap_continuation.py avec le cache de
données de différents commits (git show vers un dossier temporaire) pour dater la
rupture. Usage : python3 gap_ref_history.py <commit> [...]"""
import sys, subprocess, os, tempfile
sys.dont_write_bytecode = True
REPO = "/home/user/AutoTrader"; sys.path.insert(0, REPO + "/scripts"); sys.path.insert(0, REPO)
import pandas as pd
import backtest_liquidity_sweep_buy as bt
import frozen_gap_continuation as G
from pathlib import Path
syms = ["FDAX1!", "FIB1!", "RTY1!"]
for c in sys.argv[1:]:
    tmp = Path(tempfile.mkdtemp(dir="/home/user/AutoTrader/audit/2026-11-06/recherche"))
    for s in syms:
        for iv in ("15m", "1D"):
            f = f"data/cache/{bt.cache._safe_name(s)}_{iv}.csv"
            out = subprocess.run(["git", "-C", REPO, "show", f"{c}:{f}"], capture_output=True, text=True).stdout
            (tmp / Path(f).name).write_text(out)
    bt.cache.CACHE_DIR = tmp
    res = []
    for s in syms:
        d = bt.cache.load(s, "15m"); d.index = pd.to_datetime(d.index, utc=True)
        r = G.trades(s, d[d.index < G.REFERENCE_END], 1.0 * G.MARKETS[s][1]); r = r[r.result != "open"]
        res.append(f"{s} {(len(r), round(float(r.net_r.sum()), 1))} attendu {G.REFERENCE[s]}")
    print(c, " | ".join(res))
