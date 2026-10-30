"""Supertrend, as a strategy and as an exit for the main strategy, rules
fixed on 2026-10-29 BEFORE running (asked by the user after the 29/10 CAC
morning, where the 15m Supertrend(10, 3) had been long since 28/10 14:30).
Because the idea comes from 29/10, the decision uses bars BEFORE
2026-10-29 only; 29/10 is shown for information.

Supertrend(10, 3) on 15m bars: basis (High + Low) / 2, ATR(10) with
Wilder smoothing, bands at 3 x ATR, the usual ratchet (a band never moves
against the trend), direction flips on a CLOSE beyond the opposite band.
ADX(14) on 15m bars (finta). "Range" means ADX < 20 (Wilder's classic
threshold, not tuned).

  A1  Supertrend alone, always in the market: at each flip, the current
      position is closed and the new one opened at the flip bar's close,
      in the new direction. Risk (1R) = distance from entry to the
      Supertrend line at entry. Exit at the close of the next flip. No
      target, no other stop.
  A2  the same, flat in a range: within each Supertrend leg (flip to next
      flip), one entry at the close of the first bar of the leg whose
      ADX(14) >= 20; if ADX stays < 20 for the whole leg, no trade. Risk
      and exit as A1 (a flip closes the trade whatever the ADX).
  B   the main strategy (frozen_15m_calls_trend.py, sma20) with a
      Supertrend exit: same entries and initial stops as its trade list
      (computed on the same bars; overlaps not re-simulated), no target;
      exit at the stop (filled at the stop, or at the open if the bar
      opens beyond it) or at the close of the first bar after entry where
      the Supertrend FLIPS against the trade, whichever comes first. The
      entry bar never counts for exits. A new version, never a change to
      the frozen one.

Cost 1pt and 3pt CAC-equivalent (fixed per-market factors from
scripts/frozen_15m_calls_trend.py), bars before 2026-10-29, trades still
open at the end of the data left out.

Random baseline for A1 and A2: for each real trade, a random bar of the
same market, random direction, same risk in 15m ATR(10), held the same
number of bars, exit at the close; 200 draws.

Decision rules (fixed before running), STRICTER than the earlier tests
because this is the 4th idea tested on the same data today:
  A1, A2 (each on its own): worth live tracking (without money) only if,
    pooling the 10 markets: net R > 0 at 1pt AND 3pt; both halves of the
    history (per-market time halves, summed) > 0 at 1pt; at least 6 of 10
    markets > 0 at 1pt; t-stat at 1pt >= 2.0; and the pooled net R at 1pt
    beats the 99th percentile of the random baseline.
  B: worth live tracking next to the frozen main (which does not change)
    only if, pooling the 10 markets: its net R beats the frozen exits at
    1pt AND 3pt; it is > 0 at 3pt; it stays > 0 without its 3 best trades
    and with every gain capped at +5R (the main's go-live tests); at least
    6 of 10 markets > 0 at 1pt; and t-stat at 1pt >= 2.0.
Otherwise rejected, no re-tuning (no other period, multiplier, ADX level
or timeframe tried).

Usage: python scripts/supertrend_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from finta import TA

import backtest_liquidity_sweep_buy as bt
import frozen_15m_calls_trend as ct
from frozen_15m_calls_trend import MARKETS
from other_markets_test import tstat

DECISION_END = "2026-10-29"
ST_N, ST_M = 10, 3.0
ADX_N, ADX_MIN = 14, 20.0
WARMUP = 50


def supertrend(d, n=ST_N, m=ST_M):
    """(direction +1/-1, line, ATR) per bar, each known at the bar's close."""
    h, l, c = d.High.to_numpy(), d.Low.to_numpy(), d.Close.to_numpy()
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    hl2 = (h + l) / 2
    ub, lb = hl2 + m * atr, hl2 - m * atr
    fu, fl = ub.copy(), lb.copy()
    dirn, line = np.ones(len(c)), lb.copy()
    for i in range(1, len(c)):
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        dirn[i] = 1 if c[i] > fu[i - 1] else (-1 if c[i] < fl[i - 1] else dirn[i - 1])
        line[i] = fl[i] if dirn[i] == 1 else fu[i]
    return dirn, line, atr


