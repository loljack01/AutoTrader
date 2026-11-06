"""Three shadow variants of the MAIN strategy, frozen on 2026-11-05 after
the quantitative audit (scripts/audit_quant.py), at the user's request.
Tracked FORWARD ONLY: trades entered from 2026-11-06 count; the history
that inspired them is shown for information and never used to judge.
The main strategy itself (frozen_15m_calls_trend.py, sma20) is NOT changed.

The audit found the main strategy's backtest edge leaning on a few extreme
trades: tiny overnight stops (entries 22h-8h Paris: 50 trades, +62.5R but
+13.0R with gains capped at 5R) and trades held for weeks (one FTSE 100 put
+39.3R over 43 days), while calls showed no edge (+0.086R/trade, t=0.5).
Each variant removes one of these, everything else identical to the main
strategy (same engine, markets, factors, costs, trend filter for calls):

  A "sortie le jour meme"  any open trade is closed at the last 15m bar of
                           its Paris day (bt.backtest session_exit=True)
  B "entrees 8h-22h"       entries only between 8:00 and 22:00 Paris
                           (bt.backtest entry_hours=(8, 22))
  C "puts seulement"       the main strategy's puts only, no calls

Verdict, for each variant at 100 closed forward trades (rule fixed now):
it may replace the main strategy as the candidate for real money (after a
discussion with the user) only if, over the SAME forward period, its net R
with gains capped at +5R (1pt) is above the main strategy's AND its net R at
3pt-equivalent is > 0. Otherwise the main strategy stays the candidate.

Amended on 2026-11-06 at the user's request (working group's "test 0", fixed
BEFORE any forward trade of it), does not use the multiple-testing budget:
  D "executable turbo"     entries only between 8:00 and 21:30 Paris and any
                           open trade closed at the close of the 21:30-21:45
                           bar (turbos do not quote 22h-8h): the part of the
                           main strategy the user can actually trade.
                           bt.backtest entry_hours=(8, 21.5), session_exit=21.75
It is NOT a candidate to replace the main strategy: it is an extra CONDITION.
The main strategy goes to real money only if D ALSO passes the same
sequential rule as the main one (frozen_15m_calls_trend.py, 05/11), judged
on D's forward trades from 2026-11-06 at 3pt-equivalent cost: checks every
100 closed trades on the cumulative net R (3pt) with gains capped at +5R,
PASSE if >= +72R; ABANDON if <= 0 from 200 trades, or <= -15R at any time,
or 600 trades without passing. If D is abandoned, the main strategy cannot
go to real money as it stands.

Usage: python scripts/frozen_15m_variants.py (reads data/cache; run after
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

FORWARD_START = pd.Timestamp("2026-11-06", tz="UTC")
VERDICT_TRADES = 100
VARIANTS = {"principale": {}, "A sortie le jour meme": {"session_exit": True},
            "B entrees 8h-22h": {"entry_hours": (8, 22)}, "C puts seulement": {"puts_only": True},
            "D executable turbo": {"entry_hours": (8, 21.5), "session_exit": 21.75}}
SEQ_PASS, SEQ_BRAKE, SEQ_MAX = 72.0, -15.0, 600
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_variants_trades.csv"


def run(symbol, d, cost, puts_only=False, **kw):
    k = MARKETS[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    parts = [bt.backtest(d, True, False, direction="sell", **kw)]
    if not puts_only:
        parts.append(bt.backtest(d, True, False, direction="buy", entry_mask=trend_up(symbol, d, "SMA", 20), **kw))
    return pd.concat(parts, ignore_index=True)


def main():
    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    data = {s: bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now) for s in MARKETS}
    rows, summary = [], {}
    for name, kw in VARIANTS.items():
        res = {}
        for cost in (1.0, 3.0):
            parts = []
            for s, d in data.items():
                t = run(s, d, cost, **kw)
                parts.append(t.assign(market=MARKETS[s][0]))
            res[cost] = pd.concat(parts, ignore_index=True)
        t1, t3 = res[1.0], res[3.0]
        hist = t1[(t1.entry_time < FORWARD_START) & (t1.result != "open")].net_r
        fw = t1[t1.entry_time >= FORWARD_START]
        closed = fw[fw.result != "open"].net_r.to_numpy()
        c3 = t3[(t3.entry_time >= FORWARD_START) & (t3.result != "open")].net_r.to_numpy()
        cap = np.minimum(closed, 5.0).sum()
        summary[name] = (len(closed), closed.sum(), c3.sum(), cap)
        if name.startswith("D "):
            fw3 = t3[(t3.entry_time >= FORWARD_START) & (t3.result != "open")].sort_values("exit_time")
            seq = np.minimum(fw3.net_r.to_numpy(), 5.0).cumsum()
            state = "en cours"
            for k in range(1, len(seq) + 1):
                if seq[k - 1] <= SEQ_BRAKE:
                    state = f"ABANDON ({seq[k - 1]:+.1f}R au trade {k})"
                    break
                if k % 100 == 0:
                    if seq[k - 1] >= SEQ_PASS:
                        state = f"PASSE au trade {k}"
                        break
                    if k >= 200 and seq[k - 1] <= 0 or k >= SEQ_MAX:
                        state = f"ABANDON au trade {k}"
                        break
            summary["_seqD"] = (len(seq), seq[-1] if len(seq) else 0.0, state)
        print(f"{name:22s} historique (info) {len(hist):3d} trades {hist.sum():+7.1f}R (plafond 5R "
              f"{np.minimum(hist, 5).sum():+6.1f}R) | depuis le 06/11 : {len(closed)} trades clos, net {closed.sum():+.2f}R, "
              f"3pt {c3.sum():+.2f}R, plafond 5R {cap:+.2f}R")
        for x in fw.itertuples():
            side = "call" if x.take > x.entry else "put"
            end = "OUVERT" if x.result == "open" else f"{x.result} {paris(x.exit_time)} {x.net_r:+.2f}R"
            if name != "principale":
                print(f"     {x.market:14s} {paris(x.entry_time)} {side:4s} entree {x.entry:.2f} stop {x.stop:.2f} "
                      f"cible {x.take:.2f} -> {end}")
            rows.append({"variante": name, "marche": x.market, "sens": side, "entree_paris": paris(x.entry_time),
                         "entree": x.entry, "stop": round(x.stop, 2), "cible": round(x.take, 2), "resultat": x.result,
                         "net_r": None if x.result == "open" else round(x.net_r, 3)})
    pd.DataFrame(rows).to_csv(OUT, index=False)
    base = summary["principale"]
    for name, (n, net, net3, cap) in ((k, v) for k, v in summary.items() if not k.startswith("_")):
        if name == "principale":
            continue
        if name.startswith("D "):
            sn, scum, state = summary["_seqD"]
            print(f"Condition du passage en reel (D, regle sequentielle a 3pt) : {sn} trades, cumul plafonne 5R "
                  f"{scum:+.1f}R, objectif +{SEQ_PASS:.0f}R aux controles de 100 en 100, frein {SEQ_BRAKE:+.0f}R -> {state}")
            continue
        if n >= VERDICT_TRADES:
            better = cap > base[3] and net3 > 0
            print(f"Verdict {name} ({n} trades) : {'MEILLEURE que la principale' if better else 'pas meilleure'}")
        else:
            print(f"{name} : verdict a {VERDICT_TRADES} trades clos (encore {VERDICT_TRADES - n})")


if __name__ == "__main__":
    main()
