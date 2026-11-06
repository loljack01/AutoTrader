"""Audit marche 06/11/2026 - extraction DESCRIPTIVE des trades de la principale
(sma20, 10 futures, moteur frozen_15m_calls_trend.run, cout 1 pt CAC-eq), tout le
cache 15m (reference + suivi depuis le 28/10). Aucune regle modifiee ni testee.
Ecrit trades_principale.csv dans ce dossier (rien dans le depot).

Usage: PYTHONDONTWRITEBYTECODE=1 python3 /home/user/AutoTrader/audit/2026-11-06/marche/main_trades.py
"""
import sys
from pathlib import Path

REPO = Path("/home/user/AutoTrader")
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
from finta import TA

import backtest_liquidity_sweep_buy as bt
import frozen_15m_calls_trend as fc
from levels import structure, liquidity
from events import load_events

HERE = Path(__file__).resolve().parent
NOW = pd.Timestamp("2026-11-06 07:00", tz="UTC")   # cache 15m: derniere bougie 05/11 21:45 UTC
CODE = {"FCE1!": "FCE1", "FDAX1!": "FDAX1", "FESX1!": "FESX1", "ES1!": "ES1", "NQ1!": "NQ1",
        "ICEEUR:Z1!": "ICEEUR_Z1", "FSMI1!": "FSMI1", "YM1!": "YM1", "RTY1!": "RTY1", "FIB1!": "FIB1"}


def swept_pool_broken(d, side, sweep_times):
    """Pour chaque balayage, True si TOUS / AU MOINS UN des pools balayes a cette bougie
    avait deja ete casse en cloture (cloture au-dela du niveau entre la confirmation du
    2e membre et la bougie du balayage)."""
    atr = TA.ATR(d, 14)
    is_hi, is_lo = structure.find_swings(d, n=2)
    marks = structure.confirmed_marks(is_lo if side == 1 else is_hi, d.Low if side == 1 else d.High, 2)
    kind = "low" if side == 1 else "high"
    pools = liquidity.find_sweeps(liquidity.find_pools(marks, atr), d, kind)
    pos = {ts: i for i, ts in enumerate(d.index)}
    c = d.Close.to_numpy()
    by_sweep = {}
    for p in pools:
        if p["swept_at"] is None:
            continue
        a, b = pos[p["members"][1][0]] + 1, pos[p["swept_at"]]
        seg = c[a:b]
        broken = bool((seg < p["level"]).any() if side == 1 else (seg > p["level"]).any())
        by_sweep.setdefault(p["swept_at"], []).append(broken)
    out = {}
    for s in sweep_times:
        v = by_sweep.get(s, [])
        out[s] = (all(v) if v else np.nan, any(v) if v else np.nan, len(v))
    return out


