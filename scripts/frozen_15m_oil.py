"""FROZEN on 2026-10-30: the main strategy applied UNCHANGED to crude oil
(WTI NYMEX:CL1! and Brent ICEEUR:BRN1!), at the user's request. Two uses:

1. Out-of-sample check of the main strategy (information): oil was never
   used to design or choose it. Rule fixed before running: the main
   strategy "holds on oil" only if, on the bars before 2026-10-29 (15m
   history from August 2026 only), the two oil markets pooled are > 0 at
   3pt-equivalent cost AND > 0 with every gain capped at +5R (1pt).
   Otherwise it "does not hold on oil", one more fragility sign. This flag
   changes nothing in the main strategy or its go-live rule.
2. Live tracking WITHOUT money from FREEZE_START, separate from the main
   strategy's 100-trade count (oil never enters that count).

Rules: exactly frozen_15m_calls_trend.py sma20 (frozen 15m sweep + CHoCH
set, stop = max(sweep extreme +/- 8pt, 2x ATR), target = nearest unswept
opposite pool, net R:R >= 1.3, 4h window, Paris session filter, one trade
per sweep; calls only if the previous daily close is above its 20-day
SMA, puts always). Stop margin and cost in CAC points times a FIXED factor
(median 15m close before 2026-10-27 / 7900, as for the indices): WTI
0.0115, Brent 0.0125. Cost 1pt CAC-equivalent, 3pt shown.

Live verdict (fixed now): once at least 50 live trades are closed on the
two oil markets together, oil becomes a candidate for real turbos only if
its net R is > 0 at 3pt-equivalent cost AND > 0 with every gain capped at
+5R; calls and puts are shown separately. Otherwise it is dropped.

Usage: python scripts/frozen_15m_oil.py [tool_result.json ...]
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

FREEZE_START = "2026-10-30"
REFERENCE_END = "2026-10-29"
MIN_LIVE_TRADES = 50
OIL = {"NYMEX:CL1!": ("Petrole WTI", 0.0115), "ICEEUR:BRN1!": ("Petrole Brent", 0.0125)}
REFERENCE = {}
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_oil_trades.csv"


def run(symbol, d, cost):
    """All trades, open ones included."""
    k = OIL[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    up = trend_up(symbol, d, "SMA", 20)
    t = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up),
                   bt.backtest(d, True, False, direction="sell")], ignore_index=True)
    return t.sort_values("entry_time").reset_index(drop=True)


def closed(t):
    return t[t.result.isin(["stop", "take"])]


def side(t):
    return np.where(t["take"] > t["entry"], "call", "put")


def main():
    for f in sys.argv[1:]:
        ingest(f)
    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    hist1, hist3, live1, live3, live_side, rows = [], [], [], [], [], []
    for symbol, (name, _) in OIL.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        h = d[d.index < REFERENCE_END]
        r1 = closed(run(symbol, h, 1.0))
        r3 = closed(run(symbol, h, 3.0))
        got = (len(r1), round(float(r1.net_r.sum()), 1))
        want = REFERENCE.get(symbol)
        status = "OK" if want == got else ("a fixer" if want is None else "DIFFERENT")
        hist1.append(r1.assign(side=side(r1)))
        hist3.append(r3)
        t = run(symbol, d, 1.0)
        live = t[t.entry_time >= FREEZE_START]
        lc = closed(live)
        t3 = run(symbol, d, 3.0)
        live1.append(lc.net_r.to_numpy())
        live3.append(closed(t3[t3.entry_time >= FREEZE_START]).net_r.to_numpy())
        live_side.append(lc.assign(side=side(lc)))
        print(f"{name:14s} controle reference {got[0]} trades {got[1]:+.1f}R -> {status} | historique depuis "
              f"{paris(d.index[0])} | depuis le {FREEZE_START}: {len(lc)} trades clos, {(lc.net_r > 0).sum()} gagnants, "
              f"net {lc.net_r.sum():+.2f}R")
        for x in live.itertuples():
            s = "call" if x.take > x.entry else "put"
            end = "OUVERT" if x.result == "open" else f"{x.result} {paris(x.exit_time)} {x.net_r:+.2f}R"
            print(f"     {paris(x.entry_time)} {s:4s} entree {x.entry:.2f} stop {x.stop:.2f} cible {x.take:.2f} -> {end}")
            rows.append({"marche": name, "sens": s, "entree_paris": paris(x.entry_time), "entree": x.entry,
                         "stop": round(x.stop, 2), "cible": round(x.take, 2),
                         "sortie_paris": "" if x.result == "open" else paris(x.exit_time),
                         "resultat": x.result, "net_r": None if x.result == "open" else round(x.net_r, 3)})
    h1 = pd.concat(hist1)
    r = h1.net_r.to_numpy()
    h3 = np.concatenate([x.net_r.to_numpy() for x in hist3])
    cap, top3 = np.minimum(r, 5).sum(), np.sort(r)[::-1][3:].sum()
    holds = h3.sum() > 0 and cap > 0
    print(f"\nHors echantillon (avant le {REFERENCE_END}, information) : {len(r)} trades, {(r > 0).mean() if len(r) else 0:.0%} "
          f"gagnants, net {r.sum():+.1f}R (3pt-eq {h3.sum():+.1f}R, plafond 5R {cap:+.1f}R, sans top 3 {top3:+.1f}R) | "
          f"calls {h1[h1.side == 'call'].net_r.sum():+.1f}R ({(h1.side == 'call').sum()}), "
          f"puts {h1[h1.side == 'put'].net_r.sum():+.1f}R ({(h1.side == 'put').sum()})")
    print(f"Regle fixee avant : la principale {'TIENT' if holds else 'NE TIENT PAS'} sur le petrole")
    l1, l3 = np.concatenate(live1), np.concatenate(live3)
    ls = pd.concat(live_side)
    lcap = np.minimum(l1, 5).sum()
    print(f"\nSuivi reel sans argent depuis le {FREEZE_START} : {len(l1)} trades clos, {(l1 > 0).sum()} gagnants, "
          f"net {l1.sum():+.2f}R (3pt-eq {l3.sum():+.2f}R, plafond 5R {lcap:+.2f}R) | calls "
          f"{ls[ls.side == 'call'].net_r.sum():+.2f}R, puts {ls[ls.side == 'put'].net_r.sum():+.2f}R")
    if len(l1) >= MIN_LIVE_TRADES:
        print(f"Verdict ({len(l1)} trades): {'CANDIDAT AU REEL' if l3.sum() > 0 and lcap > 0 else 'ABANDONNE'}")
    else:
        print(f"Verdict a {MIN_LIVE_TRADES} trades clos (encore {MIN_LIVE_TRADES - len(l1)})")
    pd.DataFrame(rows, columns=["marche", "sens", "entree_paris", "entree", "stop", "cible", "sortie_paris",
                                "resultat", "net_r"]).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
