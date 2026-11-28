"""Exhaustive search over every combination of 9 entry conditions, with a
selection/check split so the search's own luck can be measured.

Conditions (buy side; sell is the exact mirror), all known at bar close:
    choch        last CHoCH within 4h is bullish
    bos_confirm  a later, distinct bullish BOS confirmed that CHoCH
    sweep        an EQL pool was swept within the last 4h
    discount     close below the range equilibrium (execution swings)
    vwap_reclaim close back above session VWAP after being below in the last 1h
    volume       bullish bar with volume >= 1.5x its 20-bar average
    fvg          close inside a bullish FVG created < 4h ago, not inverted
    ob           close inside a bullish order block confirmed < 4h ago, not broken
    ema_trend    close above EMA(50)

Trigger: the AND of the chosen conditions turns true (false on the
previous bar). Entry at that close, Paris session filter, one trade at a
time. Identical exits for every combination so they compare fairly:
stop 1.5x ATR(14), target 3x ATR (2R), round-trip cost in points.

Protocol, fixed before running: combinations are ranked on the first 2/3
of each history (selection) and only then evaluated on the last 1/3
(check). With hundreds of candidates, some look good on selection by
chance alone; the check period, the rank correlation between the two
periods, and a random-entry baseline show whether the ranking carries
any information beyond luck.

Usage: python scripts/indicator_combo_search.py [--cost 1.0] [--min-trades 20]
"""

import argparse
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from finta import TA

from data import cache
from levels import fvg, liquidity, order_blocks, structure, vwap
from setups import session

SYMBOL = "FCE1!"
INTERVALS = ("5m", "15m", "1h")
SWING_N = 2
WINDOW = pd.Timedelta(hours=4)
STOP_ATR = 1.5
TARGET_ATR = 3.0
NAMES = ("choch", "bos_confirm", "sweep", "discount", "vwap_reclaim", "volume", "fvg", "ob", "ema_trend")


def _recent(index, event, window=WINDOW):
    """At each bar: time of the latest True in `event` (NaT if none), and
    whether it falls within `window` of that bar."""
    t = pd.Series(index.where(event.to_numpy()), index=index).ffill()
    return t, (index.to_series() - t) <= window


def _zone_mask(d, zones, kind):
    """True where close sits inside a zone of `kind` that is still live:
    from its start for at most WINDOW, until a close breaks through it."""
    close = d.Close.to_numpy()
    idx = d.index
    out = np.zeros(len(d), dtype=bool)
    for z in zones:
        if z["type"] != kind:
            continue
        start = idx.searchsorted(z["start"])
        end = idx.searchsorted(z["start"] + WINDOW, side="right")
        for j in range(start, min(end, len(d))):
            broken = close[j] < z["bottom"] if kind == "bullish" else close[j] > z["top"]
            if broken:
                break
            if z["bottom"] <= close[j] <= z["top"]:
                out[j] = True
    return out


