"""Test 10, FROZEN on 2026-11-13 BEFORE any calculation, at the user's request
("Je voudrais aussi sur 5mn 15mn et 30mn" = chart time units): the test 9
comparison of sweep-to-CHoCH durations, repeated on 5-minute and 30-minute
bars. The 15-minute unit is test 9 (frozen_15m_window.py), unchanged.

Tracked FORWARD ONLY: trades entered from 2026-11-13 14:00 Paris count. No
past result of any unit or duration is computed or shown. The main
strategy (frozen_15m_calls_trend.py, sma20, 15m, 4h) is NOT changed.

Combinations, fixed now: units 5m and 30m x durations 1h, 2h, 4h, 6h, 8h
(clock time between the sweep bar and the entry bar) = 10 combinations.
Reference: the main strategy (15m, 4h) over the same forward period.
Everything else is the main strategy's engine with the same parameters,
computed on the unit's bars: swings n=2, stop = max(sweep extreme +/- 8pt
x market factor, 2x ATR(14) of the unit), target = nearest unswept
opposite pool, net R:R >= 1.3, Paris session filter, one trade per sweep,
calls only above the 20-day SMA, puts always, same 10 markets and costs.

Bars: 30m bars are built from the cached 15m bars, 5m bars from the cached
1m bars (accumulated since 2026-10-22/27, CAC since 2026-09-16; checked
continuous against the 15m bars on 2026-11-13). A built bar is used only
once the source data covers its whole span. Holes in the 1m data during
the forward period are counted and printed.

Verdict, once the reference (15m, 4h) has 100 closed forward trades
(cut-off = the exit time of its 100th closed trade; combinations counted
up to the same cut-off). A combination is kept as a NEW candidate only if
ALL hold:
  1. net R above the reference at 1pt AND at 3pt-equivalent cost;
  2. net R with every gain capped at +5R (1pt) above the reference;
  3. its own net R at 3pt-equivalent > 0;
  4. t-statistic of the differences (combination - reference, net R at
     1pt summed per Paris entry day) >= 2.84 (Bonferroni 5 % / 22 tests,
     one-sided).
If several pass, the one with the highest capped net R. If none passes,
nothing is kept and no other unit or duration is tried. A kept combination
does not change the main strategy and nothing goes to real money: it
would start its own sequential test from zero.

Usage: python scripts/frozen_window_units.py (reads data/cache; run after
the day's 15m and 1m files are ingested)
"""

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS

FORWARD_START = pd.Timestamp("2026-11-13 13:00", tz="UTC")  # 14:00 Paris
UNITS = {"5m": ("1m", 1, 5), "30m": ("15m", 15, 30)}  # unit: (source interval, source minutes, unit minutes)
HOURS = (1, 2, 4, 6, 8)
REFERENCE = ("15m", 4)
VERDICT_TRADES = 100
T_MIN = 2.84
AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
COLS = ["entry_time", "sweep_time", "entry", "stop", "take", "exit_time", "result", "net_r"]
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_window_units_trades.csv"


def bars(symbol, unit, now):
    """Closed bars of `unit`; 5m and 30m are built from the cached 1m / 15m bars."""
    if unit == "15m":
        return bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now), 15
    source, src_min, minutes = UNITS[unit]
    src = bt.cache.closed_bars(bt.cache.load(symbol, source), source, now)
    d = src.resample(f"{minutes}min", label="left", closed="left").agg(AGG).dropna(subset=["Open"])
    covered = src.index[-1] + pd.Timedelta(minutes=src_min)  # the source data stops here
    return d[d.index + pd.Timedelta(minutes=minutes) <= covered], minutes


def trend_up(symbol, d, minutes, n=20):
    """ma_grid_test.trend_up with the bar's real length: previous daily close above its n-day SMA."""
    daily = bt.cache.load(symbol, "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    ma = daily.Close.rolling(n).mean()
    up = (daily.Close > ma).to_numpy() & ma.notna().to_numpy()
    done_at = (daily.index + pd.Timedelta(days=1)).to_numpy()
    pos = np.searchsorted(done_at, (d.index + pd.Timedelta(minutes=minutes)).to_numpy(), side="right") - 1
    return np.where(pos >= 0, up[np.clip(pos, 0, None)], False).astype(bool)


def job(args):
    unit, symbol, hours, cost, now = args
    d, minutes = bars(symbol, unit, now)
    k = MARKETS[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=hours)
    t = pd.concat([bt.backtest(d, True, False, direction="sell"),
                   bt.backtest(d, True, False, direction="buy", entry_mask=trend_up(symbol, d, minutes))],
                  ignore_index=True)
    t = t[t.entry_time >= FORWARD_START]  # nothing before the freeze is kept, shown or summed
    return (unit, hours, cost), t.assign(market=MARKETS[symbol][0])


def holes(now):
    """15m bars of the forward period with no 1m bar inside: the 5m bars there are missing."""
    n = 0
    for s in MARKETS:
        q = bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now)
        m = bt.cache.closed_bars(bt.cache.load(s, "1m"), "1m", now)
        if not len(m):
            continue
        q = q[(q.index >= FORWARD_START) & (q.index + pd.Timedelta(minutes=15) <= m.index[-1])]
        n += len(q.index.difference(m.index.floor("15min")))
    return n


