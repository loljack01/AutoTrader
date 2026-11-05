"""SWING strategy "Repli en tendance" (short-term mean reversion inside the
long-term trend, RSI(2) of Connors & Alvarez, "Short Term Trading
Strategies That Work", 2009), rules fixed on 2026-11-05 BEFORE running, at
the user's request ("build yourself a swing strategy"). 19th idea; the
first swing idea built from the literature rather than from a chart. The
standard published parameters are used as they are: nothing is tuned (no
other RSI length, threshold, average, stop or holding limit is tried).

Data: daily bars of the 10 cash indices in data/cache (TradingView price
indices, dividends excluded): EURONEXT:PX1, XETR:DAX, TVC:SX5E, SP:SPX,
NASDAQ:NDX, TVC:UKX, SIX:SMI, TVC:DJI, TVC:RUT, TVC:FTMIB, from 2011 (one
year of warm-up for the 200-day average), signals from 2012-01-01 to the
last cached day.

Rule, at each daily close (long side; the short side is the exact mirror):
  trend   close > SMA(200) of closes            (short: close < SMA200)
  signal  RSI(2) (Wilder) < 10                  (short: RSI(2) > 90)
  entry   at that close
  exit    first later close > SMA(5)            (short: close < SMA5)
          protective stop (needed for a turbo) 2.5 x ATR(14) daily from the
          entry, checked on each later day's low (high); if the day opens
          beyond the stop the exit is the open, else the stop
          time limit: close of the 10th day after entry
  one position per index at a time; a new signal is only taken after the
  previous trade is closed (the exit day can open a new trade at its close)
R = the stop distance (2.5 ATR). Costs, round trip: 0.05 % of the entry
price (turbo spread, base) and 0.10 % (stress).

Random baseline: for each index and side, the same number of trades
entered at random closes where the trend condition of that side holds
(no RSI condition), same exits, keeping as many trades as the real rule in that market (drawn at
random among the non-overlapping random trades); 200 draws (seed 0); pooled
net R.

Decision rule (fixed before running), judged SEPARATELY for the long side
(calls) and the short side (puts); a side is worth live tracking WITHOUT
money only if ALL of:
  - at least 100 closed trades;
  - net R > 0 at 0.05 % AND at 0.10 %;
  - net R > 0 in both halves of the period (split at 2019-01-01) at 0.05 %;
  - at least 7 of the 10 indices with net R > 0 at 0.05 %;
  - pooled net R at 0.05 % above the 95th percentile of the random baseline.
Otherwise REJETE for that side, no re-tuning.

Usage: python scripts/test_swing_rsi2.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache

INDICES = {"EURONEXT:PX1": "CAC 40", "XETR:DAX": "DAX", "TVC:SX5E": "Euro Stoxx 50", "SP:SPX": "S&P 500",
           "NASDAQ:NDX": "Nasdaq 100", "TVC:UKX": "FTSE 100", "SIX:SMI": "SMI", "TVC:DJI": "Dow Jones",
           "TVC:RUT": "Russell 2000", "TVC:FTMIB": "FTSE MIB"}
START, SPLIT = "2012-01-01", "2019-01-01"
COSTS = (0.0005, 0.0010)
STOP_ATR, MAX_DAYS, N_RANDOM = 2.5, 10, 200
MIN_TRADES, MIN_MARKETS = 100, 7


def load(symbol):
    d = cache.load(symbol, "1D")
    d.index = pd.to_datetime(d.index, utc=True)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    c = d.Close
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    d["rsi2"] = 100 - 100 / (1 + up / dn)
    d["sma200"] = c.rolling(200).mean()
    d["sma5"] = c.rolling(5).mean()
    tr = pd.concat([d.High - d.Low, (d.High - c.shift()).abs(), (d.Low - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return d


def exit_trade(a, i, side):
    """Exit index and price of a trade entered at the close of bar i."""
    o, h, l, c, s5, atr = a
    entry, risk = c[i], STOP_ATR * atr[i]
    stop = entry - side * risk
    last = min(i + MAX_DAYS, len(c) - 1)
    for j in range(i + 1, last + 1):
        if (side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop):
            gap = (o[j] <= stop) if side == 1 else (o[j] >= stop)
            return j, (o[j] if gap else stop), risk
        if (side == 1 and c[j] > s5[j]) or (side == -1 and c[j] < s5[j]):
            return j, c[j], risk
    return (last, c[last], risk) if last == i + MAX_DAYS else (None, None, risk)


def run(d, side, entries=None):
    """Trades of one side; entries = candidate bar indices (None = the RSI(2) rule)."""
    a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
    c = a[3]
    trend = (c > d.sma200.to_numpy()) if side == 1 else (c < d.sma200.to_numpy())
    if entries is None:
        rsi = d.rsi2.to_numpy()
        sig = trend & ((rsi < 10) if side == 1 else (rsi > 90))
        entries = np.flatnonzero(sig & (d.index >= START))
    rows, free = [], -1
    for i in entries:
        if i < free:
            continue
        j, px, risk = exit_trade(a, i, side)
        if j is None or not risk > 0:
            continue
        rows.append({"entry": d.index[i], "exit": d.index[j], "side": side, "entry_px": c[i],
                     "move_r": side * (px - c[i]) / risk, "cost_frac": c[i] / risk})
        free = j
    return pd.DataFrame(rows, columns=["entry", "exit", "side", "entry_px", "move_r", "cost_frac"])


def net(t, cost):
    return t.move_r - cost * t.cost_frac if len(t) else pd.Series(dtype=float)


def main():
    data = {s: load(s) for s in INDICES}
    last = min(d.index[-1] for d in data.values())
    print(f"Indices cash journaliers, signaux du {START} au {last:%d/%m/%Y}")
    rng = np.random.default_rng(0)
    for side, label in ((1, "CALLS (au-dessus de la SMA200, RSI(2) < 10)"), (-1, "PUTS (sous la SMA200, RSI(2) > 90)")):
        print(f"\n=== {label}")
        all_t, per_mkt, rand_tot = [], {}, np.zeros(N_RANDOM)
        for s, name in INDICES.items():
            d = data[s]
            t = run(d, side)
            all_t.append(t.assign(market=name))
            r = net(t, COSTS[0])
            per_mkt[name] = r.sum()
            c = d.Close.to_numpy()
            trend = (c > d.sma200.to_numpy()) if side == 1 else (c < d.sma200.to_numpy())
            pool = np.flatnonzero(trend & (d.index >= START) & (np.arange(len(d)) < len(d) - 1))
            for k in range(N_RANDOM):
                if len(t) and len(pool):
                    pick = np.sort(rng.choice(pool, min(len(pool), 3 * len(t)), replace=False))
                    rt = net(run(d, side, pick), COSTS[0]).to_numpy()
                    if len(rt):
                        rand_tot[k] += rng.choice(rt, min(len(t), len(rt)), replace=False).sum()
            print(f"  {name:14s} {len(t):4d} trades, {(r > 0).mean() if len(r) else 0:4.0%} gagnants, net {r.sum():+7.1f}R")
        t = pd.concat(all_t, ignore_index=True)
        r1, r2 = net(t, COSTS[0]), net(t, COSTS[1])
        h1 = r1[t.entry < SPLIT].sum()
        h2 = r1[t.entry >= SPLIT].sum()
        pos = sum(v > 0 for v in per_mkt.values())
        p95 = np.percentile(rand_tot, 95)
        hold = (t.exit - t.entry).dt.days.mean() if len(t) else 0
        print(f"  Total : {len(t)} trades, {(r1 > 0).mean():.0%} gagnants, net {r1.sum():+.1f}R a 0,05 % "
              f"({r1.mean():+.3f}R/trade), {r2.sum():+.1f}R a 0,10 % | detention moyenne {hold:.1f} jours")
        print(f"  Moities (coupure {SPLIT[:4]}) : {h1:+.1f}R / {h2:+.1f}R | indices positifs {pos}/10 | "
              f"hasard (tendance seule) 95e centile {p95:+.1f}R, mediane {np.median(rand_tot):+.1f}R")
        last12 = r1[t.entry >= last - pd.Timedelta(days=365)]
        print(f"  12 derniers mois : {len(last12)} trades, net {last12.sum():+.1f}R")
        ok = (len(t) >= MIN_TRADES and r1.sum() > 0 and r2.sum() > 0 and h1 > 0 and h2 > 0
              and pos >= MIN_MARKETS and r1.sum() > p95)
        print(f"  Regle fixee avant : {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
