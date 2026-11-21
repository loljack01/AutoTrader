"""Faster variants of the daily trend filter, compared against the current
one (previous session's daily close vs its 20-day SMA). Calls only in an
up trend, puts only in a down trend; sweep strategy with a 2x ATR stop.

Variants (fixed before running):
    sma20_prev   previous daily close vs SMA20            (current filter)
    sma20_live   current bar close vs SMA20 of the completed daily closes
    ema20_prev   previous daily close vs EMA20
    sma10_prev   previous daily close vs SMA10

Decision rule, also fixed before running: a variant replaces the current
filter only if, at 1pt cost with one trade per sweep, it beats it on both
halves of the period on BOTH 5m and 15m.

Usage: python scripts/daily_filter_speed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from trend_filter_both_sides import capital

VARIANTS = ("sma20_prev", "sma20_live", "ema20_prev", "sma10_prev")


def daily_masks(d, bar):
    daily = bt.cache.load("FCE1!", "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    c = daily.Close
    sma20, sma10 = c.rolling(20).mean(), c.rolling(10).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    done_at = (daily.index + pd.Timedelta(days=1)).to_numpy()
    pos = np.searchsorted(done_at, (d.index + bar).to_numpy(), side="right") - 1
    valid = pos >= 0
    p = np.clip(pos, 0, None)

    def pick(series):
        return np.where(valid, series.to_numpy()[p], np.nan)

    close = d.Close.to_numpy()
    with np.errstate(invalid="ignore"):
        return {
            "sma20_prev": pick(c) > pick(sma20),
            "sma20_live": close > pick(sma20),
            "ema20_prev": pick(c) > pick(ema20),
            "sma10_prev": pick(c) > pick(sma10),
        }


def run_both(d, up, one):
    parts = []
    for direction, mask in (("buy", up), ("sell", ~up)):
        t = bt.backtest(d, one, False, entry_mask=mask, direction=direction)
        t = t[t.result != "open"].copy()
        t["side"] = "call" if direction == "buy" else "put"
        parts.append(t)
    return pd.concat(parts, ignore_index=True).sort_values("entry_time").reset_index(drop=True)


def main():
    now = pd.Timestamp.now(tz="UTC")
    bt.MIN_RISK_ATR_MULT = 2.0
    verdict = {v: [] for v in VARIANTS}
    for iv in ("15m", "5m"):
        d = bt.cache.closed_bars(bt.cache.load("FCE1!", iv), iv, now)
        half = d.index[len(d) // 2]
        masks = daily_masks(d, pd.Timedelta(iv.replace("m", "min")))
        print(f"\n######## {iv}: {d.index[0].date()} -> {d.index[-1].date()} (moitie au {half.date()})")
        ref = None
        for v in VARIANTS:
            up = masks[v]
            flips = int((np.diff(up.astype(int)) != 0).sum())
            for cost in (1.0, 3.0):
                bt.ROUND_TRIP_COST = cost
                for one in (True, False):
                    tt = run_both(d, up, one)
                    r = tt.net_r.to_numpy()
                    tstat = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 1 else float("nan")
                    h1, h2 = tt[tt.entry_time < half].net_r.sum(), tt[tt.entry_time >= half].net_r.sum()
                    eq, low = capital(tt)
                    c, p = tt[tt.side == "call"], tt[tt.side == "put"]
                    lab = f"cout {cost:.0f}pt {'1/balayage' if one else 're-entrees'}"
                    print(f"  {v:10s} ({up.mean():4.0%} haussier, {flips:3d} bascules) {lab}: n={len(tt):3d} calls {c.net_r.sum():+5.1f}R puts {p.net_r.sum():+5.1f}R"
                          f" net={r.sum():+6.1f}R t={tstat:+.2f} moities {h1:+5.1f}/{h2:+5.1f}R 1000->{eq:.0f} (bas {low:.0f})")
                    if cost == 1.0 and one:
                        if v == "sma20_prev":
                            ref = (h1, h2)
                        else:
                            verdict[v].append(h1 > ref[0] and h2 > ref[1])
    print("\nRegle: retenue seulement si meilleure sur les deux moities en 15m ET en 5m (cout 1pt, 1/balayage)")
    for v, oks in verdict.items():
        if v != "sma20_prev":
            print(f"  {v}: {'RETENUE' if all(oks) else 'non retenue'} (15m: {'oui' if oks[0] else 'non'}, 5m: {'oui' if oks[1] else 'non'})")


if __name__ == "__main__":
    main()
