"""SMT divergence between correlated European index futures as a filter on
the MAIN strategy, rules fixed on 2026-10-30 BEFORE running, at the user's
request (14th idea tested in two days; the user's own volume delta
indicator is deliberately NOT used: it has never been checked).

Idea (SMC/ICT "SMT divergence", classic intermarket confirmation): a sweep
of lows on one index is more likely a false break if a closely correlated
index does NOT make a new low at the same time (and the mirror for highs).
Markets: CAC 40 (FCE1!), DAX (FDAX1!), Euro Stoxx 50 (FESX1!); each one is
checked against the two others.

Base: exactly the main strategy (frozen_15m_calls_trend.py, version sma20:
frozen 15m sweep + CHoCH, stop = max(sweep extreme +/- 8pt x k, 2x ATR),
target = nearest unswept opposite pool, net R:R >= 1.3, 4h window, Paris
session filter, one trade per sweep; calls only if the previous daily
close is above its 20-day SMA, puts always). Filter, applied INSIDE the
engine (sweep_mask): a sweep counts only if, on the same 15m bar, at least
one of the two other markets does NOT trade beyond its own extreme of the
previous 16 bars (4h, the CHoCH window): for a sweep of lows (calls), its
low stays above its lowest low of the 16 previous bars; for a sweep of
highs (puts), its high stays below its highest high of the 16 previous
bars. A missing bar, or fewer than 12 of the 16 previous bars, counts as
no divergence. Nothing else changes.

Period: trades entered from START (all three markets have 15m data) to
before REFERENCE_END (30/10 excluded). Costs 1pt and 3pt CAC-equivalent
(fixed factor k per market).

Decision rule (fixed before running), the three markets pooled, SMT
version: worth live tracking WITHOUT money (frozen, next to the main
strategy, which does not change) only if ALL of:
  - at least 30 closed trades;
  - net > 0 at 3pt-equivalent cost;
  - net > 0 at 1pt with every gain capped at +5R;
  - both halves of the period (split at the middle date) > 0 at 1pt;
  - average R per trade at 1pt above the unfiltered main strategy's on
    the same markets and period;
  - net at 1pt above the 95th percentile of 2000 random subsets (seed 0)
    of the same size drawn from the unfiltered main strategy's trades.
Otherwise REJETEE, no re-tuning (no other window, partner rule or market
set is tried). Trades the filter removes are shown for information.

Result (run on 2026-10-30, 02/07 -> 29/10): REJETE. SMT version 73
trades, +5.7R at 1pt (+0.08R/trade vs +0.13R unfiltered), -0.7R at 3pt,
halves -0.3R / +6.0R, random 95th percentile +17.8R. The 19 trades the
filter removed (partners confirming the sweep) did better: +9.1R
(+0.48R/trade), the opposite of the idea, on a small sample.

Usage: python scripts/test_smt_divergence.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from ma_grid_test import trend_up

START = "2026-07-02"
REFERENCE_END = "2026-10-30"
SYMBOLS = ("FCE1!", "FDAX1!", "FESX1!")
WINDOW, MIN_BARS, MIN_TRADES = 16, 12, 30


def load(symbol):
    d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", pd.Timestamp.now(tz="UTC"))
    return d[d.index < REFERENCE_END]


def smt_masks(symbol, data):
    """Per bar of `symbol`: does at least one partner fail to confirm a new low / high?"""
    idx = data[symbol].index
    low_ok, high_ok = np.zeros(len(idx), bool), np.zeros(len(idx), bool)
    for p in SYMBOLS:
        if p == symbol:
            continue
        q = data[p].reindex(idx)
        prev_low = q.Low.shift(1).rolling(WINDOW, min_periods=MIN_BARS).min()
        prev_high = q.High.shift(1).rolling(WINDOW, min_periods=MIN_BARS).max()
        low_ok |= (q.Low > prev_low).fillna(False).to_numpy()
        high_ok |= (q.High < prev_high).fillna(False).to_numpy()
    return low_ok, high_ok


def run(symbol, d, cost, masks=None):
    k = MARKETS[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    up = trend_up(symbol, d, "SMA", 20)
    low_ok, high_ok = masks if masks is not None else (None, None)
    t = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up, sweep_mask=low_ok).assign(side="call"),
                   bt.backtest(d, True, False, direction="sell", sweep_mask=high_ok).assign(side="put")],
                  ignore_index=True)
    t = t[t.result.isin(["stop", "take"]) & (t.entry_time >= START)]
    return t.assign(market=MARKETS[symbol][0])


def line(label, t):
    r = t.net_r.to_numpy()
    if not len(r):
        return f"  {label:30s} 0 trade"
    return (f"  {label:30s} {len(r):3d} trades, {(r > 0).mean():4.0%} gagnants, net {r.sum():+6.1f}R "
            f"({r.mean():+.2f}R/trade), plafond 5R {np.minimum(r, 5).sum():+6.1f}R | "
            f"calls {t[t.side == 'call'].net_r.sum():+.1f}R ({(t.side == 'call').sum()}), "
            f"puts {t[t.side == 'put'].net_r.sum():+.1f}R ({(t.side == 'put').sum()})")


def main():
    data = {s: load(s) for s in SYMBOLS}
    base1, base3, smt1, smt3, removed = [], [], [], [], []
    for s in SYMBOLS:
        d = data[s]
        masks = smt_masks(s, data)
        b1, b3 = run(s, d, 1.0), run(s, d, 3.0)
        f1, f3 = run(s, d, 1.0, masks), run(s, d, 3.0, masks)
        pos = d.index.get_indexer(b1.sweep_time)
        keep = np.where(b1.side == "call", masks[0][pos], masks[1][pos])
        base1.append(b1), base3.append(b3), smt1.append(f1), smt3.append(f3), removed.append(b1[~keep])
        print(f"{MARKETS[s][0]} (barres 15m {d.index[0]:%d/%m} -> {d.index[-1]:%d/%m}) :")
        print(line("principale, 1pt", b1))
        print(line("principale + SMT, 1pt", f1))
        print(line("principale + SMT, 3pt", f3))
        print(line("ecartes par le filtre (info)", b1[~keep]))
    B1, B3, F1, F3 = (pd.concat(x) for x in (base1, base3, smt1, smt3))
    print("\nTrois marches ensemble :")
    print(line("principale, 1pt", B1))
    print(line("principale, 3pt", B3))
    print(line("principale + SMT, 1pt", F1))
    print(line("principale + SMT, 3pt", F3))
    print(line("ecartes par le filtre (info)", pd.concat(removed)))
    r, base = F1.net_r.to_numpy(), B1.net_r.to_numpy()
    mid = pd.Timestamp(START, tz="UTC") + (pd.Timestamp(REFERENCE_END, tz="UTC") - pd.Timestamp(START, tz="UTC")) / 2
    h1, h2 = F1[F1.entry_time < mid].net_r.sum(), F1[F1.entry_time >= mid].net_r.sum()
    rng = np.random.default_rng(0)
    rand = np.array([rng.choice(base, len(r), replace=False).sum() for _ in range(2000)]) if 0 < len(r) <= len(base) else np.array([np.inf])
    p95 = np.percentile(rand, 95)
    cap = np.minimum(r, 5).sum()
    print(f"\nSMT : moities (coupure {mid:%d/%m}) {h1:+.1f}R / {h2:+.1f}R | R/trade {r.mean() if len(r) else 0:+.2f} contre "
          f"{base.mean():+.2f} sans filtre | 95e centile de 2000 tirages au hasard de {len(r)} trades : {p95:+.1f}R")
    ok = (len(r) >= MIN_TRADES and F3.net_r.sum() > 0 and cap > 0 and h1 > 0 and h2 > 0
          and r.mean() > base.mean() and r.sum() > p95)
    print(f"\nRegle fixee avant : filtre de divergence SMT {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
