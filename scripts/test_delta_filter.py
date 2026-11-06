"""Corrected volume delta as a filter on the MAIN strategy, rules fixed on
2026-10-30 BEFORE any data is looked at, at the user's request (15th idea).
The test only runs once enough 1-minute data has been accumulated: until
then this script prints trade COUNTS only, never results, so the rule
cannot be adjusted by peeking.

Delta (same as tradingview/delta_volume_corrige.pine, version 4, "delta
séance"): from the 1-minute bars of the market, volume of green minutes
(close > open) minus volume of red minutes (close < open), divided by their
sum, x 100; neutral minutes ignored; summed from the start of the current
session (start = timestamp of the session's daily bar in the data feed)
up to the CLOSE of the 15m entry bar. It is not order flow (aggressor
volume), only minute candle colours.

Base: exactly the main strategy (frozen_15m_calls_trend.py, version sma20,
10 index futures, fixed factor k per market). Filter, in the direction of
the delta, applied INSIDE the engine (entry_mask):
  call  only if session delta > +10 % (and the usual daily SMA20 trend)
  put   only if session delta < -10 %
Between -10 % and +10 % (noise) no trade. A 15m bar is eligible only from
the first full session covered by the market's 1-minute cache; the base
uses exactly the same eligible bars, so both are compared on the same
period. Costs 1pt and 3pt CAC-equivalent.

Decision rule (fixed before any data), once the FILTERED version has at
least 30 closed trades on the 10 markets pooled: worth live tracking
WITHOUT money (frozen, next to the main strategy, which does not change)
only if ALL of:
  - net > 0 at 3pt-equivalent cost;
  - net > 0 at 1pt with every gain capped at +5R;
  - both halves of the eligible period (split at the middle date) > 0 at
    1pt;
  - average R per trade at 1pt above the unfiltered base on the same bars;
  - net at 1pt above the 95th percentile of 2000 random subsets (seed 0)
    of the same size drawn from the base trades.
Otherwise REJETE, no re-tuning (no other threshold, window, direction or
market set). The opposite reading (absorption: call when sellers dominate)
is NOT tested: one direction only, chosen before the data.

Data: 1-minute bars accumulated daily into data/cache/<market>_1m.csv by
the scheduled accumulation task (CAC since 2026-09-16, the 9 others from
2026-10-31).

Usage: python scripts/test_delta_filter.py
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

FROZEN_ON = "2026-10-30"
THRESHOLD, MIN_TRADES = 10.0, 30
BAR = pd.Timedelta(minutes=15)


def session_delta(symbol, d15, now):
    """Session delta (%) at the close of each 15m bar, and eligibility mask."""
    raw = bt.cache.load(symbol, "1m")
    m1 = bt.cache.closed_bars(raw, "1m", now) if not raw.empty else raw
    if m1.empty:
        return np.full(len(d15), np.nan), np.zeros(len(d15), bool)
    daily = bt.cache.load(symbol, "1D")
    starts = pd.DatetimeIndex(daily.index).tz_convert("UTC").sort_values()
    t1 = m1.index.tz_convert("UTC")
    sess1 = np.searchsorted(starts.asi8, t1.asi8, side="right") - 1
    buy = np.where(m1.Close > m1.Open, m1.Volume, 0.0)
    sell = np.where(m1.Close < m1.Open, m1.Volume, 0.0)
    frame = pd.DataFrame({"s": sess1, "b": buy, "v": sell})
    cb = frame.groupby("s").b.cumsum().to_numpy()
    cs = frame.groupby("s").v.cumsum().to_numpy()
    first_full = starts[starts > t1[0]]
    if not len(first_full):
        return np.full(len(d15), np.nan), np.zeros(len(d15), bool)
    t15 = d15.index.tz_convert("UTC")
    sess15 = np.searchsorted(starts.asi8, t15.asi8, side="right") - 1
    last = np.searchsorted(t1.asi8, (t15 + BAR).asi8, side="left") - 1
    out = np.full(len(d15), np.nan)
    ok = (last >= 0) & (t15 >= first_full[0]) & (t15 + BAR <= t1[-1] + pd.Timedelta(minutes=1))
    for i in np.flatnonzero(ok):
        j = last[i]
        if sess1[j] != sess15[i]:
            continue
        tot = cb[j] + cs[j]
        if tot > 0:
            out[i] = (cb[j] - cs[j]) / tot * 100
    return out, ok & ~np.isnan(out)


def run(symbol, d, cost, call_mask, put_mask):
    k = MARKETS[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    t = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=call_mask).assign(side="call"),
                   bt.backtest(d, True, False, direction="sell", entry_mask=put_mask).assign(side="put")],
                  ignore_index=True)
    return t[t.result.isin(["stop", "take"])].assign(market=MARKETS[symbol][0])


def main():
    now = pd.Timestamp.now(tz="UTC")
    base1, base3, f1s, f3s, spans = [], [], [], [], []
    for s in MARKETS:
        d = bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now)
        delta, elig = session_delta(s, d, now)
        if not elig.any():
            print(f"  {MARKETS[s][0]:14s} pas encore de donnees 1 minute exploitables")
            continue
        up = np.asarray(trend_up(s, d, "SMA", 20), bool)
        b_call, b_put = up & elig, elig.copy()
        f_call = b_call & (delta > THRESHOLD)
        f_put = elig & (delta < -THRESHOLD)
        b1, b3 = run(s, d, 1.0, b_call, b_put), run(s, d, 3.0, b_call, b_put)
        f1, f3 = run(s, d, 1.0, f_call, f_put), run(s, d, 3.0, f_call, f_put)
        base1.append(b1), base3.append(b3), f1s.append(f1), f3s.append(f3)
        first = d.index[elig.argmax()]
        spans.append(first)
        print(f"  {MARKETS[s][0]:14s} barres eligibles depuis {first:%d/%m/%Y} : principale {len(b1)} trades clos, "
              f"avec filtre delta {len(f1)}")
    if not f1s:
        print("\nAucun marche n'a encore de donnees 1 minute : test en attente.")
        return
    B1, F1, F3 = pd.concat(base1), pd.concat(f1s), pd.concat(f3s)
    print(f"\nTotal : principale {len(B1)} trades, avec filtre delta {len(F1)} (seuil de decision : {MIN_TRADES})")
    if len(F1) < MIN_TRADES:
        print(f"Test EN ATTENTE : encore {MIN_TRADES - len(F1)} trades filtres a accumuler. "
              "Aucun resultat affiche avant le seuil (regle fixee le " + FROZEN_ON + ").")
        return
    r, base = F1.net_r.to_numpy(), B1.net_r.to_numpy()
    start, end = min(spans), now
    mid = start + (end - start) / 2
    h1, h2 = F1[F1.entry_time < mid].net_r.sum(), F1[F1.entry_time >= mid].net_r.sum()
    cap = np.minimum(r, 5).sum()
    rng = np.random.default_rng(0)
    rand = np.array([rng.choice(base, len(r), replace=False).sum() for _ in range(2000)]) if len(r) <= len(base) else np.array([np.inf])
    p95 = np.percentile(rand, 95)
    for lab, t in (("principale, 1pt", B1), ("principale + delta, 1pt", F1), ("principale + delta, 3pt", F3)):
        x = t.net_r.to_numpy()
        print(f"  {lab:26s} {len(x):3d} trades, {(x > 0).mean():4.0%} gagnants, net {x.sum():+6.1f}R ({x.mean():+.2f}R/trade) | "
              f"calls {t[t.side == 'call'].net_r.sum():+.1f}R ({(t.side == 'call').sum()}), "
              f"puts {t[t.side == 'put'].net_r.sum():+.1f}R ({(t.side == 'put').sum()})")
    print(f"  plafond 5R {cap:+.1f}R | moities (coupure {mid:%d/%m}) {h1:+.1f}R / {h2:+.1f}R | "
          f"95e centile du hasard {p95:+.1f}R")
    ok = F3.net_r.sum() > 0 and cap > 0 and h1 > 0 and h2 > 0 and r.mean() > base.mean() and r.sum() > p95
    print(f"\nRegle fixee le {FROZEN_ON} : filtre delta {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
