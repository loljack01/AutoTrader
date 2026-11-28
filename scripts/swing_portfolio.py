"""Shared helpers for the swing tests frozen on 2026-11-06
(docs/tests_figes_2026-11-06.md): the 5-position book of
test_swing_rsi2_cap5.py, optionally with per-zone limits, returning the
entry date and index of each trade taken, plus risk statistics.

select_book(cands, 5) reproduces test_swing_rsi2_cap5.select exactly
(checked by check_reference()).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import test_swing_rsi2 as sw
from test_swing_rsi2_cap5 import candidates, select

DEV = ("2012-01-01", "2022-01-01")
RESERVED = ("2022-01-01", "2100-01-01")
ZONES = {"EURONEXT:PX1": "euro", "XETR:DAX": "euro", "TVC:SX5E": "euro", "TVC:FTMIB": "euro",
         "SP:SPX": "us", "NASDAQ:NDX": "us", "TVC:DJI": "us", "TVC:RUT": "us",
         "TVC:UKX": "autre", "SIX:SMI": "autre"}
ZONE_CAPS = {"euro": 2, "us": 2, "autre": 1}


def ts(x):
    return pd.Timestamp(x, tz="UTC")


def rsi2_candidates(data, period):
    out = []
    for s, d in data.items():
        out += candidates(s, d, ts(period[0]), ts(period[1]))
    return out


def select_book(cands, cap, zone_caps=None):
    """Same order and rules as test_swing_rsi2_cap5.select (exits first, same
    close by lowest RSI(2), one position per index, skip when full); with
    zone_caps, a signal whose zone is full is skipped too."""
    cands = sorted(cands, key=lambda x: (x[0], x[2]))
    open_, taken, busy = [], [], {}
    for day, ex, rsi, sym, r in cands:
        open_ = [p for p in open_ if p[0] > day]
        if busy.get(sym, day) > day:
            continue
        busy[sym] = ex
        if len(open_) >= cap:
            continue
        if zone_caps is not None:
            z = ZONES[sym]
            if sum(ZONES[p[1]] == z for p in open_) >= zone_caps[z]:
                continue
        open_.append((ex, sym))
        taken.append((day, ex, sym, r))
    return pd.DataFrame(taken, columns=["entry", "exit", "sym", "r"])


def tweek(t):
    w = t.groupby(t.exit.dt.tz_localize(None).dt.to_period("W")).r.sum()
    return w.mean() / (w.std(ddof=1) / np.sqrt(len(w)))


def risk_stats(t, period):
    """Worst drawdown (cumulative R in exit order), worst 3-month result, R per year."""
    t = t.sort_values("exit")
    eq = t.set_index("exit").r.cumsum()
    dd = (eq - np.maximum(eq.cummax(), 0)).min()
    daily = eq.resample("D").last().ffill()
    worst3 = (daily - daily.shift(91)).min()
    end = min(ts(period[1]), t.exit.max())
    years = (end - ts(period[0])).days / 365.25
    return dd, worst3, t.r.sum() / years


def check_reference(data):
    c = rsi2_candidates(data, ("2012-01-01", "2100-01-01"))
    a, b = select(c, 5), select_book(c, 5)
    return len(a) == len(b) and abs(a.r.sum() - b.r.sum()) < 1e-9


def load_all():
    return {s: sw.load(s) for s in sw.INDICES}
