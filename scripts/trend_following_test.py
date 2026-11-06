"""Daily trend following on the 10 index markets, 2012-2026, rules fixed on
2026-10-29 BEFORE running. Standard rules from the literature (time-series
momentum, Moskowitz, Ooi & Pedersen 2012; 200-day average), NOT tuned on
our data: no other lookback, average or volatility target is tried.

Data: cash index daily closes (TradingView, price indices, no rolls):
EURONEXT:PX1, XETR:DAX, TVC:SX5E, SP:SPX, NASDAQ:NDX, TVC:UKX, SIX:SMI,
TVC:DJI, TVC:RUT, TVC:FTMIB, from 2011 (one year of warm-up), evaluated
from January 2012 to the last closed month. Dividends and interest rates
are left out for every rule alike (price returns), so the comparison with
buy and hold is fair; a turbo really earns the dividends and pays the
rate, which this simplification ignores.

Sizing, all rules: each market gets an exposure of min(10% / its 60-day
annualised volatility, 2) (equal risk per market), set at the close of
the last trading day of each month and held for the next month; the
portfolio is the equal-weight average of the 10 markets.
  TSMOM 12m (decision)  long if the 12-month (252-day) return at the
                        month-end close is > 0, short otherwise
  SMA 200 (information) long if the month-end close is above its 200-day
                        average, flat otherwise
  Buy and hold (benchmark) always long, same sizing
Costs: 2pt CAC-equivalent per unit of exposure traded at each monthly
rebalance (fixed per-market factors from frozen_15m_calls_trend.py over
the index level); turbo financing margin 2.5% a year on the gross
exposure, every rule alike (the issuer's margin over the futures carry,
long or short). Gross figures shown too.

Decision rule (fixed before running), TSMOM 12m net of costs and
financing, monthly returns of the equal-weight portfolio: worth live
tracking without money (monthly review) only if annualised net return > 0,
Sharpe >= 0.3, both halves of the period > 0, at least 6 of the 10 markets
> 0 on their own, AND its Sharpe beats buy and hold's. Otherwise rejected,
no re-tuning.

Usage: python scripts/trend_following_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache
from frozen_15m_calls_trend import MARKETS

CASH = {"EURONEXT:PX1": "FCE1!", "XETR:DAX": "FDAX1!", "TVC:SX5E": "FESX1!", "SP:SPX": "ES1!", "NASDAQ:NDX": "NQ1!",
        "TVC:UKX": "ICEEUR:Z1!", "SIX:SMI": "FSMI1!", "TVC:DJI": "YM1!", "TVC:RUT": "RTY1!", "TVC:FTMIB": "FIB1!"}
START = "2012-01-01"
VOL_TARGET, MAX_EXPO = 0.10, 2.0
COST_PTS, FINANCING = 2.0, 0.025


def monthly(symbol, rule, now, net=True):
    """Monthly returns of one market under `rule`."""
    d = cache.closed_bars(cache.load(symbol, "1D"), "1D", now)
    c = d.Close
    c.index = c.index.tz_convert("UTC").normalize()
    r = c.pct_change()
    vol = r.rolling(60).std() * np.sqrt(252)
    month = c.index.to_period("M")
    ends = c.groupby(month).apply(lambda s: s.index[-1])
    k = MARKETS[CASH[symbol]][1]
    out, prev_e = {}, 0.0
    for m, end in ends.items():
        i = c.index.get_loc(end)
        if i < 252 or np.isnan(vol.iloc[i]):
            continue
        size = min(VOL_TARGET / vol.iloc[i], MAX_EXPO)
        if rule == "tsmom":
            e = size * (1 if c.iloc[i] / c.iloc[i - 252] - 1 > 0 else -1)
        elif rule == "sma200":
            e = size * (1 if c.iloc[i] > c.iloc[i - 199:i + 1].mean() else 0)
        else:
            e = size
        nxt = month[i + 1:] == m + 1 if i + 1 < len(c) else []
        days = r.iloc[i + 1:][nxt] if len(nxt) else r.iloc[0:0]
        if not len(days):
            continue
        g = np.prod(1 + e * days.to_numpy()) - 1
        if net:
            g -= abs(e - prev_e) * COST_PTS * k / c.iloc[i] + abs(e) * FINANCING * len(days) / 252
        out[m + 1] = g
        prev_e = e
    return pd.Series(out)


def stats(m):
    m = m[m.index >= pd.Period(START, "M")]
    ann = (1 + m).prod() ** (12 / len(m)) - 1
    sharpe = m.mean() / m.std() * np.sqrt(12)
    eq = (1 + m).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    return ann, sharpe, dd, m


def main():
    now = pd.Timestamp.now(tz="UTC")
    rows = {}
    for rule in ("tsmom", "sma200", "buyhold"):
        for net in (True, False):
            per = {s: monthly(s, rule, now, net) for s in CASH}
            rows[(rule, net)] = per
    print("Par marche (rendement annualise net, depuis 2012) :")
    pos = 0
    for s in CASH:
        a = {rule: stats(rows[(rule, True)][s])[0] for rule in ("tsmom", "sma200", "buyhold")}
        pos += a["tsmom"] > 0
        print(f"  {s:14s} TSMOM {a['tsmom']:+6.1%} | SMA200 {a['sma200']:+6.1%} | achat-conservation {a['buyhold']:+6.1%}")
    print("\nPortefeuille egal des 10 marches :")
    res = {}
    for rule, label in (("tsmom", "TSMOM 12m (decision)"), ("sma200", "SMA 200 (info)"), ("buyhold", "Achat-conservation")):
        for net in (True, False):
            port = pd.concat(rows[(rule, net)], axis=1).mean(axis=1).sort_index()
            ann, sh, dd, m = stats(port)
            res[(rule, net)] = (ann, sh, dd, m)
            print(f"  {label:22s} {'net ' if net else 'brut'}: {ann:+6.1%}/an, Sharpe {sh:+.2f}, baisse max {dd:6.1%}")
    ann, sh, dd, m = res[("tsmom", True)]
    half = len(m) // 2
    h1, h2 = (1 + m.iloc[:half]).prod() - 1, (1 + m.iloc[half:]).prod() - 1
    bh = res[("buyhold", True)]
    print(f"\nTSMOM net : moities {m.index[0]}-{m.index[half - 1]} {h1:+.1%} / {m.index[half]}-{m.index[-1]} {h2:+.1%} | "
          f"marches positifs {pos}/10 | Sharpe achat-conservation {bh[1]:+.2f}")
    for label, months in (("aout 2015", ["2015-08"]), ("T4 2018", ["2018-10", "2018-11", "2018-12"]),
                          ("fev-mars 2020", ["2020-02", "2020-03"]), ("2022", [f"2022-{x:02d}" for x in range(1, 13)])):
        p = [pd.Period(x, "M") for x in months]
        t = (1 + m.reindex(p).fillna(0)).prod() - 1
        b = (1 + bh[3].reindex(p).fillna(0)).prod() - 1
        print(f"  crise {label:13s}: TSMOM {t:+6.1%} | achat-conservation {b:+6.1%}")
    ok = ann > 0 and sh >= 0.3 and h1 > 0 and h2 > 0 and pos >= 6 and sh > bh[1]
    print(f"\nRegle fixee avant: TSMOM 12m {'A SUIVRE EN REEL (sans argent, revue mensuelle)' if ok else 'REJETEE'}")


if __name__ == "__main__":
    main()
