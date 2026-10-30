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

Promoted on 2026-10-28 to MAIN strategy (scripts/robustness_check.py: the
only family still positive without its 3 best trades, with gains capped at
+5R and with trades cut at 48h). Rules unchanged. Go-live rule, fixed on
2026-10-28 before any live trade: once the sma20 version has at least 100
closed live trades on the 10 markets, it may move to real turbos (small
size) only if its pooled net R is > 0 at 3pt-equivalent cost AND > 0 with
every gain capped at +5R (1pt). Otherwise it is not traded.

Amended on 2026-10-29 (stricter only, before the verdict, at 8 closed live
trades): calls and puts are judged SEPARATELY at the verdict, because the
whole historical edge came from puts (calls: 81 trades, -1.2R). A side
may move to real turbos only if, on its OWN closed live sma20 trades, it
has at least 30 trades AND net R > 0 at 3pt-equivalent cost AND > 0 with
every gain capped at +5R (1pt). A side with fewer than 30 trades keeps
being tracked without money. The pooled test is still shown but is no
longer enough on its own.

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
GO_LIVE_TRADES = 100
MIN_SIDE_TRADES = 30
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
    rows, totals, totals3 = [], {v: [] for v in VERSIONS}, {v: [] for v in VERSIONS}
    by_side = {(c, s): [] for c in (1.0, 3.0) for s in ("call", "put")}
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
            totals3[version].append(r3)
            if version == "sma20":
                for cost, tt in ((1.0, t), (3.0, t3)):
                    cl = tt[(tt.entry_time >= FREEZE_START) & (tt.result != "open")]
                    is_call = (cl["take"] > cl["entry"]).to_numpy()
                    by_side[(cost, "call")].append(cl.net_r.to_numpy()[is_call])
                    by_side[(cost, "put")].append(cl.net_r.to_numpy()[~is_call])
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
        r3, cap = np.concatenate(totals3[version]), np.minimum(r, 5.0).sum()
        print(f"  {version}: {len(r)} trades clos, {(r > 0).sum()} gagnants, net {r.sum():+.2f}R "
              f"(3pt-eq {r3.sum():+.2f}R, gains plafonnes a 5R {cap:+.2f}R)")
        if version == "sma20":
            sides = {}
            for side in ("call", "put"):
                s1, s3 = np.concatenate(by_side[(1.0, side)]), np.concatenate(by_side[(3.0, side)])
                scap = np.minimum(s1, 5.0).sum()
                sides[side] = len(s1) >= MIN_SIDE_TRADES and s3.sum() > 0 and scap > 0
                print(f"    {side}s: {len(s1)} trades clos, {(s1 > 0).sum()} gagnants, net {s1.sum():+.2f}R "
                      f"(3pt-eq {s3.sum():+.2f}R, plafond 5R {scap:+.2f}R)")
            if len(r) >= GO_LIVE_TRADES:
                ok = r3.sum() > 0 and cap > 0
                go = [side for side in ("call", "put") if sides[side]]
                print(f"  Test global (regle du 28/10): {'positif' if ok else 'negatif'} | Passage en reel (regle du 29/10, "
                      f"chaque cote juge seul, {MIN_SIDE_TRADES} trades min.): "
                      f"{'OUI, petite taille, ' + ' et '.join(s + 's' for s in go) + ' seulement' if go else 'NON'}")
            else:
                print(f"  Passage en reel: verdict a {GO_LIVE_TRADES} trades clos (encore {GO_LIVE_TRADES - len(r)}), "
                      f"calls et puts juges separement (regle du 29/10)")
    pd.DataFrame(rows, columns=["marche", "version", "sens", "entree_paris", "entree", "stop", "cible",
                                "sortie_paris", "resultat", "net_r"]).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
