"""Setups drawn from the 22/10 session, fixed on 2026-10-22 BEFORE testing.

On 22/10 the CAC fell in a staircase until 11:43 (lower highs at 09:47,
10:47, 11:17, each followed by a 20-30pt drop), flipped (break above the
last lower high around 12:05) and climbed in a staircase of higher lows
(12:20, 13:24) for +40pts. The sweep strategy caught none of the falling
legs: it only trades reversals. Two continuation setups describe the day:

  P1 "swing in trend": in a trend (last break of structure up or down),
     enter when a new swing confirms in the trend direction - a higher low
     in an up trend (call), a lower high in a down trend (put). Entry at
     the close of the confirmation bar (swing bar + 2, no look-ahead).
  P2 "first pullback after a flip": same, but only the first such swing
     after a change of character (the first higher low after a bullish
     CHoCH, the first lower high after a bearish one).

Trade rules (fixed): stop 2pt beyond the swing extreme, risk at least
1x ATR(14); target 2R; entries 09:15-17:00 Paris only; any trade still
open at the last bar of the Paris day is closed at its close (no overnight,
turbo-friendly, every day starts flat); one trade at a time. Cost 1pt and
3pt round trip.

Random baseline: for each real trade, an entry on a random allowed bar in
the trend direction with the same risk in ATR units and the same exits;
200 draws give the "trade with the trend at random times" distribution.

Test data stop on 21/10 (22/10 inspired the idea; shown for info only).

Decision rule (fixed before running): a setup shows an edge worth tracking
only if at 3pt cost it is positive on BOTH halves on 5m AND 15m, and its
mean R per trade beats the random baseline's 95th percentile on both.

Usage: python scripts/structure_pullback_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from finta import TA

from data import cache
from levels import structure

SYMBOL = "FCE1!"
N = 2
MARGIN = 2.0
RR = 2.0
TEST_END = "2026-10-22"
HOURS = (9.25, 17.0)


def prepare(d):
    d = d.copy()
    d["atr"] = TA.ATR(d, 14)
    is_hi, is_lo = structure.find_swings(d, n=N)
    sh = structure.confirmed_level(is_hi, d.High, N)
    sl = structure.confirmed_level(is_lo, d.Low, N)
    bull, bear = structure.bos_events(d.Close, sh, sl)
    choch = structure.choch_events(bull, bear)
    trend = pd.Series(np.where(bull, 1, np.where(bear, -1, np.nan)), index=d.index).ffill().fillna(0)
    d["trend"] = trend.to_numpy()
    d["choch_up"] = (choch & bull).to_numpy()
    d["choch_dn"] = (choch & bear).to_numpy()
    lo_mark = structure.confirmed_marks(is_lo, d.Low, N)   # value at confirmation bar
    hi_mark = structure.confirmed_marks(is_hi, d.High, N)
    d["lo_mark"], d["hi_mark"] = lo_mark.to_numpy(), hi_mark.to_numpy()
    paris = d.index.tz_convert("Europe/Paris")
    d["hour"] = paris.hour + paris.minute / 60
    day = paris.date
    d["last_of_day"] = np.append(day[1:] != day[:-1], True)
    d["day"] = day
    return d


def signals(d, first_only):
    """List of (i, side, stop) at confirmation bars."""
    out = []
    prev_lo = prev_hi = np.nan
    armed_up = armed_dn = False
    for i in range(len(d)):
        if d.choch_up.iat[i]:
            armed_up = True
        if d.choch_dn.iat[i]:
            armed_dn = True
        lo, hi = d.lo_mark.iat[i], d.hi_mark.iat[i]
        if not np.isnan(lo):
            if d.trend.iat[i] == 1 and not np.isnan(prev_lo) and lo > prev_lo and (armed_up or not first_only):
                out.append((i, 1, lo - MARGIN))
                armed_up = False
            prev_lo = lo
        if not np.isnan(hi):
            if d.trend.iat[i] == -1 and not np.isnan(prev_hi) and hi < prev_hi and (armed_dn or not first_only):
                out.append((i, -1, hi + MARGIN))
                armed_dn = False
            prev_hi = hi
    return out


def simulate(d, entries, cost):
    """entries: list of (i, side, risk_points). One trade at a time, exits at
    stop/target or at the last bar of the Paris day."""
    hi, lo, cl, last = d.High.to_numpy(), d.Low.to_numpy(), d.Close.to_numpy(), d.last_of_day.to_numpy()
    trades, busy_until = [], -1
    for i, side, risk in sorted(entries):
        if i <= busy_until or last[i] or not (HOURS[0] <= d.hour.iat[i] < HOURS[1]):
            continue
        entry = cl[i]
        stop, take = entry - side * risk, entry + side * RR * risk
        r, j = None, i
        for j in range(i + 1, len(d)):
            if (lo[j] <= stop) if side == 1 else (hi[j] >= stop):
                r = -1.0
                break
            if (hi[j] >= take) if side == 1 else (lo[j] <= take):
                r = RR
                break
            if last[j]:
                r = side * (cl[j] - entry) / risk
                break
        if r is None:
            break
        trades.append({"time": d.index[i], "side": side, "entry": entry, "risk": risk, "net_r": r - cost / risk})
        busy_until = j
    return pd.DataFrame(trades, columns=["time", "side", "entry", "risk", "net_r"])


def real_entries(d, first_only):
    out = []
    for i, side, stop in signals(d, first_only):
        risk = max((d.Close.iat[i] - stop) * side, d.atr.iat[i] if not np.isnan(d.atr.iat[i]) else 0.0)
        if risk > 0:
            out.append((i, side, risk))
    return out


def random_baseline(d, real, cost, draws=200, seed=0):
    rng = np.random.default_rng(seed)
    allowed = np.flatnonzero((d.hour.to_numpy() >= HOURS[0]) & (d.hour.to_numpy() < HOURS[1])
                             & (d.trend.to_numpy() != 0) & ~d.last_of_day.to_numpy() & ~np.isnan(d.atr.to_numpy()))
    atr_units = [risk / d.atr.iat[i] for i, _, risk in real if d.atr.iat[i] > 0]
    means = []
    for _ in range(draws):
        picks = rng.choice(allowed, size=len(atr_units), replace=False)
        ent = [(int(i), int(d.trend.iat[i]), u * d.atr.iat[i]) for i, u in zip(picks, atr_units)]
        t = simulate(d, ent, cost)
        means.append(t.net_r.mean() if len(t) else 0.0)
    return np.percentile(means, [50, 95])


def main():
    now = pd.Timestamp.now(tz="UTC")
    verdict = {"P1": [], "P2": []}
    for iv in ("1m", "5m", "15m"):
        full = prepare(cache.closed_bars(cache.load(SYMBOL, iv), iv, now))
        d = full[full.index < TEST_END]
        half = d.index[len(d) // 2]
        print(f"\n######## {iv}: {d.index[0].date()} -> {d.index[-1].date()} (moitie au {half.date()})")
        for name, first_only in (("P1", False), ("P2", True)):
            real = real_entries(d, first_only)
            for cost in (1.0, 3.0):
                t = simulate(d, real, cost)
                r = t.net_r.to_numpy()
                ts = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 1 else float("nan")
                h1, h2 = t[t.time < half].net_r.sum(), t[t.time >= half].net_r.sum()
                p50, p95 = random_baseline(d, real, cost, draws=100 if iv == "1m" else 200)
                c, p = t[t.side == 1], t[t.side == -1]
                print(f"  {name} cout {cost:.0f}pt: n={len(t):3d} gagnants={(r > 0).mean() if len(r) else 0:4.0%} net={r.sum():+6.1f}R moy={r.mean() if len(r) else 0:+.3f}R t={ts:+.2f} "
                      f"| calls {len(c)} {c.net_r.sum():+.1f}R puts {len(p)} {p.net_r.sum():+.1f}R | moities {h1:+.1f}/{h2:+.1f} | hasard moy {p50:+.3f} (95e {p95:+.3f})")
                if cost == 3.0 and iv in ("5m", "15m"):
                    verdict[name].append(h1 > 0 and h2 > 0 and len(r) > 0 and r.mean() > p95)
        today = full[full.index >= TEST_END]
        if len(today):
            t = simulate(full, [e for e in real_entries(full, False) if full.index[e[0]] >= pd.Timestamp(TEST_END, tz="UTC")], 1.0)
            print(f"  (info 22/10, P1 cout 1pt: " + ", ".join(f"{x.time.tz_convert('Europe/Paris'):%H:%M} {'call' if x.side == 1 else 'put'} {x.net_r:+.2f}R" for x in t.itertuples()) + ")")
    print("\nRegle fixee avant (3pt, 2 moities positives en 5m ET 15m, et mieux que le 95e centile du hasard):")
    for k, v in verdict.items():
        print(f"  {k}: {'EDGE A SUIVRE' if v and all(v) else 'pas d edge demontre'}")


if __name__ == "__main__":
    main()