def main():
    ev = load_events()
    vix = pd.read_csv(REPO / "data/cache/TVC_VIX_1D.csv", index_col=0, parse_dates=True)
    vix.index = pd.to_datetime(vix.index, utc=True).tz_convert("Europe/Paris").normalize().tz_localize(None)
    vix = vix.Close[~vix.index.duplicated(keep="last")].sort_index()
    rows = []
    for sym, (name, k) in fc.MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(sym, "15m"), "15m", NOW)
        d.index = pd.to_datetime(d.index, utc=True)
        d = d[~d.index.duplicated(keep="last")].sort_index()
        t = fc.run(sym, d, 20, 1.0)
        t = t[t.result != "open"].copy()
        atr15 = TA.ATR(d, 14)
        t["side"] = np.where(t["take"] > t["entry"], "call", "put")
        t["market"], t["symbol"], t["k"] = name, sym, k
        t["risk"] = (t.entry - t.stop).abs()
        t["risk_cac"] = t.risk / k
        t["atr15"] = atr15.reindex(t.entry_time).to_numpy()
        t["risk_atr15"] = t.risk / t.atr15
        t["rr_target"] = (t["take"] - t.entry).abs() / t.risk
        t["gross_r"] = t.net_r + 1.0 * k / t.risk
        t["net_r3"] = t.gross_r - 3.0 * k / t.risk
        # balayage sur niveau deja casse en cloture
        for col in ("sweep_broken_all", "sweep_broken_any", "n_pools_swept"):
            t[col] = pd.Series(np.nan, index=t.index, dtype=object)
        for side, sname in ((1, "call"), (-1, "put")):
            m = t.side == sname
            info = swept_pool_broken(d, side, t.loc[m, "sweep_time"])
            t.loc[m, "sweep_broken_all"] = [info[s][0] for s in t.loc[m, "sweep_time"]]
            t.loc[m, "sweep_broken_any"] = [info[s][1] for s in t.loc[m, "sweep_time"]]
            t.loc[m, "n_pools_swept"] = [info[s][2] for s in t.loc[m, "sweep_time"]]
        # journalier du future : ATR14 % (veille), tendance SMA20 / SMA50
        dd = bt.cache.load(sym, "1D")
        dd.index = pd.to_datetime(dd.index, utc=True)
        dd = dd[~dd.index.duplicated(keep="last")].sort_index()
        tr = pd.concat([dd.High - dd.Low, (dd.High - dd.Close.shift()).abs(), (dd.Low - dd.Close.shift()).abs()], axis=1).max(axis=1)
        atrp = tr.ewm(alpha=1 / 14, adjust=False).mean() / dd.Close
        atr_rank = atrp.rolling(250, min_periods=120).apply(lambda x: (x[-1] >= x).mean(), raw=True)
        dpar = dd.index.tz_convert("Europe/Paris").normalize().tz_localize(None)
        daily = pd.DataFrame({"atrp": atrp.to_numpy(), "atr_rank": atr_rank.to_numpy(),
                              "above20": (dd.Close > dd.Close.rolling(20).mean()).to_numpy(),
                              "above50": (dd.Close > dd.Close.rolling(50).mean()).to_numpy(),
                              "dist200": (dd.Close / dd.Close.rolling(200).mean() - 1).to_numpy()}, index=dpar)
        daily = daily[~daily.index.duplicated(keep="last")]
        ep = t.entry_time.dt.tz_convert("Europe/Paris")
        prev = [daily.index[daily.index < x.normalize().tz_localize(None)][-1] for x in ep]
        for col in daily.columns:
            t[col] = daily.loc[prev, col].to_numpy()
        vprev = [vix.index[vix.index < x.normalize().tz_localize(None)][-1] for x in ep]
        t["vix_prev"] = vix.loc[vprev].to_numpy()
        rows.append(t)
    t = pd.concat(rows, ignore_index=True).sort_values("entry_time").reset_index(drop=True)
    ep = t.entry_time.dt.tz_convert("Europe/Paris")
    xp = t.exit_time.dt.tz_convert("Europe/Paris")
    t["entry_paris"], t["exit_paris"] = ep.dt.strftime("%Y-%m-%d %H:%M"), xp.dt.strftime("%Y-%m-%d %H:%M")
    t["hour"] = ep.dt.hour + ep.dt.minute / 60
    t["weekday"] = ep.dt.dayofweek
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    sat = []
    for a, b in zip(ep, xp):
        days = pd.date_range(a.normalize(), b.normalize(), freq="D")
        sat.append(bool((days.dayofweek == 5).any()))
    t["weekend"] = sat
    t["live"] = t.entry_time >= pd.Timestamp(fc.FREEZE_START, tz="UTC")
    # annonces : jour (date Paris) et fenetre +/-30 min autour de l'heure, ou annonce pendant le trade
    edate = ev.assign(day=ev.time.dt.tz_convert("Europe/Paris").dt.date)
    for typ in ("NFP", "CPI", "FOMC", "BCE"):
        days = set(edate[edate.type == typ].day)
        t["day_" + typ] = [x.date() in days for x in ep]
    t["event_day"] = t[[f"day_{x}" for x in ("NFP", "CPI", "FOMC", "BCE")]].any(axis=1)
    times = ev.time.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy().astype("datetime64[ns]")
    t["entry_near_event"] = [bool((np.abs((times - a.tz_convert("UTC").tz_localize(None).to_datetime64()) / np.timedelta64(1, "m")) <= 30).any()) for a in t.entry_time]
    t["event_during"] = [bool(((times >= a.tz_convert("UTC").tz_localize(None).to_datetime64()) & (times <= b.tz_convert("UTC").tz_localize(None).to_datetime64())).any()) for a, b in zip(t.entry_time, t.exit_time)]
    t.to_csv(HERE / "trades_principale.csv", index=False)
    print(f"{len(t)} trades clos, {t.entry_time.min():%d/%m/%Y} -> {t.entry_time.max():%d/%m/%Y}; suivi (>= 28/10) {t.live.sum()}")
    print(f"total net 1pt {t.net_r.sum():+.1f}R, moy {t.net_r.mean():+.3f}R; 3pt {t.net_r3.sum():+.1f}R")


if __name__ == "__main__":
    main()
