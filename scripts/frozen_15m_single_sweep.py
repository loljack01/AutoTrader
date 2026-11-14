"""FROZEN on 2026-10-29: candidate "balayage d'un simple creux / sommet",
tracked live on the 10 index futures WITHOUT money. Idea from the 29/10
CAC session: a stair-step day with no equal highs or lows, so the main
strategy had no pool to sweep and no trade; the 13:00 dip only took out a
single swing low. Decided by the user on 2026-10-29 to follow it live
only: its history is computed for the reference control and shown for
information, it proves nothing (it was never used to choose the rule).

Rules: exactly the main strategy (frozen_15m_calls_trend.py, sma20: the
frozen 15m sweep + CHoCH set, stop = max(sweep extreme +/- 8pt, 2x ATR),
target = nearest unswept opposite EQH/EQL pool or last swing, net R:R >=
1.3, 4h window, Paris session filter, one trade per sweep; calls only if
the previous daily close is above its 20-day SMA, puts always), except
that the sweep may take out ANY single confirmed swing low (calls) or
swing high (puts), not only a pool of equal lows/highs
(backtest(..., single_swing_sweeps=True)). Targets unchanged. Stop
margin and cost scaled by the same fixed per-market factors. Cost 1pt
CAC-equivalent, 3pt shown as a pessimistic check.

Scorecard: only trades entered on or after FREEZE_START count.

Verdict rule (fixed now, before any live trade): once at least 100 live
trades are closed on the 10 markets together, it becomes a candidate for
real money only if its pooled net R is > 0 at 3pt-equivalent cost AND > 0
with every gain capped at +5R (1pt), AND it beats the main strategy
(sma20) over the same live period at 1pt. Calls and puts are reported
separately. Otherwise it is dropped. Until then it is not traded.

Usage: python scripts/frozen_15m_single_sweep.py [tool_result.json ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from frozen_15m_calls_trend import run as main_run
from ma_grid_test import trend_up
from other_markets_test import ingest

FREEZE_START = "2026-10-30"
REFERENCE_END = "2026-10-29"
GO_LIVE_TRADES = 100
REFERENCE = {"FCE1!": (66, -0.9), "FDAX1!": (72, 10.4), "FESX1!": (47, 9.5), "ES1!": (60, 23.1), "NQ1!": (46, 1.0),
             "ICEEUR:Z1!": (69, 16.2), "FSMI1!": (90, -16.7), "YM1!": (54, -6.2), "RTY1!": (37, 13.1),
             "FIB1!": (65, 20.6)}
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_single_sweep_trades.csv"


def run(symbol, d, cost):
    """All trades, open ones included."""
    k = MARKETS[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    up = trend_up(symbol, d, "SMA", 20)
    t = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up, single_swing_sweeps=True),
                   bt.backtest(d, True, False, direction="sell", single_swing_sweeps=True)], ignore_index=True)
    return t.sort_values("entry_time").reset_index(drop=True)


def main():
    for f in sys.argv[1:]:
        ingest(f)
    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    rows, r1s, r3s, sides, mains = [], [], [], {"call": [], "put": []}, []
    for symbol, (name, _) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        ref = run(symbol, d[d.index < REFERENCE_END], 1.0)
        ref = ref[ref.result != "open"]
        got = (len(ref), round(float(ref.net_r.sum()), 1))
        want = REFERENCE.get(symbol)
        status = "OK" if want == got else ("a fixer" if want is None else "DIFFERENT")
        t = run(symbol, d, 1.0)
        live = t[t.entry_time >= FREEZE_START]
        closed = live[live.result != "open"]
        r = closed.net_r.to_numpy()
        r1s.append(r)
        for x in closed.itertuples():
            sides["call" if x.take > x.entry else "put"].append(x.net_r)
        t3 = run(symbol, d, 3.0)
        r3s.append(t3[(t3.entry_time >= FREEZE_START) & (t3.result != "open")].net_r.to_numpy())
        m = main_run(symbol, d, 20, 1.0)
        mains.append(m[(m.entry_time >= FREEZE_START) & (m.result != "open")].net_r.to_numpy())
        print(f"{name:14s} controle reference {got[0]} trades {got[1]:+.1f}R (information) -> {status} | depuis le "
              f"{FREEZE_START}: {len(r)} trades clos, {(r > 0).sum()} gagnants, net {r.sum():+.2f}R")
        for x in live.itertuples():
            side = "call" if x.take > x.entry else "put"
            end = "OUVERT" if x.result == "open" else f"{x.result} {paris(x.exit_time)} {x.net_r:+.2f}R"
            print(f"     {paris(x.entry_time)} {side:4s} entree {x.entry:.2f} stop {x.stop:.2f} cible {x.take:.2f} -> {end}")
            rows.append({"marche": name, "sens": side, "entree_paris": paris(x.entry_time), "entree": x.entry,
                         "stop": round(x.stop, 2), "cible": round(x.take, 2),
                         "sortie_paris": "" if x.result == "open" else paris(x.exit_time),
                         "resultat": x.result, "net_r": None if x.result == "open" else round(x.net_r, 3)})
    r1, r3, mr = np.concatenate(r1s), np.concatenate(r3s), np.concatenate(mains)
    cap = np.minimum(r1, 5.0).sum()
    print(f"\n10 marches ensemble depuis le {FREEZE_START}: {len(r1)} trades clos, {(r1 > 0).sum()} gagnants, "
          f"net {r1.sum():+.2f}R (3pt-eq {r3.sum():+.2f}R, gains plafonnes a 5R {cap:+.2f}R) | calls "
          f"{sum(sides['call']):+.2f}R ({len(sides['call'])}), puts {sum(sides['put']):+.2f}R ({len(sides['put'])}) | "
          f"principale sur la meme periode {mr.sum():+.2f}R ({len(mr)} trades)")
    if len(r1) >= GO_LIVE_TRADES:
        ok = r3.sum() > 0 and cap > 0 and r1.sum() > mr.sum()
        print(f"Verdict ({len(r1)} trades): {'CANDIDATE AU REEL' if ok else 'ABANDONNEE'}")
    else:
        print(f"Verdict a {GO_LIVE_TRADES} trades clos (encore {GO_LIVE_TRADES - len(r1)})")
    pd.DataFrame(rows, columns=["marche", "sens", "entree_paris", "entree", "stop", "cible", "sortie_paris",
                                "resultat", "net_r"]).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
