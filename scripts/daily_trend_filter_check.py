"""Daily trend filter on the frozen buy strategy, rule fixed before running:
buy only if the previous session's daily close is above its 20-day SMA.

Baseline: random long entries (every session-allowed bar, stop 1.5xATR,
target 3xATR, same cost) split by the same trend state. If the filter
lifts random buys as much as it lifts the strategy, it is only capturing
market drift, not making the strategy better.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from indicator_combo_search import outcomes
from setups import session

now = pd.Timestamp.now(tz="UTC")
daily = bt.cache.load("FCE1!", "1D")
daily.index = pd.to_datetime(daily.index, utc=True)
sma = daily.Close.rolling(20).mean()
up_by_day = pd.Series((daily.Close > sma).to_numpy(), index=daily.index.tz_convert("Europe/Paris").date)
day_keys = np.array(list(up_by_day.index))


def trend_mask(d):
    """Uses only sessions strictly before each bar's Paris date."""
    dates = d.index.tz_convert("Europe/Paris").date
    pos = np.searchsorted(day_keys, dates, side="left") - 1
    vals = up_by_day.to_numpy()
    return np.where(pos >= 0, vals[np.clip(pos, 0, None)], False).astype(bool)


for iv in ("15m", "5m", "1m", "1h"):
    d = bt.cache.closed_bars(bt.cache.load("FCE1!", iv), iv, now)
    up = trend_mask(d)
    switches = int((np.diff(up.astype(int)) != 0).sum())
    days = pd.Series(up, index=d.index.tz_convert("Europe/Paris").date).groupby(level=0).first()
    print(f"\n=== {iv}: {d.index[0].date()} -> {d.index[-1].date()} | jours en tendance haussiere: {days.sum()}/{len(days)} | changements de tendance: {switches}")

    allowed = np.array([session.entry_allowed(session.session_window(t)) for t in d.index.tz_convert("Europe/Paris")])
    for cost in (1.0, 3.0):
        bt.ROUND_TRIP_COST = cost
        exit_idx, net = outcomes(d, "buy", cost)
        ok = allowed & (exit_idx >= 0)
        r_up, r_dn = np.nanmean(net[ok & up]), np.nanmean(net[ok & ~up])
        print(f"  cout {cost:.0f}pt | achats au hasard: tendance haussiere {r_up:+.3f}R/trade, baissiere {r_dn:+.3f}R/trade, ecart {r_up - r_dn:+.3f}")
        for one in (True, False):
            t = bt.backtest(d, one, False)
            t = t[t.result != "open"].copy()
            t["up"] = up[d.index.get_indexer(t.entry_time)]
            tf = bt.backtest(d, one, False, entry_mask=up)
            tf = tf[tf.result != "open"]
            a_up = t[t.up].net_r.mean() if t.up.any() else np.nan
            a_dn = t[~t.up].net_r.mean() if (~t.up).any() else np.nan
            lab = "1/balayage" if one else "re-entrees"
            print(f"    strategie {lab}: sans filtre n={len(t):3d} net={t.net_r.sum():+6.1f}R | AVEC filtre n={len(tf):3d} net={tf.net_r.sum():+6.1f}R moy={tf.net_r.mean() if len(tf) else float('nan'):+.2f}R"
                  f" | moy/trade haussier {a_up:+.2f} (n={int(t.up.sum())}) vs baissier {a_dn:+.2f} (n={int((~t.up).sum())})")
