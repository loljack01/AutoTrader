"""1-minute "contexte + un seul sens" on FCE1! with a 16-point stop margin
instead of 8, rules fixed on 2026-10-30 BEFORE running, at the user's
request. ONE value only, no grid (12th idea tested in two days on the same
short 1m history).

Rules: exactly scripts/test_1m_exclusive.py (1m engine with
live_signals.set_rules, range context: calls only in the lower third,
puts only in the upper third; one direction at a time, earlier entry
wins) with a single change: stop = sweep extreme -/+ 16pt (STOP_MARGIN)
instead of 8pt. Min risk 2x ATR, target, net R:R >= 1.3, 4h window and
session filter unchanged. Decision only on the 1m bars before
REFERENCE_END (30/10 excluded). Costs 1pt and 3pt CAC points.

Decision rule (fixed before running), on the bars before REFERENCE_END:
worth live tracking WITHOUT money (frozen, from the next session) only if
ALL of:
  - at least 30 closed trades;
  - net > 0 at 3pt cost;
  - net > 0 at 1pt with every gain capped at +5R;
  - both halves of the period (split at the middle date) > 0 at 1pt;
  - net at 1pt above the 95th percentile of 2000 random subsets (seed 0)
    of the same size drawn from the unfiltered 16pt version's trades at
    1pt;
  - net at 1pt above the 8pt version (+5.5R, test_1m_exclusive.py, commit
    a26a568).
Otherwise REJETEE and the 1-minute timeframe is CLOSED: no further 1m
variant is tested until at least 6 more months of 1m history have been
accumulated.

Result (run on 2026-10-30, 16/09 -> 29/10): REJETEE, 1m CLOSED. 94
trades, 35% winners, +16.4R at 1pt, +3.3R at 3pt, capped +9.0R, halves
+3.7R / +12.8R, above the 8pt version, but BELOW the random 95th
percentile (+24.4R): not distinguishable from luck. Calls -0.5R (56),
puts +17.0R (38); median stop 14.1pt; unfiltered with 16pt +7.9R (230).

Usage: python scripts/test_1m_margin16.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
import test_1m_exclusive as tx
from live_signals import set_rules
from test_1m_context import CALENDAR, MIN_TRADES, REFERENCE_END, masks

MARGIN = 16.0
REFERENCE_8PT = 5.5


def side_run(d, cost, side, sweep_mask, entry_mask=None):
    set_rules()
    bt.ROUND_TRIP_COST = cost
    bt.STOP_MARGIN = MARGIN
    return bt.backtest(d, True, False, direction=side, sweep_mask=sweep_mask, entry_mask=entry_mask)


tx.side_run = side_run


def main():
    now = pd.Timestamp.now(tz="UTC")
    d = bt.cache.closed_bars(bt.cache.load("FCE1!", "1m"), "1m", now)
    d = d[d.index < REFERENCE_END]
    events = pd.to_datetime(pd.read_csv(CALENDAR).date, utc=True)
    print(f"FCE1! 1m {d.index[0]} -> {d.index[-1]} ({len(d)} barres), marge de stop {MARGIN:.0f} pts")
    _, ctx, _, _ = masks(d, events)
    full = np.ones(len(d), bool)
    base = pd.concat([side_run(d, 1.0, s, full) for s in tx.SIDES])
    base = base[base.result.isin(["stop", "take"])].net_r.to_numpy()
    f1, f3 = tx.exclusive(d, 1.0, ctx), tx.exclusive(d, 3.0, ctx)
    r = f1.net_r.to_numpy()
    cap = np.minimum(r, 5).sum()
    mid = d.index[0] + (d.index[-1] - d.index[0]) / 2
    h1, h2 = f1[f1.entry_time < mid].net_r.sum(), f1[f1.entry_time >= mid].net_r.sum()
    rng = np.random.default_rng(0)
    rand = np.array([rng.choice(base, len(r), replace=False).sum() for _ in range(2000)]) if 0 < len(r) <= len(base) else np.array([np.inf])
    p95 = np.percentile(rand, 95)
    risk = (f1.entry - f1.stop).abs()
    print(f"  sans filtre, marge 16     1pt: {len(base)} trades, net {base.sum():+.1f}R")
    print(f"  contexte + un seul sens, marge 16 (DECISION) 1pt: {len(r)} trades, {(r > 0).mean() if len(r) else 0:.0%} gagnants, "
          f"net {r.sum():+.1f}R, plafond 5R {cap:+.1f}R | 3pt: {len(f3)} trades, net {f3.net_r.sum():+.1f}R | "
          f"calls {f1[f1.side == 'call'].net_r.sum():+.1f}R ({(f1.side == 'call').sum()}), "
          f"puts {f1[f1.side == 'put'].net_r.sum():+.1f}R ({(f1.side == 'put').sum()}) | stop median {risk.median():.1f} pts")
    print(f"  moities (coupure {mid.tz_convert('Europe/Paris'):%d/%m %H:%M}) {h1:+.1f}R / {h2:+.1f}R | "
          f"95e centile de 2000 tirages au hasard : {p95:+.1f}R | version marge 8 : {REFERENCE_8PT:+.1f}R")
    ok = (len(r) >= MIN_TRADES and f3.net_r.sum() > 0 and cap > 0 and h1 > 0 and h2 > 0 and r.sum() > p95
          and r.sum() > REFERENCE_8PT)
    print(f"\nRegle fixee avant : marge 16 {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETEE, le 1 minute est clos'}")


if __name__ == "__main__":
    main()
