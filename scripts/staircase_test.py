"""Intraday trend-following strategy "Escalier intraday", rules fixed on
2026-10-27 BEFORE running (inspired only by the 27/10 CAC morning; none of
the 10 markets' history was used to design it).

15m bars, Paris time; long side below, short side is the exact mirror:
  1 trend day   after 10:00, a 15m close above the first-hour high (bars
                closing 9:15-10:00) has happened today, and the current
                close is above the session VWAP
  2 pullback    the last confirmed 15m swing low (2 bars each side) is
                today and higher than the previous one, and no 15m close
                below the VWAP since that swing low
  3 entry       a 15m close crosses above the last confirmed swing high
                (price resumes its climb); entry at that close, 10:00-16:30
  4 stop        below the pullback low, at least 1x ATR(14) away
  5 exit        no target: the stop trails up to each new confirmed higher
                swing low; exit on a 15m close below the VWAP; everything
                closed at the bar ending 17:30 (or the last bar of the day)
  6 limits      one trade at a time, at most 2 trades per market per day
Cost 1pt and 3pt CAC-equivalent (fixed per-market factors from
scripts/frozen_15m_calls_trend.py). A stop is filled at the stop, or at the
open if the bar opens beyond it.

Random baseline: for each real trade, an entry on a random bar of the same
market in the same hours on the same side of the VWAP, same direction,
same initial risk in ATR, same exits; 200 draws.

Decision rule (fixed before running): worth live tracking only if, pooling
the 10 markets: net R > 0 at 1pt AND 3pt; both halves of the history
(per-market time halves, summed) > 0 at 1pt; at least 6 of 10 markets > 0
at 1pt; and the pooled net R at 1pt beats the 95th percentile of the
random baseline. Otherwise rejected, no parameter re-tuning.

Usage: python scripts/staircase_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from finta import TA

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from levels import structure
from levels.vwap import session_vwap
from other_markets_test import tstat

BAR = pd.Timedelta(minutes=15)


def prepare(d):
    p = pd.DataFrame(index=d.index)
    close_t = (d.index + BAR).tz_convert("Europe/Paris")
    p["h"] = close_t.hour + close_t.minute / 60
    p["day"] = close_t.date
    p["atr"] = TA.ATR(d, 14).to_numpy()
    p["vwap"] = session_vwap(d).to_numpy()
    is_hi, is_lo = structure.find_swings(d, n=2)
    p["hi_mark"] = structure.confirmed_marks(is_hi, d.High, 2).to_numpy()
    p["lo_mark"] = structure.confirmed_marks(is_lo, d.Low, 2).to_numpy()
    fh = (p.h > 9.0) & (p.h <= 10.0)
    p["fh_high"] = d.High.where(fh).groupby(p.day).transform("max").to_numpy()
    p["fh_low"] = d.Low.where(fh).groupby(p.day).transform("min").to_numpy()
    after = p.h >= 10.0
    p["up_day"] = ((d.Close > p.fh_high) & after).groupby(p.day).cummax().to_numpy()
    p["dn_day"] = ((d.Close < p.fh_low) & after).groupby(p.day).cummax().to_numpy()
    days = p.day.to_numpy()
    p["last_of_day"] = np.append(days[1:] != days[:-1], True)
    return p


def exit_trade(d, p, i, side, stop, cost):
    """Walk forward from the bar after entry i; returns (exit index, exit price)."""
    o, hi, lo, c = d.Open.to_numpy(), d.High.to_numpy(), d.Low.to_numpy(), d.Close.to_numpy()
    vw, h, last = p.vwap.to_numpy(), p.h.to_numpy(), p.last_of_day.to_numpy()
    trail = p.lo_mark.to_numpy() if side == 1 else p.hi_mark.to_numpy()
    for j in range(i + 1, len(d)):
        if (side == 1 and lo[j] <= stop) or (side == -1 and hi[j] >= stop):
            beyond = (o[j] <= stop) if side == 1 else (o[j] >= stop)
            return j, (o[j] if beyond else stop)
        if (side == 1 and c[j] < vw[j]) or (side == -1 and c[j] > vw[j]):
            return j, c[j]
        if h[j] >= 17.5 or last[j]:
            return j, c[j]
        m = trail[j]
        if not np.isnan(m) and ((side == 1 and m > stop) or (side == -1 and m < stop)):
            stop = m
    return len(d) - 1, c[-1]


def signals(d, p):
    """Entry candidates (i, side, initial stop) before the one-at-a-time / 2-per-day limits."""
    c = d.Close.to_numpy()
    out = []
    last_hi = last_lo = np.nan
    lows, highs = [], []  # (value, index) of confirmed swings
    below_since_low = above_since_high = False
    h, vw, day = p.h.to_numpy(), p.vwap.to_numpy(), p.day.to_numpy()
    for i in range(len(d)):
        if not np.isnan(p.lo_mark.iat[i]):
            lows.append((p.lo_mark.iat[i], i))
            below_since_low = False
        if not np.isnan(p.hi_mark.iat[i]):
            highs.append((p.hi_mark.iat[i], i))
            above_since_high = False
        prev_hi, prev_lo = last_hi, last_lo
        last_hi = highs[-1][0] if highs else np.nan
        last_lo = lows[-1][0] if lows else np.nan
        if c[i] < vw[i]:
            below_since_low = True
        if c[i] > vw[i]:
            above_since_high = True
        if not (10.0 <= h[i] <= 16.5) or i == 0:
            continue
        if (p.up_day.iat[i] and c[i] > vw[i] and len(lows) >= 2 and lows[-1][0] > lows[-2][0]
                and day[lows[-1][1]] == day[i] and not below_since_low
                and not np.isnan(prev_hi) and c[i] > prev_hi and c[i - 1] <= prev_hi):
            out.append((i, 1, lows[-1][0]))
        if (p.dn_day.iat[i] and c[i] < vw[i] and len(highs) >= 2 and highs[-1][0] < highs[-2][0]
                and day[highs[-1][1]] == day[i] and not above_since_high
                and not np.isnan(prev_lo) and c[i] < prev_lo and c[i - 1] >= prev_lo):
            out.append((i, -1, highs[-1][0]))
    return out


def simulate(d, p, entries, cost):
    """entries: (i, side, risk). One trade at a time, max 2 per day."""
    c, day = d.Close.to_numpy(), p.day.to_numpy()
    trades, busy_until, per_day = [], -1, {}
    for i, side, risk in sorted(entries):
        if i <= busy_until or per_day.get(day[i], 0) >= 2 or risk <= 0:
            continue
        entry = c[i]
        j, px = exit_trade(d, p, i, side, entry - side * risk, cost)
        trades.append({"time": d.index[i], "side": side, "risk_atr": risk / p.atr.iat[i],
                       "net_r": side * (px - entry) / risk - cost / risk})
        busy_until, per_day[day[i]] = j, per_day.get(day[i], 0) + 1
    return pd.DataFrame(trades, columns=["time", "side", "risk_atr", "net_r"])


def real_entries(d, p):
    c, atr = d.Close.to_numpy(), p.atr.to_numpy()
    out = []
    for i, side, pull in signals(d, p):
        if np.isnan(atr[i]):
            continue
        out.append((i, side, max((c[i] - pull) * side, atr[i])))
    return out


def main():
    now = pd.Timestamp.now(tz="UTC")
    rng = np.random.default_rng(0)
    pooled = {1.0: [], 3.0: []}
    halves, positive, rand_totals = [0.0, 0.0], 0, np.zeros(200)
    for symbol, (name, k) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        p = prepare(d)
        half = d.index[len(d) // 2]
        ent = real_entries(d, p)
        line = []
        for cost in (1.0, 3.0):
            t = simulate(d, p, ent, cost * k)
            r = t.net_r.to_numpy()
            pooled[cost].append(r)
            line.append(f"n={len(t):3d} gagnants={(r > 0).mean() if len(r) else 0:4.0%} net={r.sum():+6.1f}R")
            if cost == 1.0:
                h1, h2 = t[t.time < half].net_r.sum(), t[t.time >= half].net_r.sum()
                halves[0] += h1
                halves[1] += h2
                positive += r.sum() > 0
                calls, puts = t[t.side == 1].net_r.sum(), t[t.side == -1].net_r.sum()
                real_t = t
        # random baseline, 1pt
        c, vw, h, atr = d.Close.to_numpy(), p.vwap.to_numpy(), p.h.to_numpy(), p.atr.to_numpy()
        ok_hours = (h >= 10.0) & (h <= 16.5) & ~np.isnan(atr)
        pools = {1: np.flatnonzero(ok_hours & (c > vw)), -1: np.flatnonzero(ok_hours & (c < vw))}
        for s in range(200):
            ent_r = []
            for x in real_t.itertuples():
                cand = pools[x.side]
                if len(cand):
                    i = int(rng.choice(cand))
                    ent_r.append((i, x.side, x.risk_atr * atr[i]))
            rand_totals[s] += simulate(d, p, ent_r, 1.0 * k).net_r.sum()
        print(f"{name:14s} 1pt-eq: {line[0]} (calls {calls:+.1f}R, puts {puts:+.1f}R) | 3pt-eq: {line[1]}")
    r1, r3 = np.concatenate(pooled[1.0]), np.concatenate(pooled[3.0])
    p95 = np.percentile(rand_totals, 95)
    print(f"\n10 marches ensemble: 1pt-eq n={len(r1)} gagnants={(r1 > 0).mean():.0%} net={r1.sum():+.1f}R moy={r1.mean():+.3f}R "
          f"t={tstat(r1):+.2f} | 3pt-eq net={r3.sum():+.1f}R")
    print(f"  moities {halves[0]:+.1f}/{halves[1]:+.1f}R | marches positifs {positive}/10 | "
          f"hasard (meme cote de la VWAP): mediane {np.median(rand_totals):+.1f}R, 95e centile {p95:+.1f}R")
    ok = r1.sum() > 0 and r3.sum() > 0 and min(halves) > 0 and positive >= 6 and r1.sum() > p95
    print(f"\nRegle fixee avant: {'A SUIVRE EN REEL' if ok else 'REJETEE'}")


if __name__ == "__main__":
    main()
