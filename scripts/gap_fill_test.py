"""Opening gap back to the previous official close, rules fixed on 2026-10-27
BEFORE running (idea seen on the 27/10 CAC morning only; none of the 10
markets' history was used to design it).

15m bars, each market's cash session: European futures (CAC, DAX, Euro
Stoxx 50, FTSE 100, SMI, FTSE MIB) open 9:00 Paris; US futures (S&P 500,
Nasdaq 100, Dow, Russell 2000) open 9:30 New York.
  reference   R = previous official daily close (settlement, 1D bar close)
  entry       at the close C0 of the first 15m bar of the cash session,
              towards R (buy if C0 < R, sell if C0 > R), only if
              0.25 x daily ATR(14) <= |C0 - R| <= 1.0 x daily ATR(14)
              and that first bar has not already touched R
  target      R (limit)
  stop        same distance on the other side: C0 -/+ |C0 - R| (1:1)
  time exit   close of the bar ending 3h after the cash open
A bar that touches both stop and target counts as a stop. A stop is
filled at the stop, or at the open if the bar opens beyond it. One trade
per market per day. Cost 1pt and 3pt CAC-equivalent (fixed per-market
factors from scripts/frozen_15m_calls_trend.py).

Random baseline: for each real trade, a random cash-session day of the
same market, entry at its first 15m close, random direction, same
distance in daily ATR, same exits; 200 draws.

Decision rule (fixed before running), same as scripts/staircase_test.py:
worth live tracking only if, pooling the 10 markets: net R > 0 at 1pt AND
3pt; both halves of the history (per-market time halves, summed) > 0 at
1pt; at least 6 of 10 markets > 0 at 1pt; and the pooled net R at 1pt
beats the 95th percentile of the random baseline. Otherwise rejected, no
parameter re-tuning.

Usage: python scripts/gap_fill_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from other_markets_test import tstat

BAR = pd.Timedelta(minutes=15)
US = {"ES1!", "NQ1!", "YM1!", "RTY1!"}


def session(symbol):
    """(timezone, cash open hour, session end hour) in local time."""
    return ("America/New_York", 9.5, 16.0) if symbol in US else ("Europe/Paris", 9.0, 17.5)


def local_clock(symbol, d):
    """Local close time of each bar as fractional hour, and local date."""
    tz, _, _ = session(symbol)
    t = (d.index + BAR).tz_convert(tz)
    return np.asarray(t.hour + t.minute / 60), np.asarray(t.date)


def daily_ref(symbol, d):
    """Previous official close and daily ATR(14) known at each 15m bar."""
    daily = bt.cache.load(symbol, "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    tr = pd.concat([daily.High - daily.Low, (daily.High - daily.Close.shift()).abs(),
                    (daily.Low - daily.Close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().to_numpy()
    pos = np.searchsorted(daily.index.to_numpy(), d.index.to_numpy(), side="right") - 1
    ok = pos >= 1
    prev = np.where(ok, daily.Close.to_numpy()[np.clip(pos - 1, 0, None)], np.nan)
    patr = np.where(ok, atr[np.clip(pos - 1, 0, None)], np.nan)
    # the matching daily bar must have started less than a day before the 15m bar
    fresh = (d.index.to_numpy() - daily.index.to_numpy()[np.clip(pos, 0, None)]) < np.timedelta64(1, "D")
    return np.where(fresh, prev, np.nan), np.where(fresh, patr, np.nan)


def days(symbol, d):
    """Per cash-session day: (first bar index, last bar index of the 3h window)."""
    _, open_h, _ = session(symbol)
    h, date = local_clock(symbol, d)
    out = []
    for i in np.flatnonzero(np.isclose(h, open_h + 0.25)):
        same = np.flatnonzero((date == date[i]) & (h <= open_h + 3.0) & (np.arange(len(d)) > i))
        if len(same):
            out.append((i, same[-1]))
    return out


def walk(d, i, last, side, stop, target):
    o, hi, lo, c = d.Open.to_numpy(), d.High.to_numpy(), d.Low.to_numpy(), d.Close.to_numpy()
    for j in range(i + 1, last + 1):
        if (side == 1 and lo[j] <= stop) or (side == -1 and hi[j] >= stop):
            beyond = (o[j] <= stop) if side == 1 else (o[j] >= stop)
            return o[j] if beyond else stop
        if (side == 1 and hi[j] >= target) or (side == -1 and lo[j] <= target):
            return target
    return c[last]


def trade(d, i, last, side, dist, cost):
    entry = d.Close.iat[i]
    px = walk(d, i, last, side, entry - side * dist, entry + side * dist)
    return side * (px - entry) / dist - cost / dist


def real_trades(symbol, d, cost):
    ref, datr = daily_ref(symbol, d)
    rows = []
    for i, last in days(symbol, d):
        r, a, c0 = ref[i], datr[i], d.Close.iat[i]
        if np.isnan(r) or np.isnan(a):
            continue
        gap = c0 - r
        side = 1 if gap < 0 else -1
        touched = d.High.iat[i] >= r if side == 1 else d.Low.iat[i] <= r
        if not (0.25 * a <= abs(gap) <= 1.0 * a) or touched:
            continue
        rows.append({"time": d.index[i], "side": side, "dist_atr": abs(gap) / a,
                     "net_r": trade(d, i, last, side, abs(gap), cost)})
    return pd.DataFrame(rows, columns=["time", "side", "dist_atr", "net_r"])


def main():
    now = pd.Timestamp.now(tz="UTC")
    rng = np.random.default_rng(0)
    pooled = {1.0: [], 3.0: []}
    halves, positive, rand_totals = [0.0, 0.0], 0, np.zeros(200)
    for symbol, (name, k) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        half = d.index[len(d) // 2]
        line = {}
        for cost in (1.0, 3.0):
            t = real_trades(symbol, d, cost * k)
            r = t.net_r.to_numpy()
            pooled[cost].append(r)
            line[cost] = f"n={len(t):3d} gagnants={(r > 0).mean() if len(r) else 0:4.0%} net={r.sum():+6.1f}R"
            if cost == 1.0:
                halves[0] += t[t.time < half].net_r.sum()
                halves[1] += t[t.time >= half].net_r.sum()
                positive += r.sum() > 0
                real_t = t
        _, datr = daily_ref(symbol, d)
        pool = [(i, last) for i, last in days(symbol, d) if not np.isnan(datr[i])]
        for s in range(200):
            tot = 0.0
            for x in real_t.itertuples():
                i, last = pool[rng.integers(len(pool))]
                tot += trade(d, i, last, int(rng.choice((1, -1))), x.dist_atr * datr[i], 1.0 * k)
            rand_totals[s] += tot
        calls, puts = real_t[real_t.side == 1].net_r.sum(), real_t[real_t.side == -1].net_r.sum()
        print(f"{name:14s} 1pt-eq: {line[1.0]} (achats {calls:+.1f}R, ventes {puts:+.1f}R) | 3pt-eq: {line[3.0]}")
    r1, r3 = np.concatenate(pooled[1.0]), np.concatenate(pooled[3.0])
    p95 = np.percentile(rand_totals, 95)
    print(f"\n10 marches ensemble: 1pt-eq n={len(r1)} gagnants={(r1 > 0).mean():.0%} net={r1.sum():+.1f}R moy={r1.mean():+.3f}R "
          f"t={tstat(r1):+.2f} | 3pt-eq net={r3.sum():+.1f}R")
    print(f"  moities {halves[0]:+.1f}/{halves[1]:+.1f}R | marches positifs {positive}/10 | "
          f"hasard (jour et sens au hasard): mediane {np.median(rand_totals):+.1f}R, 95e centile {p95:+.1f}R")
    ok = r1.sum() > 0 and r3.sum() > 0 and min(halves) > 0 and positive >= 6 and r1.sum() > p95
    print(f"\nRegle fixee avant: {'A SUIVRE EN REEL' if ok else 'REJETEE'}")


if __name__ == "__main__":
    main()
