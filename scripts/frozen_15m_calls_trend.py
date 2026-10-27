"""FROZEN on 2026-10-27: candidate "calls avec la tendance, puts toujours",
the only fix that held on markets never looked at
(scripts/improved_15m_test.py, scripts/ma_grid_test.py). Tracked live on 10
index futures, next to the frozen versions (which do not change).

Rules: the frozen 15m sweep + CHoCH set (stop = max(sweep extreme +/- 8pt,
2x ATR), target = nearest unswept opposite pool, net R:R >= 1.3, 4h
window, Paris session filter, one trade per sweep), with:
  calls only if the previous daily close is above its N-day SMA of daily
  closes; puts always allowed.
Two versions, declared before any live trade:
  sma20 (main)        N = 20, chosen on the 5 original markets
  sma10 (comparison)  N = 10
Stop margin and cost are in CAC points times a FIXED factor per market
(CAC 1.0; others: median 15m close before 2026-10-27 / 7900). Cost 1pt
CAC-equivalent, 3pt shown as a pessimistic check.

Scorecard: only trades entered on or after FREEZE_START count. Reference
(bars before 2026-10-27, 1pt-eq) checked each run.

Usage: python scripts/frozen_15m_calls_trend.py [tool_result.json ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from ma_grid_test import trend_up
from other_markets_test import ingest

FREEZE_START = "2026-10-28"
REFERENCE_END = "2026-10-27"
MARKETS = {"FCE1!": ("CAC 40", 1.0), "FDAX1!": ("DAX", 3.2397), "FESX1!": ("Euro Stoxx 50", 0.8004),
           "ES1!": ("S&P 500", 0.9799), "NQ1!": ("Nasdaq 100", 3.7619), "ICEEUR:Z1!": ("FTSE 100", 1.362),
           "FSMI1!": ("SMI", 1.7999), "YM1!": ("Dow Jones", 6.6697), "RTY1!": ("Russell 2000", 0.3678),
           "FIB1!": ("FTSE MIB", 6.5848)}
VERSIONS = {"sma20": 20, "sma10": 10}
REFERENCE = {("FCE1!", "sma20"): (29, 15.0), ("FCE1!", "sma10"): (30, 14.0),
             ("FDAX1!", "sma20"): (29, 2.6), ("FDAX1!", "sma10"): (34, -0.1),
             ("FESX1!", "sma20"): (26, 11.2), ("FESX1!", "sma10"): (28, 12.3),
             ("ES1!", "sma20"): (45, 25.9), ("ES1!", "sma10"): (42, 23.6),
             ("NQ1!", "sma20"): (21, 7.7), ("NQ1!", "sma10"): (19, 5.9),
             ("ICEEUR:Z1!", "sma20"): (27, 30.7), ("ICEEUR:Z1!", "sma10"): (23, 42.6),
             ("FSMI1!", "sma20"): (41, -18.3), ("FSMI1!", "sma10"): (43, -17.8),
             ("YM1!", "sma20"): (25, -2.5), ("YM1!", "sma10"): (24, 1.2),
             ("RTY1!", "sma20"): (26, 15.1), ("RTY1!", "sma10"): (28, 13.0),
             ("FIB1!", "sma20"): (24, 9.7), ("FIB1!", "sma10"): (22, 7.1)}
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_calls_trend_trades.csv"


def run(symbol, d, n, cost):
    """All trades, open ones included."""
    k = MARKETS[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    up = trend_up(symbol, d, "SMA", n)
    t = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up),
                   bt.backtest(d, True, False, direction="sell")], ignore_index=True)
    return t.sort_values("entry_time").reset_index(drop=True)


def main():
    for f in sys.argv[1:]:
        ingest(f)
    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    rows, totals = [], {v: [] for v in VERSIONS}
    for symbol, (name, _) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        print(f"\n######## {name} ({symbol}) 15m jusqu'au {paris(d.index[-1] + pd.Timedelta(minutes=15))} (Paris)")
        for version, n in VERSIONS.items():
            ref = run(symbol, d[d.index < REFERENCE_END], n, 1.0)
            ref = ref[ref.result != "open"]
            got = (len(ref), round(float(ref.net_r.sum()), 1))
            want = REFERENCE.get((symbol, version))
            status = "OK" if want == got else ("a fixer" if want is None else "DIFFERENT")
            t = run(symbol, d, n, 1.0)
            live = t[t.entry_time >= FREEZE_START]
            r = live[live.result != "open"].net_r.to_numpy()
            totals[version].append(r)
            t3 = run(symbol, d, n, 3.0)
            r3 = t3[(t3.entry_time >= FREEZE_START) & (t3.result != "open")].net_r.to_numpy()
            print(f"  {version} controle reference {got[0]} trades {got[1]:+.1f}R -> {status} | depuis le {FREEZE_START}: "
                  f"{len(r)} trades clos, {(r > 0).sum()} gagnants, net {r.sum():+.2f}R (3pt-eq {r3.sum():+.2f}R)")
            for x in live.itertuples():
                side = "call" if x.take > x.entry else "put"
                end = "OUVERT" if x.result == "open" else f"{x.result} {paris(x.exit_time)} {x.net_r:+.2f}R"
                print(f"     {paris(x.entry_time)} {side:4s} entree {x.entry:.2f} stop {x.stop:.2f} cible {x.take:.2f} -> {end}")
                rows.append({"marche": name, "version": version, "sens": side, "entree_paris": paris(x.entry_time),
                             "entree": x.entry, "stop": round(x.stop, 2), "cible": round(x.take, 2),
                             "sortie_paris": "" if x.result == "open" else paris(x.exit_time),
                             "resultat": x.result, "net_r": None if x.result == "open" else round(x.net_r, 3)})
    print(f"\n######## Les 10 marches ensemble, cout 1pt-eq, depuis le {FREEZE_START}")
    for version, parts in totals.items():
        r = np.concatenate(parts)
        print(f"  {version}: {len(r)} trades clos, {(r > 0).sum()} gagnants, net {r.sum():+.2f}R")
    pd.DataFrame(rows, columns=["marche", "version", "sens", "entree_paris", "entree", "stop", "cible",
                                "sortie_paris", "resultat", "net_r"]).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