def conditions(d):
    """Returns {'buy': {name: bool array}, 'sell': {...}}."""
    idx = d.index
    atr = TA.ATR(d, 14)
    is_hi, is_lo = structure.find_swings(d, n=SWING_N)
    sh = structure.confirmed_level(is_hi, d.High, SWING_N)
    sl = structure.confirmed_level(is_lo, d.Low, SWING_N)
    bull_bos, bear_bos = structure.bos_events(d.Close, sh, sl)
    choch = structure.choch_events(bull_bos, bear_bos)
    bull_choch, bear_choch = choch & bull_bos, choch & bear_bos

    t_bull_choch, bull_choch_recent = _recent(idx, bull_choch)
    t_bear_choch, bear_choch_recent = _recent(idx, bear_choch)
    last_is_bull = t_bull_choch.fillna(pd.Timestamp.min.tz_localize("UTC")) > t_bear_choch.fillna(pd.Timestamp.min.tz_localize("UTC"))
    last_is_bear = t_bear_choch.fillna(pd.Timestamp.min.tz_localize("UTC")) > t_bull_choch.fillna(pd.Timestamp.min.tz_localize("UTC"))
    choch_buy = (bull_choch_recent & last_is_bull).to_numpy()
    choch_sell = (bear_choch_recent & last_is_bear).to_numpy()

    t_bull_bos, _ = _recent(idx, bull_bos & ~choch)
    t_bear_bos, _ = _recent(idx, bear_bos & ~choch)
    bos_buy = choch_buy & (t_bull_bos > t_bull_choch).to_numpy()
    bos_sell = choch_sell & (t_bear_bos > t_bear_choch).to_numpy()

    hi_marks = structure.confirmed_marks(is_hi, d.High, SWING_N)
    lo_marks = structure.confirmed_marks(is_lo, d.Low, SWING_N)
    eqh = liquidity.find_sweeps(liquidity.find_pools(hi_marks, atr), d, "high")
    eql = liquidity.find_sweeps(liquidity.find_pools(lo_marks, atr), d, "low")
    swept_low = pd.Series(False, index=idx)
    swept_high = pd.Series(False, index=idx)
    swept_low.loc[[p["swept_at"] for p in eql if p["swept_at"] is not None]] = True
    swept_high.loc[[p["swept_at"] for p in eqh if p["swept_at"] is not None]] = True
    sweep_buy = _recent(idx, swept_low)[1].to_numpy()
    sweep_sell = _recent(idx, swept_high)[1].to_numpy()

    eq = ((sh + sl) / 2).to_numpy()
    close = d.Close.to_numpy()
    with np.errstate(invalid="ignore"):
        discount = close < eq
        premium = close > eq

    vw = vwap.session_vwap(d)
    bars_per_hour = max(1, int(pd.Timedelta(hours=1) / (idx[1:] - idx[:-1]).min()))
    vwap_buy = _reclaim(d.Close, vw, "buy", bars_per_hour)
    vwap_sell = _reclaim(d.Close, vw, "sell", bars_per_hour)

    vol_spike = (d.Volume >= 1.5 * d.Volume.shift(1).rolling(20, min_periods=1).mean()).to_numpy()
    volume_buy = vol_spike & (d.Close > d.Open).to_numpy()
    volume_sell = vol_spike & (d.Close < d.Open).to_numpy()

    gaps = fvg.find_fvgs(d)
    fvg_zones = [{"type": g["type"], "top": g["top"], "bottom": g["bottom"], "start": g["created_at"]} for g in gaps]
    obs = order_blocks.find_order_blocks(d, bull_bos, bear_bos)
    ob_zones = [{"type": o["type"], "top": o["top"], "bottom": o["bottom"], "start": o["confirmed_at"]} for o in obs]

    ema = d.Close.ewm(span=50, adjust=False).mean().to_numpy()

    return {
        "buy": {
            "choch": choch_buy, "bos_confirm": bos_buy, "sweep": sweep_buy, "discount": discount,
            "vwap_reclaim": vwap_buy, "volume": volume_buy, "fvg": _zone_mask(d, fvg_zones, "bullish"),
            "ob": _zone_mask(d, ob_zones, "bullish"), "ema_trend": close > ema,
        },
        "sell": {
            "choch": choch_sell, "bos_confirm": bos_sell, "sweep": sweep_sell, "discount": premium,
            "vwap_reclaim": vwap_sell, "volume": volume_sell, "fvg": _zone_mask(d, fvg_zones, "bearish"),
            "ob": _zone_mask(d, ob_zones, "bearish"), "ema_trend": close < ema,
        },
    }


def _reclaim(close, level, direction, lookback):
    above = (close > level).to_numpy()
    on_side = above if direction == "buy" else ~above
    other = pd.Series(~on_side).shift(1, fill_value=False).rolling(lookback, min_periods=1).max().astype(bool).to_numpy()
    return on_side & other


def outcomes(d, direction, cost):
    """For an entry at each bar's close: (exit bar index, net R), or
    (-1, nan) if neither stop nor target is reached in the data."""
    atr = TA.ATR(d, 14).to_numpy()
    close, high, low = d.Close.to_numpy(), d.High.to_numpy(), d.Low.to_numpy()
    n = len(d)
    exit_idx = np.full(n, -1)
    net = np.full(n, np.nan)
    for i in range(n):
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        risk = STOP_ATR * a
        if direction == "buy":
            stop, take = close[i] - risk, close[i] + TARGET_ATR * a
        else:
            stop, take = close[i] + risk, close[i] - TARGET_ATR * a
        for j in range(i + 1, n):
            hit_stop = low[j] <= stop if direction == "buy" else high[j] >= stop
            hit_take = high[j] >= take if direction == "buy" else low[j] <= take
            if hit_stop or hit_take:
                exit_idx[i] = j
                gross = -1.0 if hit_stop else TARGET_ATR / STOP_ATR
                net[i] = gross - cost / risk
                break
    return exit_idx, net


