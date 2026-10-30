"""Opening range breakout with the trend, rules fixed on 2026-10-29 BEFORE
running (idea seen on the 29/10 CAC morning: the 8:00-9:00 range broke up
at the 9:00 open and ran +55pt; the main strategy had no sweep, so no
trade). Because the idea comes from 29/10, the decision uses bars BEFORE
2026-10-29 only; 29/10 is shown for information.

15m bars, each market's cash session (scripts/gap_fill_test.py): European
futures open 9:00 and end 17:30 Paris; US futures open 9:30 and end 16:00
New York.
  range    high H and low L of the 4 bars of the hour before the cash
           open (Europe 8:00-9:00 Paris, US 8:30-9:30 New York); all 4
           bars must exist, else no trade that day
  trigger  the FIRST 15m close outside the range among the bars closing
           from the open +15min to the open +2h: above H = buy, below L =
           sell. Only that first break counts (one trade per market per
           day at most)
  trend    "with the trend" (decision version): a buy only if the previous
           daily close is above its 20-day SMA (same filter as the main
           strategy, ma_grid_test.trend_up), a sell only if it is below.
           A first break against the trend means no trade that day
  entry    at the close of the trigger bar
  stop     the other side of the range (L for a buy, H for a sell)
  minimum  risk (entry to stop) >= 0.2 x daily ATR(14) of the previous
           day, else no trade (a turbo cannot hold a tighter stop)
  target   1:1 (entry +/- risk)
  exit     at the close of the last bar of the cash session (no night)
A bar that touches both stop and target counts as a stop. A stop is
filled at the stop, or at the open if the bar opens beyond it. The entry
bar never counts for exits. Cost 1pt and 3pt CAC-equivalent (fixed
per-market factors from scripts/frozen_15m_calls_trend.py).

Shown for information only: "sans filtre" (first break taken either way).

Random baseline: for each real trade, a random cash-session day of the
same market, entry at its first 15m close of the cash session, random
direction, same risk in daily ATR, same 1:1 target and session-end exit;
200 draws.

Decision rule (fixed before running), same as scripts/gap_fill_test.py,
on the "with the trend" version, bars before 2026-10-29: worth live
tracking (without money, as a new frozen candidate) only if, pooling the
10 markets: net R > 0 at 1pt AND 3pt; both halves of the history
(per-market time halves, summed) > 0 at 1pt; at least 6 of 10 markets > 0
at 1pt; and the pooled net R at 1pt beats the 95th percentile of the
random baseline. Otherwise rejected, no re-tuning (no other range,
window, filter, target or exit tried).

Usage: python scripts/opening_range_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from gap_fill_test import daily_ref, local_clock, session, walk
from ma_grid_test import BAR
from other_markets_test import tstat

DECISION_END = "2026-10-29"
SMA = 20
MIN_RISK_ATR = 0.2


def trend(symbol, d):
    """+1 / -1 / 0: previous daily close above / below its SMA20, known at each 15m close."""
    daily = bt.cache.load(symbol, "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    c = daily.Close
    ma = c.rolling(SMA).mean()
    sign = np.where(ma.notna(), np.sign(c - ma), 0)
    done_at = (daily.index + pd.Timedelta(days=1)).to_numpy()
    pos = np.searchsorted(done_at, (d.index + BAR).to_numpy(), side="right") - 1
    return np.where(pos >= 0, sign[np.clip(pos, 0, None)], 0)


def sessions(symbol, d):
    """Per day: (range high, range low, window indices, session last index, first cash bar index)."""
    _, open_h, end_h = session(symbol)
    h, date = local_clock(symbol, d)
    idx = np.arange(len(d))
    out = []
    for i0 in np.flatnonzero(np.isclose(h, open_h + 0.25)):
        same = date == date[i0]
        pre = np.flatnonzero(same & (h > open_h - 1.0 + 1e-9) & (h < open_h + 1e-9))
        if len(pre) != 4:
            continue
        window = np.flatnonzero(same & (idx >= i0) & (h <= open_h + 2.0 + 1e-9))
        last = np.flatnonzero(same & (h <= end_h + 1e-9))[-1]
        out.append((d.High.to_numpy()[pre].max(), d.Low.to_numpy()[pre].min(), window, last, i0))
    return out


def trades(symbol, d, cost, with_trend):
    side_of_trend = trend(symbol, d)
    _, datr = daily_ref(symbol, d)
    c = d.Close.to_numpy()
    rows = []
    for hi, lo, window, last, _ in sessions(symbol, d):
        brk = [j for j in window if c[j] > hi or c[j] < lo]
        if not brk:
            continue
        j = brk[0]
        side = 1 if c[j] > hi else -1
        if with_trend and side_of_trend[j] != side:
            continue
        stop = lo if side == 1 else hi
        risk = abs(c[j] - stop)
        if np.isnan(datr[j]) or risk < MIN_RISK_ATR * datr[j] or j >= last:
            continue
        px = walk(d, j, last, side, stop, c[j] + side * risk)
        rows.append({"time": d.index[j], "side": side, "entry": c[j], "stop": stop, "take": c[j] + side * risk,
                     "risk_atr": risk / datr[j], "net_r": side * (px - c[j]) / risk - cost / risk})
    return pd.DataFrame(rows, columns=["time", "side", "entry", "stop", "take", "risk_atr", "net_r"])


def main():
    now = pd.Timestamp.now(tz="UTC")
    rng = np.random.default_rng(0)
    pooled = {(v, c): [] for v in ("tendance", "sans filtre") for c in (1.0, 3.0)}
    halves, positive, rand_totals = [0.0, 0.0], 0, np.zeros(200)
    today = []
    for symbol, (name, k) in MARKETS.items():
        full = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        d = full[full.index < DECISION_END]
        half = d.index[len(d) // 2]
        line = {}
        for v, wt in (("tendance", True), ("sans filtre", False)):
            for cost in (1.0, 3.0):
                t = trades(symbol, d, cost * k, wt)
                r = t.net_r.to_numpy()
                pooled[(v, cost)].append(r)
                line[(v, cost)] = f"n={len(t):3d} gagnants={(r > 0).mean() if len(r) else 0:4.0%} net={r.sum():+6.1f}R"
                if v == "tendance" and cost == 1.0:
                    halves[0] += t[t.time < half].net_r.sum()
                    halves[1] += t[t.time >= half].net_r.sum()
                    positive += r.sum() > 0
                    real_t = t
        _, datr = daily_ref(symbol, d)
        pool = [(i0, last) for _, _, _, last, i0 in sessions(symbol, d) if not np.isnan(datr[i0]) and i0 < last]
        c = d.Close.to_numpy()
        for s in range(200):
            tot = 0.0
            for x in real_t.itertuples():
                i0, last = pool[rng.integers(len(pool))]
                side = int(rng.choice((1, -1)))
                dist = x.risk_atr * datr[i0]
                px = walk(d, i0, last, side, c[i0] - side * dist, c[i0] + side * dist)
                tot += side * (px - c[i0]) / dist - 1.0 * k / dist
            rand_totals[s] += tot
        print(f"{name:14s} tendance    1pt-eq: {line[('tendance', 1.0)]} | 3pt-eq: {line[('tendance', 3.0)]}")
        print(f"{'':14s} sans filtre 1pt-eq: {line[('sans filtre', 1.0)]} | 3pt-eq: {line[('sans filtre', 3.0)]}")
        t = trades(symbol, full, 1.0 * k, True)
        for x in t[t.time >= DECISION_END].itertuples():
            today.append(f"  {name:14s} {x.time.tz_convert('Europe/Paris'):%d/%m %H:%M} {'achat' if x.side == 1 else 'vente'} "
                         f"entree {x.entry:.2f} stop {x.stop:.2f} cible {x.take:.2f} -> {x.net_r:+.2f}R (provisoire si seance en cours)")
    print("\n## 10 marches ensemble, avant le 29/10")
    for v in ("tendance", "sans filtre"):
        r1, r3 = np.concatenate(pooled[(v, 1.0)]), np.concatenate(pooled[(v, 3.0)])
        print(f"  {v:11s} 1pt-eq n={len(r1)} gagnants={(r1 > 0).mean():.0%} net={r1.sum():+.1f}R moy={r1.mean():+.3f}R "
              f"t={tstat(r1):+.2f} | 3pt-eq net={r3.sum():+.1f}R")
    r1, r3 = np.concatenate(pooled[("tendance", 1.0)]), np.concatenate(pooled[("tendance", 3.0)])
    p95 = np.percentile(rand_totals, 95)
    print(f"  tendance: moities {halves[0]:+.1f}/{halves[1]:+.1f}R | marches positifs {positive}/10 | "
          f"hasard: mediane {np.median(rand_totals):+.1f}R, 95e centile {p95:+.1f}R")
    ok = r1.sum() > 0 and r3.sum() > 0 and min(halves) > 0 and positive >= 6 and r1.sum() > p95
    print(f"\nRegle fixee avant: {'A SUIVRE EN REEL (sans argent)' if ok else 'REJETEE'}")
    print("\n29/10 (information, hors decision):")
    print("\n".join(today) if today else "  aucun trade")


if __name__ == "__main__":
    main()
