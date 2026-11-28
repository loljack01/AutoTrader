"""Test 9, FROZEN on 2026-11-13 BEFORE any calculation, at the user's request
("optimise sur les seances en cours"): the sweep-to-CHoCH window of the MAIN
strategy, never optimised (4h is a convention of 2026-10-07; only 1h was
tried, on 2026-10-27, and did not hold).

Tracked FORWARD ONLY: trades entered from 2026-11-13 11:00 Paris count. No
past result of any duration is computed or shown, so the choice cannot be
made on data already seen. The main strategy itself
(frozen_15m_calls_trend.py, sma20, 4h) is NOT changed.

Durations, fixed now (clock time between the sweep bar and the entry bar):
  1h, 2h, 4h (reference = the main strategy), 6h, 8h
8h is the longest that never carries a sweep over the European night
(22h -> 8h = 10h). Everything else is the main strategy: same engine,
markets, factors, costs, calls only above the 20-day SMA, puts always.

Verdict, once the 4h reference has 100 closed forward trades (cut-off = the
exit time of its 100th closed trade; other durations counted up to the same
cut-off). A duration is kept as a NEW candidate only if ALL hold:
  1. net R above the 4h reference at 1pt AND at 3pt-equivalent cost;
  2. net R with every gain capped at +5R (1pt) above the reference;
  3. its own net R at 3pt-equivalent > 0;
  4. t-statistic of the differences (duration - reference, net R at 1pt
     summed per Paris entry day) >= 2.64 (Bonferroni 5 % / 12 tests,
     one-sided).
If several pass, the one with the highest capped net R. If none passes, 4h
stays and no other duration is tried. A kept duration does not change the
main strategy and nothing goes to real money: it would start its own
sequential test from zero.

Usage: python scripts/frozen_15m_window.py (reads data/cache; run after
frozen_15m_calls_trend.py, which ingests the day's files)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from ma_grid_test import trend_up

FORWARD_START = pd.Timestamp("2026-11-13 10:00", tz="UTC")  # 11:00 Paris
HOURS = (1, 2, 4, 6, 8)
REFERENCE = 4
VERDICT_TRADES = 100
T_MIN = 2.64
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_window_trades.csv"


def run(symbol, d, cost, hours):
    k = MARKETS[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=hours)
    t = pd.concat([bt.backtest(d, True, False, direction="sell"),
                   bt.backtest(d, True, False, direction="buy", entry_mask=trend_up(symbol, d, "SMA", 20))],
                  ignore_index=True)
    return t[t.entry_time >= FORWARD_START]  # nothing before the freeze is kept, shown or summed


def main():
    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    data = {s: bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now) for s in MARKETS}
    fw = {}
    for h in HOURS:
        for cost in (1.0, 3.0):
            fw[h, cost] = pd.concat([run(s, d, cost, h).assign(market=MARKETS[s][0]) for s, d in data.items()],
                                    ignore_index=True)
    closed = lambda t: t[t.result != "open"]
    ref = closed(fw[REFERENCE, 1.0]).sort_values("exit_time")
    done = len(ref) >= VERDICT_TRADES
    cutoff = ref.exit_time.iloc[VERDICT_TRADES - 1] if done else None
    upto = lambda t: closed(t)[closed(t).exit_time <= cutoff] if done else closed(t)
    day = lambda t: t.net_r.astype(float).groupby(
        pd.to_datetime(t.entry_time, utc=True).dt.tz_convert("Europe/Paris").dt.date).sum()

    print(f"Test 9 - duree de la fenetre balayage -> CHoCH, suivi en avant depuis le {paris(FORWARD_START)} (Paris)")
    rows, stats = [], {}
    for h in HOURS:
        t1, t3 = fw[h, 1.0], fw[h, 3.0]
        c1, c3 = upto(t1), upto(t3)
        stats[h] = (len(c1), c1.net_r.sum(), c3.net_r.sum(), np.minimum(c1.net_r, 5.0).sum(), day(c1))
        n, net, net3, cap, _ = stats[h]
        tag = " (reference = principale)" if h == REFERENCE else ""
        print(f"  {h}h{tag} : {n} trades clos, net {net:+.2f}R, 3pt {net3:+.2f}R, plafond 5R {cap:+.2f}R, "
              f"{int((t1.result == 'open').sum())} ouverts")
        for x in t1.sort_values("entry_time").itertuples():
            side = "call" if x.take > x.entry else "put"
            rows.append({"duree_h": h, "marche": x.market, "sens": side, "balayage_paris": paris(x.sweep_time),
                         "entree_paris": paris(x.entry_time), "entree": x.entry, "stop": round(x.stop, 2),
                         "cible": round(x.take, 2), "resultat": x.result,
                         "sortie_paris": None if x.result == "open" else paris(x.exit_time),
                         "net_r": None if x.result == "open" else round(x.net_r, 3)})
    pd.DataFrame(rows, columns=["duree_h", "marche", "sens", "balayage_paris", "entree_paris", "entree", "stop",
                                "cible", "resultat", "sortie_paris", "net_r"]).to_csv(OUT, index=False)

    n_ref, net_ref, net3_ref, cap_ref, day_ref = stats[REFERENCE]
    if not done:
        print(f"Verdict a {VERDICT_TRADES} trades clos de la reference 4h (encore {VERDICT_TRADES - n_ref}). "
              "Aucune duree n'est retenue ni ecartee avant.")
        return
    print(f"VERDICT (coupure a la sortie du {VERDICT_TRADES}e trade de la reference, {paris(cutoff)}) :")
    kept = []
    for h in HOURS:
        if h == REFERENCE:
            continue
        n, net, net3, cap, dd = stats[h]
        diff = dd.sub(day_ref, fill_value=0.0)
        sd = diff.std(ddof=1)
        t = diff.mean() / (sd / np.sqrt(len(diff))) if len(diff) > 1 and sd > 0 else 0.0
        ok = net > net_ref and net3 > net3_ref and cap > cap_ref and net3 > 0 and t >= T_MIN
        print(f"  {h}h : net {net:+.2f}R vs {net_ref:+.2f}R, 3pt {net3:+.2f}R vs {net3_ref:+.2f}R, plafond "
              f"{cap:+.2f}R vs {cap_ref:+.2f}R, t {t:.2f} (seuil {T_MIN}) -> {'RETENUE' if ok else 'non retenue'}")
        if ok:
            kept.append((cap, h))
    print(f"  -> nouvelle candidate : {max(kept)[1]}h (la principale n'est pas modifiee)" if kept
          else "  -> 4h reste ; aucune autre duree ne sera essayee")


if __name__ == "__main__":
    main()
