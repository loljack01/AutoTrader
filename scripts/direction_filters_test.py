"""Three direction filters, fixed on 2026-10-27 BEFORE running, after the
5m diagnosis (calls 24% winners vs puts 41% in a falling market).

Base: frozen live rule set (2x ATR stop floor, 8pt margin, one trade per
sweep, net R:R >= 1.3, 4h window, Paris session filter), calls and puts,
no filter. Each filter only allows calls when it reads "up" and puts when
it reads "down", using closed data only (no look-ahead):

  D "tendance journaliere": previous session's daily close vs its 20-day
    SMA (same rule as the frozen 15m sma20 version).
  S "structure 1h": direction of the last break of structure on closed 1h
    bars (close above the last confirmed 1h swing high = up, below the
    last confirmed swing low = down), swings of 2 bars each side.
  V "VWAP de seance": entry bar close above the Paris-session VWAP = up,
    below = down.

Decision rule (fixed before running): a filter is kept as a NEW candidate
(tracked separately, frozen versions unchanged) only if, on BOTH 5m and
15m and at BOTH 1pt and 3pt cost:
  - its net R beats the base on BOTH halves of the history, and
  - its total net R beats the 95th percentile of 1000 random removals of
    the same number of trades from the base trade list.

Usage: python scripts/direction_filters_test.py [tool_result.json ...]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from exit_variants_test import set_rules
from levels import structure
from levels.vwap import session_vwap

BARS = {"5m": pd.Timedelta(minutes=5), "15m": pd.Timedelta(minutes=15)}
FILTERS = {"D tendance journaliere": "daily", "S structure 1h": "h1", "V VWAP de seance": "vwap"}


def as_of(d, bar, times, values):
    """For each bar of `d`, the latest value whose time is <= the bar's close."""
    pos = np.searchsorted(times, (d.index + bar).to_numpy(), side="right") - 1
    return np.where(pos >= 0, values[np.clip(pos, 0, None)], np.nan)


def up_down(d, bar, kind):
    if kind == "daily":
        daily = bt.cache.load(bt.SYMBOL, "1D")
        daily.index = pd.to_datetime(daily.index, utc=True)
        c, ma = daily.Close, daily.Close.rolling(20).mean()
        sign = np.where(ma.isna(), np.nan, np.sign(c - ma))
        done_at = (daily.index + pd.Timedelta(days=1)).to_numpy()
        s = as_of(d, bar, done_at, sign)
    elif kind == "h1":
        h = bt.cache.load(bt.SYMBOL, "1h")
        is_hi, is_lo = structure.find_swings(h, n=2)
        sh = structure.confirmed_level(is_hi, h.High, 2)
        sl = structure.confirmed_level(is_lo, h.Low, 2)
        bull, bear = structure.bos_events(h.Close, sh, sl)
        state = pd.Series(np.where(bull, 1.0, np.where(bear, -1.0, np.nan)), index=h.index).ffill()
        done_at = (h.index + pd.Timedelta(hours=1)).to_numpy()
        s = as_of(d, bar, done_at, state.to_numpy())
    else:
        s = np.sign((d.Close - session_vwap(d)).to_numpy())
    return s > 0, s < 0


def run(d, cost, masks=None):
    set_rules(cost)
    parts = []
    for direction, mask in (("buy", None if masks is None else masks[0]), ("sell", None if masks is None else masks[1])):
        parts.append(bt.backtest(d, True, False, direction=direction, entry_mask=mask))
    t = pd.concat(parts, ignore_index=True)
    return t[t.result != "open"].sort_values("entry_time").reset_index(drop=True)


def main():
    for f in sys.argv[1:]:
        j = json.load(open(f))
        bt.cache.ingest(bt.SYMBOL, j["interval"], j["bars"])
    now = pd.Timestamp.now(tz="UTC")
    rng = np.random.default_rng(0)
    verdict = {k: [] for k in FILTERS}
    for iv, bar in BARS.items():
        d = bt.cache.closed_bars(bt.cache.load(bt.SYMBOL, iv), iv, now)
        half = d.index[len(d) // 2]
        print(f"\n######## {iv}: {d.index[0].date()} -> {d.index[-1].date()} (moitie au {half.date()})")
        for cost in (1.0, 3.0):
            base = run(d, cost)
            b1, b2 = base[base.entry_time < half].net_r.sum(), base[base.entry_time >= half].net_r.sum()
            print(f"  cout {cost:.0f}pt {'base (sans filtre)':24s} n={len(base):3d} gagnants={(base.net_r > 0).mean():4.0%} "
                  f"net={base.net_r.sum():+6.1f}R | moities {b1:+.1f}/{b2:+.1f}R")
            for name, kind in FILTERS.items():
                t = run(d, cost, up_down(d, bar, kind))
                v1, v2 = t[t.entry_time < half].net_r.sum(), t[t.entry_time >= half].net_r.sum()
                k = max(len(base) - len(t), 0)
                rand = [np.delete(base.net_r.to_numpy(), rng.choice(len(base), k, replace=False)).sum() for _ in range(1000)]
                p95 = np.percentile(rand, 95)
                ok = v1 > b1 and v2 > b2 and t.net_r.sum() > p95
                verdict[name].append(ok)
                print(f"  cout {cost:.0f}pt {name:24s} n={len(t):3d} gagnants={(t.net_r > 0).mean():4.0%} net={t.net_r.sum():+6.1f}R "
                      f"| moities {v1:+.1f}/{v2:+.1f}R | hasard 95e {p95:+.1f}R | {'OK' if ok else '--'}")
    print("\nRegle fixee avant (2 moities > base ET > 95e centile du hasard, en 5m ET 15m, a 1pt ET 3pt):")
    for name, v in verdict.items():
        print(f"  {name}: {'RETENU comme nouvelle candidate' if all(v) else 'NON RETENU'} ({sum(v)}/{len(v)} cas)")


if __name__ == "__main__":
    main()
