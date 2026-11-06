"""Helpers communs (audit execution 06/11/2026). Lecture seule du depot."""
import sys
from pathlib import Path
REPO = Path("/home/user/AutoTrader")
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
import numpy as np
import pandas as pd
import test_swing_rsi2 as sw

ZONE = {"EURONEXT:PX1": "eu", "XETR:DAX": "eu", "TVC:SX5E": "eu", "TVC:FTMIB": "eu", "TVC:UKX": "eu", "SIX:SMI": "eu",
        "SP:SPX": "us", "NASDAQ:NDX": "us", "TVC:DJI": "us", "TVC:RUT": "us"}


def load_all():
    return {s: sw.load(s) for s in sw.INDICES}


def cap5_trades(data, start="2012-01-01", end="2100-01-01", cap=5):
    """Livre a 5 positions identique a test_swing_rsi2_cap5.select, avec le detail de chaque trade."""
    cands = []
    for s, d in data.items():
        a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
        c, rsi = a[3], d.rsi2.to_numpy()
        idx = np.flatnonzero((c > d.sma200.to_numpy()) & (rsi < 10) & (d.index >= pd.Timestamp(start, tz="UTC"))
                             & (d.index < pd.Timestamp(end, tz="UTC")))
        for i in idx:
            j, px, risk = sw.exit_trade(a, i, 1)
            if j is None or not risk > 0:
                continue
            cands.append(dict(entry=d.index[i].normalize(), exit=d.index[j].normalize(), rsi=rsi[i], sym=s,
                              entry_px=c[i], exit_px=px, risk=risk, move_r=(px - c[i]) / risk, cost_frac=c[i] / risk,
                              days=j - i, exit_ts=d.index[j], entry_ts=d.index[i]))
    cands.sort(key=lambda x: (x["entry"], x["rsi"]))
    open_, taken, busy = [], [], {}
    for x in cands:
        open_ = [p for p in open_ if p[0] > x["entry"]]
        if busy.get(x["sym"], x["entry"]) > x["entry"]:
            continue
        busy[x["sym"]] = x["exit"]
        if len(open_) >= cap:
            continue
        open_.append((x["exit"], x["sym"]))
        taken.append(x)
    t = pd.DataFrame(taken)
    t["net005"] = t.move_r - 0.0005 * t.cost_frac
    t["net010"] = t.move_r - 0.0010 * t.cost_frac
    t["market"] = t.sym.map(sw.INDICES)
    return t
