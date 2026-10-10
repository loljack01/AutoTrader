"""Calls + puts on FCE1! 5m (sweep strategy, 2x ATR stop floor) with a
trend filter, rule fixed before running: take calls only when the last
COMPLETED bar of the trend timeframe closed above its 20-period SMA, puts
only when it closed below. Trend timeframes tried: 1D, 4h, 1h.

A trend bar counts as completed only once its full duration has elapsed
(open time + 1 day / 4h / 1h <= the 5m bar's close), so no bar is used
before it is known.

Baseline: random entries in the trend direction vs against it (every
session-allowed bar, stop 1.5x ATR, target 3x ATR, same cost), to see how
much of any gain is the filter riding market drift.

Usage: python scripts/trend_filter_both_sides.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from indicator_combo_search import outcomes
from setups import session

TREND_TFS = {"1D": pd.Timedelta(days=1), "4h": pd.Timedelta(hours=4), "1h": pd.Timedelta(hours=1)}
BAR = pd.Timedelta(minutes=5)
START = 1000.0
RISK = 0.01


def trend_up(d, tf):
    tb = bt.cache.load("FCE1!", tf)
    tb.index = pd.to_datetime(tb.index, utc=True)
    up = (tb.Close > tb.Close.rolling(20).mean()).to_numpy()
    done_at = (tb.index + TREND_TFS[tf]).to_numpy()
    pos = np.searchsorted(done_at, (d.index + BAR).to_numpy(), side="right") - 1
    return np.where(pos >= 0, up[np.clip(pos, 0, None)], False).astype(bool)


def capital(trades):
    equity, stakes, events = START, {}, []
    for k, t in trades.iterrows():
        events += [(t.entry_time, 0, k), (t.exit_time, 1, k)]
    low = START
    for _, kind, k in sorted(events):
        if kind == 0:
            stakes[k] = equity * RISK
        else:
            equity += trades.loc[k, "net_r"] * stakes.pop(k)
            low = min(low, equity)
    return equity, low


def main():
    now = pd.Timestamp.now(tz="UTC")
    d = bt.cache.closed_bars(bt.cache.load("FCE1!", "5m"), "5m", now)
    allowed = np.array([session.entry_allowed(session.session_window(t)) for t in d.index.tz_convert("Europe/Paris")])
    half = d.index[len(d) // 2]
    print(f"FCE1! 5m {d.index[0].date()} -> {d.index[-1].date()}, marche {d.Close.iloc[0]:.0f} -> {d.Close.iloc[-1]:.0f}, stop min 2xATR")
    bt.MIN_RISK_ATR_MULT = 2.0

    filters = {"aucun": np.ones(len(d), dtype=bool)} | {tf: trend_up(d, tf) for tf in TREND_TFS}
    for name, up in filters.items():
        share = up.mean() if name != "aucun" else float("nan")
        flips = int((np.diff(up.astype(int)) != 0).sum())
        print(f"\n######## filtre de tendance: {name}" + ("" if name == "aucun" else f" (haussier {share:.0%} du temps, {flips} changements)"))
        for cost in (1.0, 3.0):
            bt.ROUND_TRIP_COST = cost
            if name != "aucun":
                base = []
                for direction, mask in (("buy", up), ("sell", ~up)):
                    exit_idx, net = outcomes(d, direction, cost)
                    ok = allowed & (exit_idx >= 0)
                    base.append((np.nanmean(net[ok & mask]), np.nanmean(net[ok & ~mask])))
                w = np.mean([b[0] for b in base]); a = np.mean([b[1] for b in base])
                print(f"  cout {cost:.0f}pt | hasard dans le sens de la tendance {w:+.3f}R/trade, contre {a:+.3f}R/trade")
            for one in (True, False):
                parts = []
                for direction in ("buy", "sell"):
                    mask = None if name == "aucun" else (up if direction == "buy" else ~up)
                    t = bt.backtest(d, one, False, entry_mask=mask, direction=direction)
                    t = t[t.result != "open"].copy()
                    t["side"] = "call" if direction == "buy" else "put"
                    parts.append(t)
                tt = pd.concat(parts, ignore_index=True).sort_values("entry_time").reset_index(drop=True)
                r = tt.net_r.to_numpy()
                tstat = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 1 else float("nan")
                eq, low = capital(tt)
                c, p = tt[tt.side == "call"], tt[tt.side == "put"]
                h1, h2 = tt[tt.entry_time < half].net_r.sum(), tt[tt.entry_time >= half].net_r.sum()
                lab = "1/balayage" if one else "re-entrees"
                print(f"    cout {cost:.0f}pt {lab:10s}: n={len(tt):3d} (calls {len(c)} {c.net_r.sum():+5.1f}R, puts {len(p)} {p.net_r.sum():+5.1f}R) net={r.sum():+6.1f}R t={tstat:+.2f}"
                      f" | moities {h1:+.1f}/{h2:+.1f}R | 1000 EUR -> {eq:.0f} (plus bas {low:.0f})")


if __name__ == "__main__":
    main()
