"""Test of one idea, fixed on 2026-10-22 before running: only keep sweeps
that take out the extreme of the current Paris session.

Criterion: a sweep counts only if, on the sweep bar, its extreme is the
session extreme so far - for a call, the sweep bar's Low is the lowest Low
of the Paris day up to and including that bar; for a put, its High is the
highest High. No look-ahead: only bars up to the sweep are used. Other
sweeps are ignored (they cannot trigger a trade); everything else is the
frozen rule set (2x ATR stop floor, one trade per sweep, net R:R >= 1.3,
4h window, Paris session filter), no trend filter.

The idea came from the 22/10 session, so the test period stops on the
21/10 close; results including 22/10 are shown for information only.

Decision rule (fixed before running): the criterion is kept as a NEW
candidate, tracked separately from 2026-10-23 (the frozen versions are not
changed), only if at 1pt cost it beats the same rules without it on BOTH
halves of the period on BOTH 5m and 15m, and at 3pt cost it beats them on
the whole period on both. Otherwise it is not kept.

Usage: python scripts/session_extreme_sweep_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt

TEST_END = "2026-10-22"


def set_rules(cost):
    bt.ROUND_TRIP_COST = cost
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)


def session_extreme_masks(d):
    day = d.index.tz_convert("Europe/Paris").date
    low_ok = (d.Low <= d.Low.groupby(day).cummin()).to_numpy()
    high_ok = (d.High >= d.High.groupby(day).cummax()).to_numpy()
    return low_ok, high_ok


def run(d, cost, filtered):
    set_rules(cost)
    low_ok, high_ok = session_extreme_masks(d)
    parts = []
    for direction, mask in (("buy", low_ok), ("sell", high_ok)):
        t = bt.backtest(d, True, False, direction=direction, sweep_mask=mask if filtered else None)
        t = t[t.result != "open"].copy()
        t["side"] = "call" if direction == "buy" else "put"
        parts.append(t)
    return pd.concat(parts, ignore_index=True).sort_values("entry_time").reset_index(drop=True)


def capital(t, start=1000.0, risk=0.01):
    eq = start
    for r in t.net_r:
        eq += r * eq * risk
    return eq


def describe(t, half):
    r = t.net_r.to_numpy()
    tstat = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 1 else float("nan")
    h1, h2 = t[t.entry_time < half].net_r.sum(), t[t.entry_time >= half].net_r.sum()
    c, p = t[t.side == "call"], t[t.side == "put"]
    txt = (f"n={len(t):3d} gagnants={(t.result == 'take').mean():4.0%} net={r.sum():+6.1f}R moy={r.mean() if len(r) else 0:+.2f}R t={tstat:+.2f} "
           f"| calls {len(c)} {c.net_r.sum():+.1f}R, puts {len(p)} {p.net_r.sum():+.1f}R | moities {h1:+.1f}/{h2:+.1f}R | 1000 -> {capital(t):,.0f} EUR")
    return txt, (h1, h2), r.sum()


def main():
    now = pd.Timestamp.now(tz="UTC")
    verdict = []
    for iv in ("5m", "15m"):
        full = bt.cache.closed_bars(bt.cache.load(bt.SYMBOL, iv), iv, now)
        d = full[full.index < TEST_END]
        half = d.index[len(d) // 2]
        print(f"\n######## {iv}: {d.index[0].date()} -> {d.index[-1].date()} (moitie au {half.date()})")
        res = {}
        for cost in (1.0, 3.0):
            for filtered in (False, True):
                t = run(d, cost, filtered)
                txt, halves, total = describe(t, half)
                res[(cost, filtered)] = (halves, total)
                print(f"  cout {cost:.0f}pt {'extreme de seance' if filtered else 'tous balayages  '}: {txt}")
        (b_h, _), (f_h, _) = res[(1.0, False)], res[(1.0, True)]
        ok = f_h[0] > b_h[0] and f_h[1] > b_h[1] and res[(3.0, True)][1] > res[(3.0, False)][1]
        verdict.append(ok)
        print(f"  -> {iv}: {'meilleur sur les 2 moities a 1pt et au total a 3pt' if ok else 'pas meilleur partout'}")
        t = run(full, 1.0, True)
        t = t[t.entry_time >= TEST_END]
        print(f"  (info, 22/10 seulement, cout 1pt: {len(t)} trades, {t.net_r.sum():+.2f}R)")
    print(f"\nRegle fixee avant: {'RETENU comme nouvelle candidate' if all(verdict) else 'NON RETENU'}")


if __name__ == "__main__":
    main()
