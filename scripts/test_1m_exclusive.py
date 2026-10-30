"""1-minute sweep + CHoCH on FCE1! with range context AND one direction at
a time, rules fixed on 2026-10-30 BEFORE running, at the user's request
(11th idea tested in two days, on the same short 1m history: a pass would
still need live confirmation).

Origin: on 30/10 the 1m engine sold at 10:01 then bought at 10:04 while
the put was still open: calls and puts run independently and can be held
together. scripts/test_1m_context.py (rejected the same day) added the
range context but still allowed opposite positions at the same time.

Rules: exactly the "C contexte" version of test_1m_context.py (1m engine
with live_signals.set_rules, calls only when the sweep low is in the lower
third of the range [min(previous day low, today's low), max(previous day
high, today's high)], puts only in the upper third), PLUS exclusivity: no
entry on one side while a position on the other side is open (from its
entry bar up to, not including, its exit bar). The earlier entry wins; if
a call and a put would enter on the same bar, neither is taken. Done
inside the engine (entry_mask), re-running a side after each conflict in
time order, so a refused entry never blocks a later trade of its own side.
Decision only on the 1m bars before REFERENCE_END (30/10 excluded, it
inspired the idea). Costs 1pt and 3pt CAC points.

Decision rule (fixed before running), on the bars before REFERENCE_END:
worth live tracking WITHOUT money (frozen, from the next session) only if
ALL of:
  - at least 30 closed trades;
  - net > 0 at 3pt cost;
  - net > 0 at 1pt with every gain capped at +5R;
  - both halves of the period (split at the middle date) > 0 at 1pt;
  - net at 1pt above the 95th percentile of 2000 random subsets (seed 0)
    of the same size drawn from the unfiltered version's trades at 1pt;
  - net at 1pt above the "C contexte" version alone (exclusivity must add
    something).
Otherwise REJETEE, no re-tuning.

Result (run on 2026-10-30, 16/09 -> 29/10): REJETEE. 155 trades, 31%
winners, +5.5R at 1pt (C alone +1.0R, unfiltered -14.9R) but -17.7R at
3pt, capped -7.4R, halves +20.4R / -14.9R, random 95th percentile +21.4R;
calls -7.0R (83), puts +12.5R (72).

Usage: python scripts/test_1m_exclusive.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from live_signals import set_rules
from test_1m_context import CALENDAR, MIN_TRADES, REFERENCE_END, masks

SIDES = ("buy", "sell")


def side_run(d, cost, side, sweep_mask, entry_mask=None):
    set_rules()
    bt.ROUND_TRIP_COST = cost
    return bt.backtest(d, True, False, direction=side, sweep_mask=sweep_mask, entry_mask=entry_mask)


def exclusive(d, cost, ctx):
    """Both sides with context, one direction at a time (earlier entry wins)."""
    idx = d.index
    allow = {s: np.ones(len(d), bool) for s in SIDES}
    trades = {s: side_run(d, cost, s, ctx[s]) for s in SIDES}
    while True:
        first = None
        for s in SIDES:
            o = "sell" if s == "buy" else "buy"
            for x in trades[s].itertuples():
                for y in trades[o].itertuples():
                    end = y.exit_time if y.exit_time is not None and not pd.isna(y.exit_time) else idx[-1] + pd.Timedelta(minutes=1)
                    if y.entry_time <= x.entry_time < end:
                        if first is None or x.entry_time < first[1]:
                            first = (s, x.entry_time, y.entry_time, end)
        if first is None:
            break
        s, t, t_opp, end = first
        o = "sell" if s == "buy" else "buy"
        if t == t_opp:
            allow[s][idx == t] = False
            allow[o][idx == t] = False
            trades[o] = side_run(d, cost, o, ctx[o], allow[o])
        else:
            allow[s] &= ~((idx >= t_opp) & (idx < end))
        trades[s] = side_run(d, cost, s, ctx[s], allow[s])
    out = [trades[s].assign(side="call" if s == "buy" else "put") for s in SIDES]
    t = pd.concat(out)
    return t[t.result.isin(["stop", "take"])]


def main():
    now = pd.Timestamp.now(tz="UTC")
    d = bt.cache.closed_bars(bt.cache.load("FCE1!", "1m"), "1m", now)
    d = d[d.index < REFERENCE_END]
    events = pd.to_datetime(pd.read_csv(CALENDAR).date, utc=True)
    print(f"FCE1! 1m {d.index[0]} -> {d.index[-1]} ({len(d)} barres)")
    _, ctx, _, _ = masks(d, events)
    full = np.ones(len(d), bool)
    base = pd.concat([side_run(d, 1.0, s, full) for s in SIDES])
    base = base[base.result.isin(["stop", "take"])].net_r.to_numpy()
    c_only = pd.concat([side_run(d, 1.0, s, ctx[s]) for s in SIDES])
    c_only = c_only[c_only.result.isin(["stop", "take"])].net_r.sum()
    f1, f3 = exclusive(d, 1.0, ctx), exclusive(d, 3.0, ctx)
    r = f1.net_r.to_numpy()
    cap = np.minimum(r, 5).sum()
    mid = d.index[0] + (d.index[-1] - d.index[0]) / 2
    h1, h2 = f1[f1.entry_time < mid].net_r.sum(), f1[f1.entry_time >= mid].net_r.sum()
    rng = np.random.default_rng(0)
    rand = np.array([rng.choice(base, len(r), replace=False).sum() for _ in range(2000)]) if 0 < len(r) <= len(base) else np.array([np.inf])
    p95 = np.percentile(rand, 95)
    print(f"  sans filtre (reference)   1pt: {len(base)} trades, net {base.sum():+.1f}R")
    print(f"  C contexte seul           1pt: net {c_only:+.1f}R")
    print(f"  C + un seul sens (DECISION) 1pt: {len(r)} trades, {(r > 0).mean() if len(r) else 0:.0%} gagnants, net {r.sum():+.1f}R, "
          f"plafond 5R {cap:+.1f}R | 3pt: {len(f3)} trades, net {f3.net_r.sum():+.1f}R | "
          f"calls {f1[f1.side == 'call'].net_r.sum():+.1f}R ({(f1.side == 'call').sum()}), "
          f"puts {f1[f1.side == 'put'].net_r.sum():+.1f}R ({(f1.side == 'put').sum()})")
    print(f"  moities (coupure {mid.tz_convert('Europe/Paris'):%d/%m %H:%M}) {h1:+.1f}R / {h2:+.1f}R | "
          f"95e centile de 2000 tirages au hasard de {len(r)} trades sans filtre : {p95:+.1f}R")
    ok = (len(r) >= MIN_TRADES and f3.net_r.sum() > 0 and cap > 0 and h1 > 0 and h2 > 0 and r.sum() > p95
          and r.sum() > c_only)
    print(f"\nRegle fixee avant : 1m contexte + un seul sens {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETEE'}")


if __name__ == "__main__":
    main()
