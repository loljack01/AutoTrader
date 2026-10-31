"""TradingView indicator "simple scalping - papamallis" (EMA channel of
highs and lows with a slope filter) turned into a strategy, rules fixed on
2026-10-31 BEFORE running, at the user's request (16th idea tested; close
to the Supertrend family already rejected on 29/10). The indicator's
default settings are used as they are, no other value is tried:
lookback 22, EMA length 21, high/low lookback 1.

Indicator (as in the Pine code): emah = EMA21 of the highs, emal = EMA21
of the lows (pandas ewm span 21, not adjusted). Upper band rising if emah >
emah 22 bars earlier, lower band falling if emal < emal 22 bars earlier.
  buy signal   close crosses above emah (previous close <= previous emah)
               and the upper band is rising
  sell signal  close crosses below emal and the lower band is falling
The indicator gives no exit; the following exits are fixed now:
  entry   at the close of the signal bar (15m)
  stop    the opposite band at entry (long: emal, short: emah), checked
          intrabar from the next bar (a touch = exit at the stop)
  exit    first later close back through the opposite band (long: close
          < emal of that bar, short: close > emah), at that close
One position at a time per market; signals during a position are ignored,
except that a bar which exits a position may open the opposite one at the
same close if it is itself a signal. No session filter (the indicator has
none). Costs 1pt and 3pt CAC-equivalent x fixed factor k
(frozen_15m_calls_trend.MARKETS). 10 index futures, all 15m bars before
REFERENCE_END. Information only: the MACD-confirmed entry of the indicator
(MACD 12/26 crossing its 9-bar SMA signal while price is outside the
channel and both bands slope the same way), same exits.

Decision rule (fixed before running), 10 markets pooled, base version:
worth live tracking WITHOUT money only if ALL of:
  - at least 30 closed trades;
  - net > 0 at 3pt-equivalent cost;
  - net > 0 at 1pt with every gain capped at +5R;
  - both halves of the period (split at the middle date) > 0 at 1pt;
  - at least 6 of the 10 markets > 0 at 1pt.
Otherwise REJETE, no re-tuning (no other length, lookback, exit or
filter is tried).

Usage: python scripts/test_papamallis_channel.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache
from frozen_15m_calls_trend import MARKETS

REFERENCE_END = "2026-10-31"
LOOKBACK, EMA_LEN = 22, 21


def signals(d, macd_confirm=False):
    emah = d.High.ewm(span=EMA_LEN, adjust=False).mean()
    emal = d.Low.ewm(span=EMA_LEN, adjust=False).mean()
    h_up = emah > emah.shift(LOOKBACK)
    l_dn = emal < emal.shift(LOOKBACK)
    c = d.Close
    if macd_confirm:
        macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
        sig = macd.rolling(9).mean()
        up_x = (macd > sig) & (macd.shift(1) <= sig.shift(1))
        dn_x = (macd < sig) & (macd.shift(1) >= sig.shift(1))
        l_up = emal > emal.shift(LOOKBACK)
        h_dn = emah < emah.shift(LOOKBACK)
        buy = up_x & (c > emah) & h_up & l_up
        sell = dn_x & (c < emal) & l_dn & h_dn
    else:
        buy = (c > emah) & (c.shift(1) <= emah.shift(1)) & h_up
        sell = (c < emal) & (c.shift(1) >= emal.shift(1)) & l_dn
    warm = np.arange(len(d)) >= EMA_LEN + LOOKBACK
    return emah.to_numpy(), emal.to_numpy(), (buy & warm).to_numpy(), (sell & warm).to_numpy()


def backtest(d, k, cost, macd_confirm=False):
    emah, emal, buy, sell = signals(d, macd_confirm)
    hi, lo, cl = d.High.to_numpy(), d.Low.to_numpy(), d.Close.to_numpy()
    idx, c = d.index, cost * k
    trades, pos = [], None
    for i in range(len(d)):
        if pos is not None and i > pos["i"]:
            s = pos["side"]
            hit = lo[i] <= pos["stop"] if s == 1 else hi[i] >= pos["stop"]
            out = cl[i] < emal[i] if s == 1 else cl[i] > emah[i]
            if hit or out:
                px = pos["stop"] if hit else cl[i]
                trades.append({"side": "call" if s == 1 else "put", "entry_time": idx[pos["i"]],
                               "exit_time": idx[i], "result": "stop" if hit else "sortie",
                               "net_r": (s * (px - pos["entry"]) - c) / pos["risk"]})
                pos = None
        if pos is None and (buy[i] or sell[i]):
            s = 1 if buy[i] else -1
            stop = emal[i] if s == 1 else emah[i]
            risk = (cl[i] - stop) * s
            if risk > 0:
                pos = {"i": i, "side": s, "entry": cl[i], "stop": stop, "risk": risk}
    return pd.DataFrame(trades, columns=["side", "entry_time", "exit_time", "result", "net_r"])


def line(label, t):
    r = t.net_r.to_numpy()
    if not len(r):
        return f"  {label:28s} 0 trade"
    return (f"  {label:28s} {len(r):4d} trades, {(r > 0).mean():4.0%} gagnants, net {r.sum():+7.1f}R "
            f"({r.mean():+.3f}R/trade), plafond 5R {np.minimum(r, 5).sum():+7.1f}R | "
            f"calls {t[t.side == 'call'].net_r.sum():+.1f}R ({(t.side == 'call').sum()}), "
            f"puts {t[t.side == 'put'].net_r.sum():+.1f}R ({(t.side == 'put').sum()})")


def main():
    now = pd.Timestamp.now(tz="UTC")
    all1, all3, allm, per = [], [], [], {}
    start = end = None
    for s, (name, k) in MARKETS.items():
        d = cache.closed_bars(cache.load(s, "15m"), "15m", now)
        d = d[d.index < REFERENCE_END]
        start = d.index[0] if start is None else min(start, d.index[0])
        end = d.index[-1] if end is None else max(end, d.index[-1])
        t1, t3, tm = backtest(d, k, 1.0), backtest(d, k, 3.0), backtest(d, k, 1.0, True)
        all1.append(t1), all3.append(t3), allm.append(tm)
        per[name] = t1.net_r.sum()
        print(f"{name} ({d.index[0]:%d/%m} -> {d.index[-1]:%d/%m}) :")
        print(line("canal, 1pt", t1))
        print(line("canal, 3pt", t3))
        print(line("confirmation MACD (info), 1pt", tm))
    T1, T3, TM = pd.concat(all1), pd.concat(all3), pd.concat(allm)
    print("\n10 marches ensemble :")
    print(line("canal, 1pt", T1))
    print(line("canal, 3pt", T3))
    print(line("confirmation MACD (info), 1pt", TM))
    mid = start + (end - start) / 2
    h1, h2 = T1[T1.entry_time < mid].net_r.sum(), T1[T1.entry_time >= mid].net_r.sum()
    pos = sum(v > 0 for v in per.values())
    cap = np.minimum(T1.net_r.to_numpy(), 5).sum()
    print(f"  moities (coupure {mid:%d/%m}) {h1:+.1f}R / {h2:+.1f}R | marches positifs {pos}/10 | "
          f"sorties : stop {(T1.result == 'stop').sum()}, retour dans le canal {(T1.result == 'sortie').sum()}")
    ok = len(T1) >= 30 and T3.net_r.sum() > 0 and cap > 0 and h1 > 0 and h2 > 0 and pos >= 6
    print(f"\nRegle fixee avant : indicateur papamallis {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
