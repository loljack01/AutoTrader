"""1-minute sweep + CHoCH on FCE1! with CONTEXT filters, rules fixed on
2026-10-30 BEFORE running, at the user's request (10th idea tested in
the last two days, hence the strict rule below).

Origin: on 30/10 at 10:04 the 1m engine bought a 4-point dip at the German
GDP release while the market was failing under its range top (8006 under
8009 / 8013): a put context. The plain 1m engine (set_rules of
live_signals.py, both sides) is already rejected: 356 trades, -14.9R at
1pt, -78.8R at 3pt from 16/09 to 30/10. Question: does the missing
context fix it? 30/10 itself inspired the idea and is EXCLUDED: decision
only on the 1m bars before REFERENCE_END (from 2026-09-16, start of the
1m history).

Engine: backtest_liquidity_sweep_buy.backtest on 1m, rules of
live_signals.set_rules (stop = sweep extreme +/- 8pt, min risk 2x ATR,
target = nearest unswept opposite pool, net R:R >= 1.3, 4h window, Paris
session filter, one trade per sweep), calls and puts. Filters are applied
INSIDE the engine (sweep_mask / entry_mask), so a filtered-out sweep never
blocks a later trade. No lookahead: every level is known before the sweep
bar.

  N  niveau    the sweep bar's extreme pierces a plan level by at most 8pt
               (calls: low < L <= low + 8; puts: high - 8 <= L < high).
               Plan levels (Paris days): previous trading day's high and
               low; today's high and low BEFORE the sweep bar; 15m swing
               highs and lows (SWING_N=2, 15m bars built from the 1m bars,
               usable 45 min after the swing bar opens) of the previous
               and current trading day; round numbers (multiples of 50).
  A  annonces  no sweep and no entry within 15 min (before or after) of a
               high-importance release (TradingView calendar, US, EU, DE,
               FR, importance 1, saved in
               data/backtests/calendar_high_2026-09-15_2026-10-30.csv);
               no entry 9:00-9:15 Paris nor 9:30-9:45 New York (plan rule).
  C  contexte  range = [min(previous day low, today's low), max(previous
               day high, today's high)], today's extremes up to and
               including the sweep bar. Calls only if the sweep low is in
               the lower third, puts only if the sweep high is in the
               upper third. No previous day: no trade.

Versions shown: none (reference), N, A, C alone (information) and N+A+C
(DECISION). Costs 1pt (turbo spread) and 3pt CAC points.

Decision rule (fixed before running), N+A+C on the bars before
REFERENCE_END: worth live tracking WITHOUT money (frozen, from the next
session) only if ALL of:
  - at least 30 closed trades;
  - net > 0 at 3pt cost;
  - net > 0 at 1pt with every gain capped at +5R;
  - both halves of the period (split at the middle date) > 0 at 1pt;
  - net at 1pt above the 95th percentile of 2000 random subsets (seed 0)
    of the same size drawn from the unfiltered version's trades at 1pt
    (the filters must beat luck).
Otherwise REJETEE, no re-tuning (no other margin, third, window or level
list is tried).

Usage: python scripts/test_1m_context.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from levels import structure
from live_signals import set_rules

REFERENCE_END = "2026-10-30"
MARGIN = 8.0
NEWS_WINDOW = pd.Timedelta(minutes=15)
MIN_TRADES = 30
ROOT = Path(__file__).resolve().parent.parent
CALENDAR = ROOT / "data" / "backtests" / "calendar_high_2026-09-15_2026-10-30.csv"


def plan_levels(d):
    """Per 1m bar: previous day high/low, today's high/low before the bar,
    today's high/low including the bar, and the 15m swing levels known."""
    paris = d.index.tz_convert("Europe/Paris")
    day = pd.Series(paris.date, index=d.index)
    days = sorted(set(day))
    prev_of = {x: days[k - 1] if k else None for k, x in enumerate(days)}
    daily = d.groupby(day.values).agg({"High": "max", "Low": "min"})
    prev_hi = np.array([daily.High.get(prev_of[x], np.nan) if prev_of[x] else np.nan for x in day])
    prev_lo = np.array([daily.Low.get(prev_of[x], np.nan) if prev_of[x] else np.nan for x in day])
    g = d.groupby(day.values)
    hi_incl = g.High.cummax().to_numpy()
    lo_incl = g.Low.cummin().to_numpy()
    hi_before = g.High.transform(lambda s: s.cummax().shift(1)).to_numpy()
    lo_before = g.Low.transform(lambda s: s.cummin().shift(1)).to_numpy()

    m15 = d.resample("15min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    is_hi, is_lo = structure.find_swings(m15, n=2)
    m15_day = m15.index.tz_convert("Europe/Paris").date
    swings = [(ts + pd.Timedelta(minutes=45), m15_day[k], m15.High.iloc[k] if is_hi.iloc[k] else None,
               m15.Low.iloc[k] if is_lo.iloc[k] else None)
              for k, ts in enumerate(m15.index) if is_hi.iloc[k] or is_lo.iloc[k]]
    return day.to_numpy(), prev_of, prev_hi, prev_lo, hi_before, lo_before, hi_incl, lo_incl, swings


def masks(d, events):
    day, prev_of, prev_hi, prev_lo, hi_before, lo_before, hi_incl, lo_incl, swings = plan_levels(d)
    n = len(d)
    hi, lo = d.High.to_numpy(), d.Low.to_numpy()
    lvl = {"buy": np.zeros(n, bool), "sell": np.zeros(n, bool)}
    ctx = {"buy": np.zeros(n, bool), "sell": np.zeros(n, bool)}
    times = d.index
    for i in range(n):
        if np.isnan(prev_hi[i]):
            continue
        ok_days = (day[i], prev_of[day[i]])
        known = [(h, l) for t, sd, h, l in swings if t <= times[i] and sd in ok_days]
        highs = [prev_hi[i], hi_before[i]] + [h for h, _ in known if h is not None]
        lows = [prev_lo[i], lo_before[i]] + [l for _, l in known if l is not None]
        levels = [x for x in highs + lows if not np.isnan(x)]
        r50_up = np.floor((lo[i] + MARGIN) / 50) * 50
        lvl["buy"][i] = any(lo[i] < x <= lo[i] + MARGIN for x in levels) or r50_up > lo[i]
        r50_dn = np.ceil((hi[i] - MARGIN) / 50) * 50
        lvl["sell"][i] = any(hi[i] - MARGIN <= x < hi[i] for x in levels) or r50_dn < hi[i]
        top, bot = max(prev_hi[i], hi_incl[i]), min(prev_lo[i], lo_incl[i])
        third = (top - bot) / 3
        ctx["buy"][i] = lo[i] <= bot + third
        ctx["sell"][i] = hi[i] >= top - third

    news = np.zeros(n, bool)
    for t in events:
        news |= (times >= t - NEWS_WINDOW) & (times <= t + NEWS_WINDOW)
    paris = times.tz_convert("Europe/Paris")
    ny = times.tz_convert("America/New_York")
    ph, nh = paris.hour + paris.minute / 60, ny.hour + ny.minute / 60
    blocked = ((ph >= 9) & (ph < 9.25)) | ((nh >= 9.5) & (nh < 9.75))
    return lvl, ctx, ~news, ~news & ~np.asarray(blocked)


def run(d, cost, side, use, lvl, ctx, sweep_ok, entry_ok):
    set_rules()
    bt.ROUND_TRIP_COST = cost
    sm = np.ones(len(d), bool)
    em = None
    if "N" in use:
        sm &= lvl[side]
    if "C" in use:
        sm &= ctx[side]
    if "A" in use:
        sm &= sweep_ok
        em = entry_ok
    t = bt.backtest(d, True, False, direction=side, sweep_mask=sm, entry_mask=em)
    return t[t.result.isin(["stop", "take"])].assign(side="call" if side == "buy" else "put")


def main():
    now = pd.Timestamp.now(tz="UTC")
    d = bt.cache.closed_bars(bt.cache.load("FCE1!", "1m"), "1m", now)
    d = d[d.index < REFERENCE_END]
    events = pd.to_datetime(pd.read_csv(CALENDAR).date, utc=True)
    print(f"FCE1! 1m {d.index[0]} -> {d.index[-1]} ({len(d)} barres), {len(events)} annonces majeures")
    lvl, ctx, sweep_ok, entry_ok = masks(d, events)
    res = {}
    for use, label in (("", "sans filtre (reference)"), ("N", "N niveau du plan"), ("A", "A annonces"),
                       ("C", "C contexte (tiers du range)"), ("NAC", "N+A+C (DECISION)")):
        out = {}
        for cost in (1.0, 3.0):
            out[cost] = pd.concat([run(d, cost, s, use, lvl, ctx, sweep_ok, entry_ok) for s in ("buy", "sell")])
        res[use] = out
        a, b = out[1.0], out[3.0]
        r = a.net_r.to_numpy()
        print(f"  {label:28s} 1pt: {len(r):3d} trades, {(r > 0).mean() if len(r) else 0:4.0%} gagnants, net {r.sum():+6.1f}R, "
              f"plafond 5R {np.minimum(r, 5).sum():+6.1f}R | 3pt: {len(b):3d} trades, net {b.net_r.sum():+6.1f}R | "
              f"calls {a[a.side == 'call'].net_r.sum():+.1f}R ({(a.side == 'call').sum()}), "
              f"puts {a[a.side == 'put'].net_r.sum():+.1f}R ({(a.side == 'put').sum()})")

    f1, f3 = res["NAC"][1.0], res["NAC"][3.0]
    r = f1.net_r.to_numpy()
    mid = d.index[0] + (d.index[-1] - d.index[0]) / 2
    h1 = f1[f1.entry_time < mid].net_r.sum()
    h2 = f1[f1.entry_time >= mid].net_r.sum()
    base = res[""][1.0].net_r.to_numpy()
    rng = np.random.default_rng(0)
    rand = np.array([rng.choice(base, len(r), replace=False).sum() for _ in range(2000)]) if 0 < len(r) <= len(base) else np.array([np.inf])
    p95 = np.percentile(rand, 95)
    cap = np.minimum(r, 5).sum()
    print(f"\nN+A+C : moities (coupure {mid.tz_convert('Europe/Paris'):%d/%m %H:%M}) {h1:+.1f}R / {h2:+.1f}R | "
          f"95e centile de 2000 tirages au hasard de {len(r)} trades sans filtre : {p95:+.1f}R")
    for x in f1.sort_values("entry_time").itertuples():
        print(f"     {x.entry_time.tz_convert('Europe/Paris'):%d/%m %H:%M} {x.side:4s} entree {x.entry:.1f} stop {x.stop:.1f} "
              f"cible {x.take:.1f} -> {x.result} {x.net_r:+.2f}R")
    ok = len(r) >= MIN_TRADES and f3.net_r.sum() > 0 and cap > 0 and h1 > 0 and h2 > 0 and r.sum() > p95
    print(f"\nRegle fixee avant : 1m avec contexte {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETEE'}")


if __name__ == "__main__":
    main()
