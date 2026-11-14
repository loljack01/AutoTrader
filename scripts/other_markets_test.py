"""Out-of-market check of the frozen 15m rules, fixed on 2026-10-27 BEFORE
running. The rules were tuned on FCE1! only; if their edge is real it
should show up on other index futures they have never seen.

Markets: DAX (FDAX1!), Euro Stoxx 50 (FESX1!), S&P 500 (ES1!), Nasdaq 100
(NQ1!), 15m, all the history the data feed holds (about 3-4 months).

Rules: exactly the frozen 15m set (scripts/frozen_15m_daily.py): sweep +
CHoCH, stop = max(sweep extreme +/- margin, 2x ATR), target = nearest
unswept opposite pool, net R:R >= 1.3, 4h window, Paris session filter,
one trade per sweep, calls and puts, in two versions:
    none   no filter
    sma20  calls only if the previous daily close is above its 20-day
           SMA, puts only if below
The two settings expressed in CAC points are scaled to each market's
price level (factor = median close / 7900): the 8pt stop margin, and the
round-trip cost (1pt and 3pt CAC-equivalent, i.e. about 0.013% and 0.038%
of price).

Decision rule (fixed before running), for each version: the edge is
CONFIRMED outside the CAC only if, pooling the four markets,
  - net R > 0 at the 1pt-equivalent AND at the 3pt-equivalent cost, and
  - the mean R per trade at 1pt-equivalent has a t-stat >= 2.0, and
  - net R > 0 on at least 3 of the 4 markets at 1pt-equivalent.
Otherwise: NOT CONFIRMED.

Usage: python scripts/other_markets_test.py [tool_result.json ...]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt

MARKETS = {"FDAX1!": "DAX", "FESX1!": "Euro Stoxx 50", "ES1!": "S&P 500", "NQ1!": "Nasdaq 100"}
CAC_LEVEL = 7900.0
BAR = pd.Timedelta(minutes=15)


def ingest(path):
    j = json.load(open(path))
    bars = j["bars"]
    if isinstance(bars, dict):  # columns format
        bars = [dict(zip(bars.keys(), row)) for row in zip(*bars.values())]
    bt.cache.ingest(j["symbol"], j["interval"], bars)


def trend_up(symbol, d):
    daily = bt.cache.load(symbol, "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    c = daily.Close
    ma = c.rolling(20).mean()
    up = (c > ma).to_numpy() & ma.notna().to_numpy()
    done_at = (daily.index + pd.Timedelta(days=1)).to_numpy()
    pos = np.searchsorted(done_at, (d.index + BAR).to_numpy(), side="right") - 1
    return np.where(pos >= 0, up[np.clip(pos, 0, None)], False).astype(bool)


def run(symbol, d, version, cost_cac):
    k = float(d.Close.median()) / CAC_LEVEL
    bt.ROUND_TRIP_COST = cost_cac * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    if version == "none":
        masks = (("buy", None), ("sell", None))
    else:
        up = trend_up(symbol, d)
        masks = (("buy", up), ("sell", ~up))
    parts = [bt.backtest(d, True, False, direction=direction, entry_mask=mask) for direction, mask in masks]
    t = pd.concat(parts, ignore_index=True)
    return t[t.result != "open"].sort_values("entry_time").reset_index(drop=True)


def tstat(r):
    return r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 1 else float("nan")


def main():
    for f in sys.argv[1:]:
        ingest(f)
    now = pd.Timestamp.now(tz="UTC")
    pooled = {(v, c): [] for v in ("none", "sma20") for c in (1.0, 3.0)}
    positive = {v: 0 for v in ("none", "sma20")}
    for symbol, name in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        half = d.index[len(d) // 2]
        k = float(d.Close.median()) / CAC_LEVEL
        print(f"\n######## {name} ({symbol}) 15m: {d.index[0].date()} -> {d.index[-1].date()}, "
              f"facteur {k:.2f} (marge {8 * k:.1f} pts, cout {k:.1f}/{3 * k:.1f} pts)")
        for version in ("none", "sma20"):
            for cost in (1.0, 3.0):
                t = run(symbol, d, version, cost)
                r = t.net_r.to_numpy()
                pooled[(version, cost)].append(r)
                h1, h2 = t[t.entry_time < half].net_r.sum(), t[t.entry_time >= half].net_r.sum()
                if cost == 1.0 and r.sum() > 0:
                    positive[version] += 1
                print(f"  {version:5s} cout {cost:.0f}pt-eq: n={len(t):3d} gagnants={(r > 0).mean() if len(r) else 0:4.0%} "
                      f"net={r.sum():+6.1f}R moy={r.mean() if len(r) else 0:+.3f}R t={tstat(r):+.2f} | moities {h1:+.1f}/{h2:+.1f}R")
    print("\n######## Les 4 marches ensemble")
    for version in ("none", "sma20"):
        r1, r3 = np.concatenate(pooled[(version, 1.0)]), np.concatenate(pooled[(version, 3.0)])
        ok = r1.sum() > 0 and r3.sum() > 0 and tstat(r1) >= 2.0 and positive[version] >= 3
        print(f"  {version:5s}: 1pt-eq n={len(r1)} net={r1.sum():+.1f}R moy={r1.mean():+.3f}R t={tstat(r1):+.2f} | "
              f"3pt-eq net={r3.sum():+.1f}R | marches positifs a 1pt-eq: {positive[version]}/4 -> "
              f"{'AVANTAGE CONFIRME hors CAC' if ok else 'NON CONFIRME'}")


if __name__ == "__main__":
    main()