def st_trades(d, cost, with_adx):
    dirn, line, atr = supertrend(d)
    adx = TA.ADX(d, ADX_N).to_numpy()
    c = d.Close.to_numpy()
    flips = [i for i in range(max(1, WARMUP), len(d)) if dirn[i] != dirn[i - 1]]
    rows = []
    for f, nxt in zip(flips, flips[1:]):
        legal = [f] if not with_adx else [i for i in range(f, nxt) if not np.isnan(adx[i]) and adx[i] >= ADX_MIN]
        if not legal:
            continue
        i = legal[0]
        side = int(dirn[f])
        risk = abs(c[i] - line[i])
        if risk <= 0:
            continue
        rows.append({"time": d.index[i], "side": side, "entry": c[i], "risk_atr": risk / atr[i], "bars": nxt - i,
                     "net_r": side * (c[nxt] - c[i]) / risk - cost / risk})
    return pd.DataFrame(rows, columns=["time", "side", "entry", "risk_atr", "bars", "net_r"])


def main_with_st_exit(symbol, d, cost):
    """Frozen main (sma20) entries and stops, Supertrend-flip exit."""
    t = ct.run(symbol, d, 20, cost)
    dirn, _, _ = supertrend(d)
    o, hi, lo, c = d.Open.to_numpy(), d.High.to_numpy(), d.Low.to_numpy(), d.Close.to_numpy()
    pos = {ts: i for i, ts in enumerate(d.index)}
    k = MARKETS[symbol][1]
    rows = []
    for x in t.itertuples():
        i = pos[x.entry_time]
        side = 1 if x.take > x.entry else -1
        risk = abs(x.entry - x.stop)
        px = None
        for j in range(i + 1, len(d)):
            if (side == 1 and lo[j] <= x.stop) or (side == -1 and hi[j] >= x.stop):
                beyond = (o[j] <= x.stop) if side == 1 else (o[j] >= x.stop)
                px = o[j] if beyond else x.stop
                break
            if dirn[j] != dirn[j - 1] and dirn[j] == -side:
                px = c[j]
                break
        if px is None:
            continue
        rows.append({"time": x.entry_time, "side": side, "net_r": side * (px - x.entry) / risk - cost * k / risk})
    return pd.DataFrame(rows, columns=["time", "side", "net_r"])


