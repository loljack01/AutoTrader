"""Bollinger squeeze breakout in the direction of the VWAP, rules fixed on
2026-10-27 BEFORE running (idea seen on the 27/10 CAC late morning only;
none of the 10 markets' history was used to design it).

15m bars, each market's cash session (as in scripts/gap_fill_test.py:
Europe 9:00-17:30 Paris, US 9:30-16:00 New York). Long side below, short
side is the exact mirror:
  squeeze  Bollinger(20, 2) width / middle band on the previous bar is at
           or below the 20th percentile of the 100 bars before it
  entry    a 15m close above the upper band (previous close was not),
           with the close above the session VWAP; entry at that close,
           bars closing from cash open +15 min to session end -1h
  stop     the middle band (SMA20) at entry, at least 1x ATR(14) away
  exit     stop hit; or a 15m close below the (moving) middle band, at
           that close; or the bar ending at the session end, at its close
  limits   one trade at a time, at most 2 trades per market per day
A stop is filled at the stop, or at the open if the bar opens beyond it.
Cost 1pt and 3pt CAC-equivalent (fixed per-market factors).

Random baseline (as in scripts/staircase_test.py): for each real trade, an
entry on a random bar of the same market in the same hours on the same
side of the VWAP, same direction, same initial risk in ATR, same exits;
200 draws.

Decision rule (fixed before running), same as scripts/staircase_test.py:
worth live tracking only if, pooling the 10 markets: net R > 0 at 1pt AND
3pt; both halves of the history (per-market time halves, summed) > 0 at
1pt; at least 6 of 10 markets > 0 at 1pt; and the pooled net R at 1pt
beats the 95th percentile of the random baseline. Otherwise rejected, no
parameter re-tuning.

Usage: python scripts/squeeze_breakout_test.py
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
from gap_fill_test import local_clock, session
from levels.vwap import session_vwap
from other_markets_test import tstat


def prepare(symbol, d):
    p = pd.DataFrame(index=d.index)
    _, open_h, end_h = session(symbol)
    h, date = local_clock(symbol, d)
    p["h"], p["day"] = h, date
    mid, sd = d.Close.rolling(20).mean(), d.Close.rolling(20).std()
    p["mid"], p["up"], p["lo"] = mid, mid + 2 * sd, mid - 2 * sd
    width = (4 * sd / mid).to_numpy()
    q20 = pd.Series(width).shift(1).rolling(100).quantile(0.2).to_numpy()
    p["squeeze"] = np.append(False, (width[:-1] <= q20[1:]))  # previous bar's width vs the 100 before it
    p["atr"] = TA.ATR(d, 14).to_numpy()
    p["vwap"] = session_vwap(d).to_numpy()
    p["in_hours"] = (h >= open_h + 0.25) & (h <= end_h - 1.0)
    p["end"] = (h >= end_h) | np.append(date[1:] != date[:-1], True)
    return p


def exit_trade(d, p, i, side, stop):
    o, hi, lo, c = d.Open.to_numpy(), d.High.to_numpy(), d.Low.to_numpy(), d.Close.to_numpy()
    mid, end = p.mid.to_numpy(), p.end.to_numpy()
    for j in range(i + 1, len(d)):
        if (side == 1 and lo[j] <= stop) or (side == -1 and hi[j] >= stop):
            beyond = (o[j] <= stop) if side == 1 else (o[j] >= stop)
            return j, (o[j] if beyond else stop)
        if (side == 1 and c[j] < mid[j]) or (side == -1 and c[j] > mid[j]) or end[j]:
            return j, c[j]
    return len(d) - 1, c[-1]


def real_entries(d, p):
    c, up, lo, vw = d.Close.to_numpy(), p.up.to_numpy(), p.lo.to_numpy(), p.vwap.to_numpy()
    mid, atr, sq, ok = p.mid.to_numpy(), p.atr.to_numpy(), p.squeeze.to_numpy(), p.in_hours.to_numpy()
    out = []
    for i in range(1, len(d)):
        if not (ok[i] and sq[i]) or np.isnan(atr[i]) or np.isnan(up[i - 1]):
            continue
        if c[i] > up[i] and c[i - 1] <= up[i - 1] and c[i] > vw[i]:
            out.append((i, 1, max(c[i] - mid[i], atr[i])))
        if c[i] < lo[i] and c[i - 1] >= lo[i - 1] and c[i] < vw[i]:
            out.append((i, -1, max(mid[i] - c[i], atr[i])))
    return out


def simulate(d, p, entries, cost):
    """entries: (i, side, risk). One trade at a time, max 2 per day."""
    c, day = d.Close.to_numpy(), p.day.to_numpy()
    trades, busy_until, per_day = [], -1, {}
    for i, side, risk in sorted(entries):
        if i <= busy_until or per_day.get(day[i], 0) >= 2 or risk <= 0:
            continue
        entry = c[i]
        j, px = exit_trade(d, p, i, side, entry - side * risk)
        trades.append({"time": d.index[i], "side": side, "risk_atr": risk / p.atr.iat[i],
                       "net_r": side * (px - entry) / risk - cost / risk})
        busy_until, per_day[day[i]] = j, per_day.get(day[i], 0) + 1
    return pd.DataFrame(trades, columns=["time", "side", "risk_atr", "net_r"])


def main():
    now = pd.Timestamp.now(tz="UTC")
    rng = np.random.default_rng(0)
    pooled = {1.0: [], 3.0: []}
    halves, positive, rand_totals = [0.0, 0.0], 0, np.zeros(200)
    for symbol, (name, k) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        p = prepare(symbol, d)
        half = d.index[len(d) // 2]
        ent = real_entries(d, p)
        line = {}
        for cost in (1.0, 3.0):
            t = simulate(d, p, ent, cost * k)
            r = t.net_r.to_numpy()
            pooled[cost].append(r)
            line[cost] = f"n={len(t):3d} gagnants={(r > 0).mean() if len(r) else 0:4.0%} net={r.sum():+6.1f}R"
            if cost == 1.0:
                halves[0] += t[t.time < half].net_r.sum()
                halves[1] += t[t.time >= half].net_r.sum()
                positive += r.sum() > 0
                real_t = t
        c, vw, atr = d.Close.to_numpy(), p.vwap.to_numpy(), p.atr.to_numpy()
        ok = p.in_hours.to_numpy() & ~np.isnan(atr)
        pools = {1: np.flatnonzero(ok & (c > vw)), -1: np.flatnonzero(ok & (c < vw))}
        for s in range(200):
            ent_r = []
            for x in real_t.itertuples():
                if len(pools[x.side]):
                    i = int(rng.choice(pools[x.side]))
                    ent_r.append((i, x.side, x.risk_atr * atr[i]))
            rand_totals[s] += simulate(d, p, ent_r, 1.0 * k).net_r.sum()
        calls, puts = real_t[real_t.side == 1].net_r.sum(), real_t[real_t.side == -1].net_r.sum()
        print(f"{name:14s} 1pt-eq: {line[1.0]} (achats {calls:+.1f}R, ventes {puts:+.1f}R) | 3pt-eq: {line[3.0]}")
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
