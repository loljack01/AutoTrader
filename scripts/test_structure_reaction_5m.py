"""Reaction trades in the direction of the 5m structure, with levels fixed
at 9:15, rules fixed on 2026-11-03 BEFORE running, at the user's request
(17th idea). Origin: on 03/11 the CAC rose all morning (higher 5m lows)
while the reaction trades taken were puts only; the proposed correction
is "trade only in the direction of the 5m structure, with levels rebuilt
at 9:15, and the same criteria for calls and puts". 03/11 itself, which
inspired the idea, is EXCLUDED from the test.

Data: FCE1! (CAC 40 future) 5m bars, all sessions in the cache strictly
before 2026-11-03 (5m history starts 24/08/2026: about 50 sessions, a
short sample - read the result as indicative). Times in Paris.

Levels, computed once per session at 9:15 and not changed afterwards:
  previous day high, low and close (previous daily bar of the data feed),
  high and low of the session's 5m bars from 8:00 to 9:15 (bars 8:00 to
  9:10), and every multiple of 50 points within +/-150 points of the
  open of the 9:15 bar.

5m structure (continuous series, all bars): swing high / low = bar whose
high (low) is the highest (lowest) of the 2 bars on each side; confirmed
at the close of the 2nd bar after it. At each bar, from the swings
confirmed so far:
  call side allowed  if the last swing low  > the previous swing low
                     (higher lows)
  put side allowed   if the last swing high < the previous swing high
                     (lower highs)
  if both are true at once (contraction) no trade.

Trigger (bar opening between 9:15 and 17:00 inclusive, except the bars
opening 15:30 and 15:35 - US cash open):
  call  call side allowed; for some level L: previous bar close >= L, this
        bar's low < L, this bar's close > L (sweep then close back above).
  put   mirror: previous close <= L, high > L, close < L.
Entry at the close of the trigger bar. Stop: call = bar low - 8 points,
put = bar high + 8 points. Target: the nearest level strictly beyond the
entry in the trade's direction. Taken only if the net R:R
(target distance - cost) / (stop distance + cost) >= 1.3, otherwise
skipped (no other level is tried). One position at a time; the bar that
closes a position cannot open a new one. Exit: stop or target checked
from the next bar (a bar touching both counts as a stop), otherwise at
the close of the 17:25 bar (17:30); never held overnight. Costs 1 point
and 3 points round trip.

Comparison, same triggers and rules but WITHOUT the structure filter
(both sides allowed on every bar): "sans filtre".

Decision rule (fixed before running), structure version at 1 point unless
stated: worth live tracking WITHOUT money (frozen, next to the main
strategy, which does not change) only if ALL of:
  - at least 30 closed trades;
  - net > 0 at 3 points;
  - net > 0 with every gain capped at +5R;
  - both halves of the period (split at the middle session) > 0;
  - average R per trade above the "sans filtre" version;
  - net above the 95th percentile of 2000 random subsets (seed 0) of the
    same size drawn from the "sans filtre" trades.
Otherwise REJETE, no re-tuning (no other swing length, level set, margin,
window, R:R or target is tried).

Result (run on 2026-11-03, 51 sessions 24/08 -> 02/11): REJETE.
Structure version 56 trades, 34% winners, +1.9R at 1pt (+0.034R/trade),
+1.8R at 3pt (41 trades), capped +1.9R, but halves +13.5R / -11.6R and
below the random 95th percentile (+12.5R). Calls -8.4R (27), puts +10.3R
(29): the calls taken on higher 5m lows - the very case that inspired the
idea - lost. "Sans filtre": 145 trades, -4.9R at 1pt, -24.4R at 3pt.

Usage: python scripts/test_structure_reaction_5m.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache

SYMBOL, END = "FCE1!", "2026-11-03"
MARGIN, MIN_RR, N, MIN_TRADES = 8.0, 1.3, 2, 30
TZ = "Europe/Paris"


def load():
    now = pd.Timestamp.now(tz="UTC")
    d = cache.closed_bars(cache.load(SYMBOL, "5m"), "5m", now)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(TZ)
    d = d[d.index.date < pd.Timestamp(END).date()]
    daily = cache.load(SYMBOL, "1D")
    daily.index = pd.to_datetime(daily.index, utc=True).tz_convert(TZ)
    return d, daily


def structure(d):
    """Per bar: (call side allowed, put side allowed) from confirmed swings."""
    h, l = d.High.to_numpy(), d.Low.to_numpy()
    n = len(d)
    call_ok, put_ok = np.zeros(n, bool), np.zeros(n, bool)
    sh, sl = [], []
    for t in range(n):
        i = t - N  # swing candidate confirmed at the close of bar t
        if i - N >= 0:
            if h[i] >= h[i - N:i + N + 1].max():
                sh.append(h[i])
            if l[i] <= l[i - N:i + N + 1].min():
                sl.append(l[i])
        hl = len(sl) >= 2 and sl[-1] > sl[-2]
        lh = len(sh) >= 2 and sh[-1] < sh[-2]
        call_ok[t], put_ok[t] = hl and not lh, lh and not hl
    return call_ok, put_ok


def day_levels(day, prev):
    early = day[(day.index.strftime("%H:%M") >= "08:00") & (day.index.strftime("%H:%M") < "09:15")]
    at915 = day[day.index.strftime("%H:%M") == "09:15"]
    if early.empty or at915.empty:
        return None
    o = at915.Open.iloc[0]
    lv = {prev.High, prev.Low, prev.Close, early.High.max(), early.Low.min()}
    lv |= {float(x) for x in np.arange(np.ceil((o - 150) / 50) * 50, o + 150 + 1e-9, 50)}
    return np.array(sorted(lv))


def run(d, daily, cost, use_structure):
    call_ok, put_ok = structure(d)
    if not use_structure:
        call_ok[:], put_ok[:] = True, True
    pos_of = {ts: k for k, ts in enumerate(d.index)}
    trades = []
    ddate = np.array(daily.index.date)
    for date, day in d.groupby(d.index.date):
        prev = daily[ddate < date]
        if prev.empty:
            continue
        lv = day_levels(day, prev.iloc[-1])
        if lv is None:
            continue
        hm = day.index.strftime("%H:%M")
        pos = None
        for j in range(1, len(day)):
            ts, b, pb = day.index[j], day.iloc[j], day.iloc[j - 1]
            k = pos_of[ts]
            closed_now = False
            if pos is not None:
                s = pos["s"]
                hit_stop = b.Low <= pos["stop"] if s == 1 else b.High >= pos["stop"]
                hit_take = b.High >= pos["take"] if s == 1 else b.Low <= pos["take"]
                px = pos["stop"] if hit_stop else pos["take"] if hit_take else (b.Close if hm[j] == "17:25" or j == len(day) - 1 else None)
                if px is not None:
                    res = "stop" if hit_stop else "take" if hit_take else "1730"
                    trades.append({"date": date, "side": "call" if s == 1 else "put", "entry_time": pos["t"],
                                   "result": res, "net_r": (s * (px - pos["e"]) - cost) / pos["risk"]})
                    pos, closed_now = None, True
            if pos is not None or closed_now or not ("09:15" <= hm[j] <= "17:00") or hm[j] in ("15:30", "15:35"):
                continue
            for s, ok in ((1, call_ok[k]), (-1, put_ok[k])):
                if not ok:
                    continue
                if s == 1:
                    swept = lv[(pb.Close >= lv) & (b.Low < lv) & (b.Close > lv)]
                else:
                    swept = lv[(pb.Close <= lv) & (b.High > lv) & (b.Close < lv)]
                if not len(swept):
                    continue
                e = b.Close
                stop = b.Low - MARGIN if s == 1 else b.High + MARGIN
                beyond = lv[lv > e] if s == 1 else lv[lv < e]
                if not len(beyond):
                    continue
                take = beyond.min() if s == 1 else beyond.max()
                risk, reward = abs(e - stop), abs(take - e)
                if (reward - cost) / (risk + cost) < MIN_RR:
                    continue
                pos = {"s": s, "e": e, "stop": stop, "take": take, "risk": risk, "t": ts}
                break
    return pd.DataFrame(trades, columns=["date", "side", "entry_time", "result", "net_r"])


def line(label, t):
    r = t.net_r.to_numpy()
    if not len(r):
        return f"  {label:24s} 0 trade"
    return (f"  {label:24s} {len(r):3d} trades, {(r > 0).mean():4.0%} gagnants, net {r.sum():+6.1f}R "
            f"({r.mean():+.3f}R/trade), plafond 5R {np.minimum(r, 5).sum():+6.1f}R | "
            f"calls {t[t.side == 'call'].net_r.sum():+.1f}R ({(t.side == 'call').sum()}), "
            f"puts {t[t.side == 'put'].net_r.sum():+.1f}R ({(t.side == 'put').sum()}) | "
            f"cible {(t.result == 'take').sum()}, stop {(t.result == 'stop').sum()}, 17h30 {(t.result == '1730').sum()}")


def main():
    d, daily = load()
    s1, s3 = run(d, daily, 1.0, True), run(d, daily, 3.0, True)
    u1, u3 = run(d, daily, 1.0, False), run(d, daily, 3.0, False)
    dates = sorted(set(d.index.date))
    print(f"FCE1! 5m, {len(dates)} seances ({dates[0]} -> {dates[-1]})")
    print(line("structure, 1pt", s1))
    print(line("structure, 3pt", s3))
    print(line("sans filtre, 1pt", u1))
    print(line("sans filtre, 3pt", u3))
    mid = dates[len(dates) // 2]
    h1, h2 = s1[s1.date < mid].net_r.sum(), s1[s1.date >= mid].net_r.sum()
    r, base = s1.net_r.to_numpy(), u1.net_r.to_numpy()
    rng = np.random.default_rng(0)
    rand = (np.array([rng.choice(base, len(r), replace=False).sum() for _ in range(2000)])
            if 0 < len(r) <= len(base) else np.array([np.inf]))
    p95 = np.percentile(rand, 95)
    cap = np.minimum(r, 5).sum()
    rpt, upt = (r.mean() if len(r) else 0.0), (base.mean() if len(base) else 0.0)
    print(f"\nStructure : moities (coupure {mid}) {h1:+.1f}R / {h2:+.1f}R | R/trade {rpt:+.3f} contre {upt:+.3f} sans filtre "
          f"| 95e centile du hasard {p95:+.1f}R")
    ok = (len(r) >= MIN_TRADES and s3.net_r.sum() > 0 and cap > 0 and h1 > 0 and h2 > 0
          and rpt > upt and r.sum() > p95)
    print(f"\nRegle fixee avant : reaction dans le sens de la structure 5m {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