def main():
    now = pd.Timestamp.now(tz="UTC")
    rng = np.random.default_rng(0)
    res = {(v, c): {} for v in ("A1", "A2", "B", "gel") for c in (1.0, 3.0)}
    halves = {"A1": [0.0, 0.0], "A2": [0.0, 0.0]}
    rand = {"A1": np.zeros(200), "A2": np.zeros(200)}
    today = []
    for symbol, (name, k) in MARKETS.items():
        full = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        d = full[full.index < DECISION_END]
        half = d.index[len(d) // 2]
        _, _, atr = supertrend(d)
        c = d.Close.to_numpy()
        parts = []
        for v, adx in (("A1", False), ("A2", True)):
            for cost in (1.0, 3.0):
                t = st_trades(d, cost * k, adx)
                res[(v, cost)][symbol] = t.net_r.to_numpy()
                if cost == 1.0:
                    halves[v][0] += t[t.time < half].net_r.sum()
                    halves[v][1] += t[t.time >= half].net_r.sum()
                    for s in range(200):
                        tot = 0.0
                        for x in t.itertuples():
                            b = int(rng.integers(WARMUP, len(d) - x.bars))
                            side = int(rng.choice((1, -1)))
                            dist = x.risk_atr * atr[b]
                            tot += side * (c[b + x.bars] - c[b]) / dist - 1.0 * k / dist
                        rand[v][s] += tot
            r1, r3 = res[(v, 1.0)][symbol], res[(v, 3.0)][symbol]
            parts.append(f"{v} n={len(r1):3d} {(r1 > 0).mean() if len(r1) else 0:4.0%} {r1.sum():+6.1f}R (3pt {r3.sum():+6.1f}R)")
        for cost in (1.0, 3.0):
            res[("B", cost)][symbol] = main_with_st_exit(symbol, d, cost).net_r.to_numpy()
            g = ct.run(symbol, d, 20, cost)
            res[("gel", cost)][symbol] = g[g.result.isin(["stop", "take"])].net_r.to_numpy()
        b1, g1 = res[("B", 1.0)][symbol], res[("gel", 1.0)][symbol]
        parts.append(f"B n={len(b1):3d} {b1.sum():+6.1f}R (fige {len(g1)} trades {g1.sum():+6.1f}R)")
        print(f"{name:14s} " + " | ".join(parts))
        if symbol == "FCE1!":
            t = st_trades(full, 1.0 * k, False)
            dirn, line, _ = supertrend(full)
            today.append(f"  CAC 40 maintenant: Supertrend {'acheteur' if dirn[-1] == 1 else 'vendeur'}, ligne {line[-1]:.1f}, "
                         f"dernier retournement {t.time.iloc[-1].tz_convert('Europe/Paris'):%d/%m %H:%M} si clos, sinon en cours")
    print("\n## 10 marches ensemble, avant le 29/10")
    verdict = {}
    for v in ("A1", "A2"):
        r1 = np.concatenate(list(res[(v, 1.0)].values()))
        r3 = np.concatenate(list(res[(v, 3.0)].values()))
        pos = sum(x.sum() > 0 for x in res[(v, 1.0)].values())
        p99 = np.percentile(rand[v], 99)
        print(f"  {v}: n={len(r1)} gagnants={(r1 > 0).mean():.0%} net={r1.sum():+.1f}R t={tstat(r1):+.2f} | 3pt {r3.sum():+.1f}R | "
              f"moities {halves[v][0]:+.1f}/{halves[v][1]:+.1f}R | marches positifs {pos}/10 | "
              f"hasard mediane {np.median(rand[v]):+.1f}R, 99e centile {p99:+.1f}R")
        verdict[v] = (r1.sum() > 0 and r3.sum() > 0 and min(halves[v]) > 0 and pos >= 6 and tstat(r1) >= 2.0
                      and r1.sum() > p99)
    b1 = np.concatenate(list(res[("B", 1.0)].values()))
    b3 = np.concatenate(list(res[("B", 3.0)].values()))
    g1 = np.concatenate(list(res[("gel", 1.0)].values()))
    g3 = np.concatenate(list(res[("gel", 3.0)].values()))
    s = np.sort(b1)[::-1]
    top3, cap = s[3:].sum(), np.minimum(b1, 5.0).sum()
    pos = sum(x.sum() > 0 for x in res[("B", 1.0)].values())
    print(f"  B : n={len(b1)} gagnants={(b1 > 0).mean():.0%} net={b1.sum():+.1f}R t={tstat(b1):+.2f} | 3pt {b3.sum():+.1f}R | "
          f"sans top 3 {top3:+.1f}R | plafond 5R {cap:+.1f}R | marches positifs {pos}/10")
    print(f"      principale figee (memes barres): n={len(g1)} net={g1.sum():+.1f}R | 3pt {g3.sum():+.1f}R")
    verdict["B"] = (b1.sum() > g1.sum() and b3.sum() > g3.sum() and b3.sum() > 0 and top3 > 0 and cap > 0 and pos >= 6
                    and tstat(b1) >= 2.0)
    print("\nRegles fixees avant:")
    for v, label in (("A1", "Supertrend seul"), ("A2", "Supertrend + rien en range (ADX < 20)"),
                     ("B", "principale + sortie Supertrend")):
        print(f"  {v} {label}: {'A SUIVRE EN REEL (sans argent)' if verdict[v] else 'REJETEE'}")
    print("\n29/10 (information, hors decision):")
    print("\n".join(today))


if __name__ == "__main__":
    main()
