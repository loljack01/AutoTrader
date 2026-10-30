"""Daily trend filter on the frozen sweep strategy, rule fixed before
running: buy only if the previous session's daily close is above its
20-day SMA; sell (the mirror strategy) only if it is below.

Baseline: random entries in the same direction (every session-allowed
bar, stop 1.5xATR, target 3xATR, same cost) split by the same trend
state. If the filter lifts random entries as much as it lifts the
strategy, it is only capturing market drift, not improving the strategy.
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


for direction in ("buy", "sell"):
    print(f"\n################ {'ACHATS (call)' if direction == 'buy' else 'VENTES (put)'} ################")
    for iv in ("15m", "5m", "1m", "1h"):
        d = bt.cache.closed_bars(bt.cache.load("FCE1!", iv), iv, now)
        up = trend_mask(d)
        with_trend = up if direction == "buy" else ~up
        switches = int((np.diff(up.astype(int)) != 0).sum())
        days = pd.Series(with_trend, index=d.index.tz_convert("Europe/Paris").date).groupby(level=0).first()
        print(f"\n=== {iv}: {d.index[0].date()} -> {d.index[-1].date()} | jours dans le sens du filtre: {days.sum()}/{len(days)} | changements de tendance: {switches}")

        allowed = np.array([session.entry_allowed(session.session_window(t)) for t in d.index.tz_convert("Europe/Paris")])
        for cost in (1.0, 3.0):
            bt.ROUND_TRIP_COST = cost
            exit_idx, net = outcomes(d, direction, cost)
            ok = allowed & (exit_idx >= 0)
            r_with = np.nanmean(net[ok & with_trend]) if (ok & with_trend).any() else np.nan
            r_against = np.nanmean(net[ok & ~with_trend]) if (ok & ~with_trend).any() else np.nan
            print(f"  cout {cost:.0f}pt | entrees au hasard: dans le sens du filtre {r_with:+.3f}R/trade, contre {r_against:+.3f}R/trade")
            for one in (True, False):
                t = bt.backtest(d, one, False, direction=direction)
                t = t[t.result != "open"].copy()
                t["ok"] = with_trend[d.index.get_indexer(t.entry_time)]
                tf = bt.backtest(d, one, False, entry_mask=with_trend, direction=direction)
                tf = tf[tf.result != "open"]
                a_w = t[t.ok].net_r.mean() if t.ok.any() else np.nan
                a_c = t[~t.ok].net_r.mean() if (~t.ok).any() else np.nan
                lab = "1/balayage" if one else "re-entrees"
                avg = tf.net_r.mean() if len(tf) else float("nan")
                print(f"    strategie {lab}: sans filtre n={len(t):3d} net={t.net_r.sum():+6.1f}R | AVEC filtre n={len(tf):3d} net={tf.net_r.sum():+6.1f}R moy={avg:+.2f}R"
                      f" | moy/trade dans le sens {a_w:+.2f} (n={int(t.ok.sum())}) vs contre {a_c:+.2f} (n={int((~t.ok).sum())})")
