"""First pullback to the VWAP after a strong opening, rules fixed on
2026-10-29 BEFORE running (idea from the 29/10 CAC morning: strong gap up
at the 9:00 open, then a dip back to the VWAP around 9:45 before the run
to 7983). Because the idea comes from 29/10, the decision uses bars
BEFORE 2026-10-29 only; 29/10 is shown for information.

15m bars, each market's cash session (scripts/gap_fill_test.py): European
futures open 9:00 and end 17:30 Paris; US futures open 9:30 and end 16:00
New York.
  drive    the "l'ecart continue" condition (frozen_gap_continuation.py):
           the first 15m bar of the cash session closes AWAY from the
           previous official daily close R, 0.25 x daily ATR(14) <=
           |C0 - R| <= 1.0 x daily ATR(14), and that bar has not touched R.
           Buy side if C0 > R, sell side if C0 < R
  VWAP     volume-weighted typical price (H+L+C)/3, anchored at the first
           bar of the cash session; a bar is compared with the VWAP known
           at the PREVIOUS bar's close (no look-ahead)
  entry    at the close of the first bar, among the bars closing from the
           open +30min to the open +2h30, whose low touches that VWAP and
           which closes back above it (mirror for the sell side: high
           touches, close back below). At most one trade per market per day
  stop     the lowest low of the cash session so far, entry bar included
           (highest high for a sell)
  minimum  risk (entry to stop) >= 0.2 x daily ATR(14), else no trade
  target   2R (entry +/- 2 x risk)
  exit     at the close of the last bar of the cash session (no night)
A bar that touches both stop and target counts as a stop. A stop is
filled at the stop, or at the open if the bar opens beyond it. The entry
bar never counts for exits. Cost 1pt and 3pt CAC-equivalent (fixed
per-market factors from scripts/frozen_15m_calls_trend.py).

Random baseline: for each real trade, a random cash-session day of the
same market, entry at the close of the 3rd bar of the cash session (open
+45min), random direction, same risk in daily ATR, same 2R target and
session-end exit; 200 draws.

Decision rule (fixed before running), same as scripts/gap_fill_test.py and
scripts/opening_range_test.py, bars before 2026-10-29: worth live tracking
(without money, as a new frozen candidate) only if, pooling the 10
markets: net R > 0 at 1pt AND 3pt; both halves of the history (per-market
time halves, summed) > 0 at 1pt; at least 6 of 10 markets > 0 at 1pt; and
the pooled net R at 1pt beats the 95th percentile of the random baseline.
Otherwise rejected, no re-tuning (no other reference line, window, stop,
target or exit tried).

Usage: python scripts/opening_pullback_test.py
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
from other_markets_test import tstat

DECISION_END = "2026-10-29"
MIN_RISK_ATR = 0.2
TARGET_R = 2.0


def days(symbol, d):
    """Per cash-session day: (first bar index, last bar index of the session)."""
    _, open_h, end_h = session(symbol)
    h, date = local_clock(symbol, d)
    out = []
    for i0 in np.flatnonzero(np.isclose(h, open_h + 0.25)):
        last = np.flatnonzero((date == date[i0]) & (h <= end_h + 1e-9))[-1]
        if last > i0:
            out.append((i0, last))
    return out


def trades(symbol, d, cost):
    _, open_h, _ = session(symbol)
    h, _ = local_clock(symbol, d)
    ref, datr = daily_ref(symbol, d)
    o, hi, lo, c, v = (d[x].to_numpy() for x in ("Open", "High", "Low", "Close", "Volume"))
    rows = []
    for i0, last in days(symbol, d):
        r, a = ref[i0], datr[i0]
        if np.isnan(r) or np.isnan(a):
            continue
        gap = c[i0] - r
        side = 1 if gap > 0 else -1
        touched = lo[i0] <= r if side == 1 else hi[i0] >= r
        if not (0.25 * a <= abs(gap) <= 1.0 * a) or touched:
            continue
        seg = np.arange(i0, last + 1)
        tp = (hi[seg] + lo[seg] + c[seg]) / 3
        vol = v[seg].astype(float)
        if vol.sum() <= 0:
            continue
        vwap = np.cumsum(tp * vol) / np.maximum(np.cumsum(vol), 1e-12)
        for k, j in enumerate(seg[1:], start=1):
            if not (open_h + 0.5 - 1e-9 <= h[j] <= open_h + 2.5 + 1e-9) or j >= last:
                continue
            ref_v = vwap[k - 1]
            hit = (lo[j] <= ref_v and c[j] > ref_v) if side == 1 else (hi[j] >= ref_v and c[j] < ref_v)
            if not hit:
                continue
            stop = lo[i0:j + 1].min() if side == 1 else hi[i0:j + 1].max()
            risk = abs(c[j] - stop)
            if risk >= MIN_RISK_ATR * datr[j]:
                take = c[j] + side * TARGET_R * risk
                px = walk(d, j, last, side, stop, take)
                rows.append({"time": d.index[j], "side": side, "entry": c[j], "stop": stop, "take": take,
                             "risk_atr": risk / datr[j], "net_r": side * (px - c[j]) / risk - cost / risk})
            break
    return pd.DataFrame(rows, columns=["time", "side", "entry", "stop", "take", "risk_atr", "net_r"])


def main():
    now = pd.Timestamp.now(tz="UTC")
    rng = np.random.default_rng(0)
    pooled = {1.0: [], 3.0: []}
    halves, positive, rand_totals = [0.0, 0.0], 0, np.zeros(200)
    today = []
    for symbol, (name, k) in MARKETS.items():
        full = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        d = full[full.index < DECISION_END]
        half = d.index[len(d) // 2]
        line = {}
        for cost in (1.0, 3.0):
            t = trades(symbol, d, cost * k)
            r = t.net_r.to_numpy()
            pooled[cost].append(r)
            line[cost] = f"n={len(t):3d} gagnants={(r > 0).mean() if len(r) else 0:4.0%} net={r.sum():+6.1f}R"
            if cost == 1.0:
                halves[0] += t[t.time < half].net_r.sum()
                halves[1] += t[t.time >= half].net_r.sum()
                positive += r.sum() > 0
                real_t = t
        _, datr = daily_ref(symbol, d)
        pool = [(i0 + 2, last) for i0, last in days(symbol, d) if i0 + 2 < last and not np.isnan(datr[i0 + 2])]
        c = d.Close.to_numpy()
        for s in range(200):
            tot = 0.0
            for x in real_t.itertuples():
                j, last = pool[rng.integers(len(pool))]
                side = int(rng.choice((1, -1)))
                dist = x.risk_atr * datr[j]
                px = walk(d, j, last, side, c[j] - side * dist, c[j] + side * TARGET_R * dist)
                tot += side * (px - c[j]) / dist - 1.0 * k / dist
            rand_totals[s] += tot
        calls, puts = real_t[real_t.side == 1].net_r.sum(), real_t[real_t.side == -1].net_r.sum()
        print(f"{name:14s} 1pt-eq: {line[1.0]} (achats {calls:+.1f}R, ventes {puts:+.1f}R) | 3pt-eq: {line[3.0]}")
        t = trades(symbol, full, 1.0 * k)
        for x in t[t.time >= DECISION_END].itertuples():
            today.append(f"  {name:14s} {x.time.tz_convert('Europe/Paris'):%d/%m %H:%M} {'achat' if x.side == 1 else 'vente'} "
                         f"entree {x.entry:.2f} stop {x.stop:.2f} cible {x.take:.2f} -> {x.net_r:+.2f}R (provisoire si seance en cours)")
    r1, r3 = np.concatenate(pooled[1.0]), np.concatenate(pooled[3.0])
    p95 = np.percentile(rand_totals, 95)
    print(f"\n10 marches ensemble, avant le 29/10: 1pt-eq n={len(r1)} gagnants={(r1 > 0).mean():.0%} net={r1.sum():+.1f}R "
          f"moy={r1.mean():+.3f}R t={tstat(r1):+.2f} | 3pt-eq net={r3.sum():+.1f}R")
    print(f"  moities {halves[0]:+.1f}/{halves[1]:+.1f}R | marches positifs {positive}/10 | "
          f"hasard: mediane {np.median(rand_totals):+.1f}R, 95e centile {p95:+.1f}R")
    ok = r1.sum() > 0 and r3.sum() > 0 and min(halves) > 0 and positive >= 6 and r1.sum() > p95
    print(f"\nRegle fixee avant: {'A SUIVRE EN REEL (sans argent)' if ok else 'REJETEE'}")
    print("\n29/10 (information, hors decision):")
    print("\n".join(today) if today else "  aucun trade")


if __name__ == "__main__":
    main()
