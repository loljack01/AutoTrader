"""Audit of the three frozen sweep strategies (puts 5m; 15m calls+puts with
daily SMA20 or EMA20 filter; all with a 2x ATR stop floor, one trade per
sweep). Data before the 2026-10-12 freeze only: this is a diagnosis of
what is already known, not a validation.

Part 1 - statistics: win rate, average win/loss, expectancy, t-stat and a
bootstrap 95% interval, results by side, month and entry hour, holding
time, overnight holds, and max favourable/adverse excursion (MFE/MAE).

Part 2 - small adjustments, list and decision rule fixed before running.
An adjustment is kept as a NEW candidate (the frozen versions are never
changed) only if it improves the net R of all 3 versions at both 1pt
and 3pt cost AND improves both halves of the period of every version at
1pt. Adjustments:
    gap_fill        realistic fills when a bar opens beyond stop/target
    breakeven_1R    stop moved to entry once +1R is reached
    session_exit    no overnight holding: close at the last bar of the day
    cash_hours      entries only 9:15-17:30 Paris
    min_rr_2        minimum net R:R 2.0 instead of 1.3
    consumed_pools  a pool closed through before being swept is consumed

Usage: python scripts/audit_frozen.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_daily import trend_up

FREEZE = "2026-10-12"
ADJUSTMENTS = {
    "gap_fill": {"gap_fill": True},
    "breakeven_1R": {"breakeven_r": 1.0},
    "session_exit": {"session_exit": True},
    "cash_hours": {"entry_hours": (9.25, 17.5)},
    "min_rr_2": {"min_rr": 2.0},
    "consumed_pools": {"consumed_pools": True},
}


def set_rules(cost, min_rr=1.3):
    bt.ROUND_TRIP_COST = cost
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0
    bt.SWING_N = 2
    bt.MIN_NET_RR = min_rr
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)


def run_version(name, data, cost, **opts):
    set_rules(cost, opts.pop("min_rr", 1.3))
    if name == "puts_5m":
        t = bt.backtest(data["5m"], True, False, direction="sell", **opts)
        t["side"] = "put"
    else:
        d = data["15m"]
        up = trend_up(d, "sma20" if name == "15m_sma20" else "ema20")
        parts = []
        for direction, mask in (("buy", up), ("sell", ~up)):
            x = bt.backtest(d, True, False, entry_mask=mask, direction=direction, **opts)
            x["side"] = "call" if direction == "buy" else "put"
            parts.append(x)
        t = pd.concat(parts, ignore_index=True)
    t = t[(t.result != "open") & (t.entry_time < FREEZE)]
    return t.sort_values("entry_time").reset_index(drop=True)


def excursions(t, d):
    pos = {ts: i for i, ts in enumerate(d.index)}
    mfe, mae = [], []
    for _, r in t.iterrows():
        a, b = pos[r.entry_time] + 1, pos[r.exit_time]
        seg = d.iloc[a:b + 1]
        risk = abs(r.entry - r.stop)
        if r.side == "call":
            mfe.append((seg.High.max() - r.entry) / risk); mae.append((r.entry - seg.Low.min()) / risk)
        else:
            mfe.append((r.entry - seg.Low.min()) / risk); mae.append((seg.High.max() - r.entry) / risk)
    return np.array(mfe), np.array(mae)


def stats(name, t, d, rng):
    r = t.net_r.to_numpy()
    w, l = t[t.result == "take"], t[t.result != "take"]
    boot = rng.choice(r, size=(5000, len(r)), replace=True).mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    tstat = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
    print(f"\n######## {name}: {len(t)} trades {t.entry_time.min():%d/%m} -> {t.entry_time.max():%d/%m}")
    print(f"  gagnants {len(w)} ({len(w)/len(t):.0%}), gain moyen {w.net_r.mean():+.2f}R, perte moyenne {l.net_r.mean():+.2f}R, "
          f"esperance {r.mean():+.2f}R/trade, t={tstat:+.2f}, IC95% bootstrap [{lo:+.2f} ; {hi:+.2f}]R/trade")
    for side, g in t.groupby("side"):
        print(f"  {side:4s}: n={len(g)} WR={(g.result=='take').mean():.0%} net={g.net_r.sum():+.1f}R")
    month = t.groupby(t.entry_time.dt.tz_convert("Europe/Paris").dt.strftime("%Y-%m")).net_r.agg(["size", "sum"])
    print("  par mois: " + ", ".join(f"{m} {int(row['size'])}tr {row['sum']:+.1f}R" for m, row in month.iterrows()))
    hours = t.entry_time.dt.tz_convert("Europe/Paris").dt.hour
    bucket = pd.cut(hours, [0, 11, 14, 17.5, 24], labels=["<11h", "11-14h", "14-17h30", ">17h30"], right=False)
    hb = t.groupby(bucket, observed=False).net_r.agg(["size", "sum"])
    print("  par heure d'entree: " + ", ".join(f"{k} {int(v['size'])}tr {v['sum']:+.1f}R" for k, v in hb.iterrows()))
    hold = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    overnight = t.entry_time.dt.tz_convert("Europe/Paris").dt.date != t.exit_time.dt.tz_convert("Europe/Paris").dt.date
    print(f"  duree mediane {hold.median():.1f}h, gardes la nuit {overnight.mean():.0%} (net {t[overnight].net_r.sum():+.1f}R vs journee {t[~overnight].net_r.sum():+.1f}R)")
    mfe, mae = excursions(t, d)
    is_loss = (t.result != "take").to_numpy()
    print(f"  perdants passes par +1R avant le stop: {(mfe[is_loss] >= 1).sum()}/{is_loss.sum()} ; par +0.5R: {(mfe[is_loss] >= 0.5).sum()}/{is_loss.sum()}")
    print(f"  gagnants passes par -0.5R avant la cible: {(mae[~is_loss] >= 0.5).sum()}/{(~is_loss).sum()} ; MAE mediane gagnants {np.median(mae[~is_loss]):.2f}R")


def main():
    now = pd.Timestamp.now(tz="UTC")
    data = {iv: bt.cache.closed_bars(bt.cache.load(bt.SYMBOL, iv), iv, now) for iv in ("5m", "15m")}
    versions = ("puts_5m", "15m_sma20", "15m_ema20")
    rng = np.random.default_rng(0)

    print("=========== PARTIE 1 : STATISTIQUES (cout 1pt) ===========")
    base = {}
    for v in versions:
        d = data["5m" if v == "puts_5m" else "15m"]
        for cost in (1.0, 3.0):
            base[(v, cost)] = run_version(v, data, cost)
        stats(v, base[(v, 1.0)], d, rng)

    print("\n=========== PARTIE 2 : PETITS REGLAGES ===========")
    print("Regle: retenu seulement si meilleur sur les 3 versions aux 2 couts ET sur les 2 moities de chaque version a 1pt")
    for name, opts in ADJUSTMENTS.items():
        ok_all = True
        cells = []
        for v in versions:
            d = data["5m" if v == "puts_5m" else "15m"]
            half = d.index[len(d) // 2]
            for cost in (1.0, 3.0):
                t0, t1 = base[(v, cost)], run_version(v, data, cost, **dict(opts))
                better = t1.net_r.sum() > t0.net_r.sum()
                ok_all &= better
                txt = f"{t0.net_r.sum():+.1f}->{t1.net_r.sum():+.1f}R"
                if cost == 1.0:
                    h = [(t0[sel0].net_r.sum(), t1[sel1].net_r.sum()) for sel0, sel1 in
                         (((t0.entry_time < half), (t1.entry_time < half)), ((t0.entry_time >= half), (t1.entry_time >= half)))]
                    halves_ok = all(b > a for a, b in h)
                    ok_all &= halves_ok
                    txt += f" (n {len(t0)}->{len(t1)}, moities {h[0][0]:+.1f}->{h[0][1]:+.1f} / {h[1][0]:+.1f}->{h[1][1]:+.1f})"
                cells.append(f"{v} {cost:.0f}pt {txt}")
        print(f"\n  {name}: {'RETENU' if ok_all else 'non retenu'}")
        for c in cells:
            print(f"    {c}")


if __name__ == "__main__":
    main()