def main():
    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    combos = [REFERENCE] + [(u, h) for u in UNITS for h in HOURS]
    tasks = [(u, s, h, c, now) for u, h in combos for c in (1.0, 3.0) for s in MARKETS]
    fw = {}
    with ProcessPoolExecutor(max_workers=4) as pool:
        for key, t in pool.map(job, tasks, chunksize=4):
            fw.setdefault(key, []).append(t)
    fw = {k: pd.concat(v, ignore_index=True) for k, v in fw.items()}
    closed = lambda t: t[t.result != "open"]
    ref = closed(fw[REFERENCE + (1.0,)]).sort_values("exit_time")
    done = len(ref) >= VERDICT_TRADES
    cutoff = ref.exit_time.iloc[VERDICT_TRADES - 1] if done else None
    upto = lambda t: closed(t)[closed(t).exit_time <= cutoff] if done else closed(t)
    day = lambda t: t.net_r.astype(float).groupby(
        pd.to_datetime(t.entry_time, utc=True).dt.tz_convert("Europe/Paris").dt.date).sum()

    print(f"Test 10 - durees de fenetre sur bougies de 5 et 30 minutes, suivi en avant depuis le "
          f"{paris(FORWARD_START)} (Paris)")
    print(f"  trous dans les bougies d'une minute depuis le debut du suivi : {holes(now)} quart(s) d'heure")
    rows, stats = [], {}
    for u, h in combos:
        t1, c1, c3 = fw[u, h, 1.0], upto(fw[u, h, 1.0]), upto(fw[u, h, 3.0])
        stats[u, h] = (len(c1), c1.net_r.sum(), c3.net_r.sum(), np.minimum(c1.net_r.astype(float), 5.0).sum(), day(c1))
        n, net, net3, cap, _ = stats[u, h]
        tag = " (reference = principale)" if (u, h) == REFERENCE else ""
        print(f"  {u:>3s} {h}h{tag} : {n} trades clos, net {net:+.2f}R, 3pt {net3:+.2f}R, plafond 5R {cap:+.2f}R, "
              f"{int((t1.result == 'open').sum())} ouverts")
        for x in t1.sort_values("entry_time").itertuples():
            rows.append({"unite": u, "duree_h": h, "marche": x.market, "sens": "call" if x.take > x.entry else "put",
                         "balayage_paris": paris(x.sweep_time), "entree_paris": paris(x.entry_time), "entree": x.entry,
                         "stop": round(x.stop, 2), "cible": round(x.take, 2), "resultat": x.result,
                         "sortie_paris": None if x.result == "open" else paris(x.exit_time),
                         "net_r": None if x.result == "open" else round(x.net_r, 3)})
    pd.DataFrame(rows, columns=["unite", "duree_h", "marche", "sens", "balayage_paris", "entree_paris", "entree",
                                "stop", "cible", "resultat", "sortie_paris", "net_r"]).to_csv(OUT, index=False)

    n_ref, net_ref, net3_ref, cap_ref, day_ref = stats[REFERENCE]
    if not done:
        print(f"Verdict a {VERDICT_TRADES} trades clos de la reference 15m 4h (encore {VERDICT_TRADES - n_ref}). "
              "Aucune combinaison n'est retenue ni ecartee avant.")
        return
    print(f"VERDICT (coupure a la sortie du {VERDICT_TRADES}e trade de la reference, {paris(cutoff)}) :")
    kept = []
    for u, h in combos[1:]:
        n, net, net3, cap, dd = stats[u, h]
        diff = dd.sub(day_ref, fill_value=0.0)
        sd = diff.std(ddof=1)
        t = diff.mean() / (sd / np.sqrt(len(diff))) if len(diff) > 1 and sd > 0 else 0.0
        ok = net > net_ref and net3 > net3_ref and cap > cap_ref and net3 > 0 and t >= T_MIN
        print(f"  {u:>3s} {h}h : net {net:+.2f}R vs {net_ref:+.2f}R, 3pt {net3:+.2f}R vs {net3_ref:+.2f}R, plafond "
              f"{cap:+.2f}R vs {cap_ref:+.2f}R, t {t:.2f} (seuil {T_MIN}) -> {'RETENUE' if ok else 'non retenue'}")
        if ok:
            kept.append((cap, u, h))
    print(f"  -> nouvelle candidate : {max(kept)[1]} {max(kept)[2]}h (la principale n'est pas modifiee)" if kept
          else "  -> rien n'est retenu ; aucune autre unite ni duree ne sera essayee")


if __name__ == "__main__":
    main()