def simulate(signal, allowed, exit_idx, net, split):
    """One trade at a time. Returns per-period lists of net R."""
    sel, chk = [], []
    busy_until = -1
    for i in np.flatnonzero(signal & allowed):
        if i <= busy_until or exit_idx[i] < 0:
            continue
        (sel if i < split else chk).append(net[i])
        busy_until = exit_idx[i]
    return sel, chk


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cost", type=float, default=1.0)
    parser.add_argument("--min-trades", type=int, default=20)
    args = parser.parse_args()

    rows = []
    baselines = []
    now = pd.Timestamp.now(tz="UTC")
    for interval in INTERVALS:
        d = cache.closed_bars(cache.load(SYMBOL, interval), interval, now)
        split = int(len(d) * 2 / 3)
        allowed = np.array([session.entry_allowed(session.session_window(t)) for t in d.index.tz_convert("Europe/Paris")])
        conds = conditions(d)
        for direction in ("buy", "sell"):
            exit_idx, net = outcomes(d, direction, args.cost)
            ok = allowed & (exit_idx >= 0)
            baselines.append({
                "interval": interval, "direction": direction,
                "sel_avg": np.nanmean(net[:split][ok[:split]]), "chk_avg": np.nanmean(net[split:][ok[split:]]),
            })
            for k in range(1, len(NAMES) + 1):
                for combo in itertools.combinations(NAMES, k):
                    state = np.logical_and.reduce([conds[direction][c] for c in combo])
                    signal = state & ~np.concatenate(([False], state[:-1]))
                    sel, chk = simulate(signal, allowed, exit_idx, net, split)
                    rows.append({
                        "interval": interval, "direction": direction, "k": k, "combo": "+".join(combo),
                        "sel_n": len(sel), "sel_net": float(np.sum(sel)), "sel_avg": float(np.mean(sel)) if sel else np.nan,
                        "chk_n": len(chk), "chk_net": float(np.sum(chk)), "chk_avg": float(np.mean(chk)) if chk else np.nan,
                    })
        print(f"{interval}: {d.index[0]} -> {d.index[-1]}, selection jusqu'a {d.index[split - 1]}", file=sys.stderr)

    res = pd.DataFrame(rows)
    base = pd.DataFrame(baselines)
    return res, base, args


if __name__ == "__main__":
    res, base, args = main()
    pd.set_option("display.width", 200)
    print(f"cout={args.cost}pt, min {args.min_trades} trades en selection")
    print("\nEntrees au hasard (moyenne net R par trade):")
    print(base.round(3).to_string(index=False))

    ranked = res[res.sel_n >= args.min_trades]
    print(f"\n{len(res)} combinaisons x sens testees, {len(ranked)} avec >= {args.min_trades} trades en selection")
    print(f"positives en selection: {(ranked.sel_net > 0).sum()} ({(ranked.sel_net > 0).mean():.0%})")
    both = ranked[ranked.chk_n >= 10]
    rho = both.sel_avg.rank().corr(both.chk_avg.rank())
    print(f"correlation des rangs selection -> verification (n={len(both)}): {rho:+.2f}")

    print("\nMeilleure combinaison par nombre d'indicateurs (classee sur la selection):")
    best_k = ranked.sort_values("sel_net", ascending=False).groupby("k").head(1).sort_values("k")
    print(best_k[["k", "interval", "direction", "combo", "sel_n", "sel_net", "chk_n", "chk_net", "chk_avg"]].round(2).to_string(index=False))

    print("\nTop 10 global en selection, puis leur verification:")
    top = ranked.sort_values("sel_net", ascending=False).head(10)
    print(top[["interval", "direction", "combo", "sel_n", "sel_net", "sel_avg", "chk_n", "chk_net", "chk_avg"]].round(2).to_string(index=False))
    print(f"\nTop 10 positifs en verification: {(top.chk_net > 0).sum()}/10, net verification cumule {top.chk_net.sum():+.1f}R")
    res.to_csv(Path(__file__).resolve().parent.parent / "data" / "backtests" / f"combo_search_cost{args.cost:g}.csv", index=False)
