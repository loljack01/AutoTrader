"""Diversified daily trend following (time-series momentum) across four
asset classes, 2012-2026, rules fixed on 2026-10-29 BEFORE running. Same
standard rule as scripts/trend_following_test.py (rejected on equity
indices alone the same day), now with the diversification the literature
says it needs (Moskowitz, Ooi & Pedersen 2012). Nothing is tuned: no other
lookback, volatility target, instrument list or weighting is tried.

Instruments (TradingView daily closes, from 2011 for one year of warm-up,
evaluated from January 2012 to the last closed month):
  actions    the 10 cash indices of trend_following_test.py
  taux       10-year government bonds, from the yields TVC:US10Y,
             TVC:DE10Y, TVC:GB10Y: daily bond return = -8.5 x change in
             yield (constant modified duration 8.5)
  matieres   OANDA:XAUUSD, OANDA:XAGUSD, TVC:UKOIL, COMEX:HG1!
  devises    FX:EURUSD, FX:USDJPY, FX:GBPUSD, FX:AUDUSD
Price returns only for every instrument: dividends, coupons, rate
differentials, roll yield and the financing rate are left out, as in the
equity test (a known limitation, the same for every rule).

Rule TSMOM 12m: at the close of each month's last trading day, long if
the instrument's 12-month (252-day) return is > 0, short otherwise, held
for the next month; exposure min(10% / its 60-day annualised volatility,
2). Equal risk per asset class: each class is the equal-weight average of
its instruments, the portfolio the equal-weight average of the 4 classes.
Costs per unit of exposure traded at each rebalance: equities 2pt
CAC-equivalent (as before), bonds 0.03%, gold 0.04%, silver / oil /
copper 0.08%, currencies 0.02%; turbo financing margin 2.5% a year on the
gross exposure. Benchmark: buy and hold of the 10 equity indices, same
sizing, costs and financing.

Decision rule (fixed before running), STRICTER than the equity test since
this is the 7th idea tested today, TSMOM 12m portfolio net of costs and
financing: worth live tracking without money (monthly review) only if
annualised net return > 0, Sharpe >= 0.4, both halves of the period > 0,
at least 3 of the 4 asset classes > 0 on their own, AND its Sharpe beats
the equity buy and hold's. Otherwise rejected, no re-tuning.

Usage: python scripts/diversified_trend_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache
from frozen_15m_calls_trend import MARKETS
from trend_following_test import CASH

START = "2012-01-01"
VOL_TARGET, MAX_EXPO, FINANCING, DURATION = 0.10, 2.0, 0.025, 8.5
CLASSES = {
    "actions": {s: ("price", None) for s in CASH},
    "taux": {s: ("yield", 0.0003) for s in ("TVC:US10Y", "TVC:DE10Y", "TVC:GB10Y")},
    "matieres": {"OANDA:XAUUSD": ("price", 0.0004), "OANDA:XAGUSD": ("price", 0.0008),
                 "TVC:UKOIL": ("price", 0.0008), "COMEX:HG1!": ("price", 0.0008)},
    "devises": {s: ("price", 0.0002) for s in ("FX:EURUSD", "FX:USDJPY", "FX:GBPUSD", "FX:AUDUSD")},
}


def returns(symbol, kind, now):
    d = cache.closed_bars(cache.load(symbol, "1D"), "1D", now)
    c = d.Close.copy()
    c.index = c.index.tz_convert("UTC").normalize()
    c = c[~c.index.duplicated(keep="last")]
    r = -DURATION * c.diff() / 100 if kind == "yield" else c.pct_change()
    return c, r


def monthly(symbol, kind, cost, rule, now):
    c, r = returns(symbol, kind, now)
    vol = r.rolling(60).std() * np.sqrt(252)
    month = c.index.tz_localize(None).to_period("M")
    out, prev_e = {}, 0.0
    ends = [i for i in range(len(c) - 1) if month[i + 1] != month[i]]
    for i in ends:
        if i < 252 or np.isnan(vol.iloc[i]) or vol.iloc[i] <= 0:
            continue
        size = min(VOL_TARGET / vol.iloc[i], MAX_EXPO)
        if rule == "tsmom":
            past = np.prod(1 + r.iloc[i - 251:i + 1].to_numpy()) - 1
            e = size * (1 if past > 0 else -1)
        else:
            e = size
        m = month[i + 1]
        days = r.iloc[i + 1:][month[i + 1:] == m].to_numpy()
        unit = cost if cost is not None else 2.0 * MARKETS[CASH[symbol]][1] / c.iloc[i]
        g = np.prod(1 + e * days) - 1 - abs(e - prev_e) * unit - abs(e) * FINANCING * len(days) / 252
        out[m] = g
        prev_e = e
    return pd.Series(out)


def stats(m):
    m = m[m.index >= pd.Period(START, "M")].dropna()
    ann = (1 + m).prod() ** (12 / len(m)) - 1
    eq = (1 + m).cumprod()
    return ann, m.mean() / m.std() * np.sqrt(12), (eq / eq.cummax() - 1).min(), m


def main():
    now = pd.Timestamp.now(tz="UTC")
    classes = {}
    print("Par instrument, TSMOM 12m net (rendement annualise) :")
    for cl, inst in CLASSES.items():
        per = {}
        for s, (kind, cost) in inst.items():
            per[s] = monthly(s, kind, cost, "tsmom", now)
            print(f"  {cl:9s} {s:14s} {stats(per[s])[0]:+6.1%}")
        classes[cl] = pd.concat(per, axis=1).mean(axis=1).sort_index()
    print("\nPar classe (TSMOM 12m net) :")
    pos = 0
    for cl, m in classes.items():
        ann, sh, dd, _ = stats(m)
        pos += ann > 0
        print(f"  {cl:9s} {ann:+6.1%}/an, Sharpe {sh:+.2f}, baisse max {dd:6.1%}")
    port = pd.concat(classes, axis=1).mean(axis=1).sort_index()
    ann, sh, dd, m = stats(port)
    no_eq = stats(pd.concat({k: v for k, v in classes.items() if k != "actions"}, axis=1).mean(axis=1).sort_index())
    bh = stats(pd.concat({s: monthly(s, "price", None, "buyhold", now) for s in CASH}, axis=1).mean(axis=1).sort_index())
    half = len(m) // 2
    h1, h2 = (1 + m.iloc[:half]).prod() - 1, (1 + m.iloc[half:]).prod() - 1
    print(f"\nPortefeuille TSMOM 12m diversifie (net) : {ann:+.1%}/an, Sharpe {sh:+.2f}, baisse max {dd:.1%}")
    print(f"  moities {m.index[0]}-{m.index[half - 1]} {h1:+.1%} / {m.index[half]}-{m.index[-1]} {h2:+.1%} | "
          f"classes positives {pos}/4")
    print(f"  (info) sans les actions : {no_eq[0]:+.1%}/an, Sharpe {no_eq[1]:+.2f}, baisse max {no_eq[2]:.1%}")
    print(f"  achat-conservation des 10 indices (net) : {bh[0]:+.1%}/an, Sharpe {bh[1]:+.2f}, baisse max {bh[2]:.1%}")
    for label, months in (("T4 2018", ["2018-10", "2018-11", "2018-12"]), ("fev-mars 2020", ["2020-02", "2020-03"]),
                          ("2022", [f"2022-{x:02d}" for x in range(1, 13)])):
        p = [pd.Period(x, "M") for x in months]
        t = (1 + m.reindex(p).fillna(0)).prod() - 1
        b = (1 + bh[3].reindex(p).fillna(0)).prod() - 1
        print(f"  crise {label:13s}: TSMOM diversifie {t:+6.1%} | achat-conservation actions {b:+6.1%}")
    ok = ann > 0 and sh >= 0.4 and h1 > 0 and h2 > 0 and pos >= 3 and sh > bh[1]
    print(f"\nRegle fixee avant: TSMOM 12m diversifie {'A SUIVRE EN REEL (sans argent, revue mensuelle)' if ok else 'REJETEE'}")


if __name__ == "__main__":
    main()
