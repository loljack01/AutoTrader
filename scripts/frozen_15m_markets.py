"""FROZEN on 2026-10-27: the frozen 15m rules (scripts/frozen_15m_daily.py),
unchanged, tracked on four more index futures to get more trades than the
CAC alone: DAX (FDAX1!), Euro Stoxx 50 (FESX1!), S&P 500 (ES1!), Nasdaq 100
(NQ1!). Same two versions as the out-of-market test
(scripts/other_markets_test.py): none and sma20. The stop margin (8pt CAC)
and the cost (1pt CAC, 3pt as a pessimistic check) are scaled by a FIXED
factor per market (its median 15m close before 2026-10-27 / 7900), so the
rules do not drift as new bars arrive.

Scorecard: only trades entered on or after FREEZE_START count. Capital:
--capital EUR, 1% of current capital risked per trade, per market.

Reference (bars before 2026-10-27, 1pt-eq), checked each run: a different
result on that period means the code or the cached data changed.

Usage: python scripts/frozen_15m_markets.py [--capital 1000] [tool_result.json ...]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from other_markets_test import MARKETS, ingest, trend_up

FREEZE_START = "2026-10-28"
REFERENCE_END = "2026-10-27"
SCALE = {"FDAX1!": 3.2397, "FESX1!": 0.8004, "ES1!": 0.9799, "NQ1!": 3.7619}
REFERENCE = {("FDAX1!", "none"): (48, -3.6), ("FDAX1!", "sma20"): (20, -1.6),
             ("FESX1!", "none"): (48, -3.7), ("FESX1!", "sma20"): (19, 10.1),
             ("ES1!", "none"): (57, 31.6), ("ES1!", "sma20"): (25, 9.6),
             ("NQ1!", "none"): (28, 5.5), ("NQ1!", "sma20"): (15, 0.3)}
RISK_PCT = 0.01
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_markets_trades.csv"


def run(symbol, d, version, cost):
    """All trades, open ones included."""
    k = SCALE[symbol]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    if version == "none":
        masks = (("buy", None), ("sell", None))
    else:
        up = trend_up(symbol, d)
        masks = (("buy", up), ("sell", ~up))
    t = pd.concat([bt.backtest(d, True, False, direction=dr, entry_mask=m) for dr, m in masks], ignore_index=True)
    return t.sort_values("entry_time").reset_index(drop=True)


def capital(r, start):
    eq = start
    for x in r:
        eq += x * eq * RISK_PCT
    return eq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    for f in args.files:
        ingest(f)
    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    rows, totals = [], {"none": [], "sma20": []}
    for symbol, name in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        print(f"\n######## {name} ({symbol}) 15m jusqu'au {paris(d.index[-1] + pd.Timedelta(minutes=15))} (Paris)")
        for version in ("none", "sma20"):
            ref = run(symbol, d[d.index < REFERENCE_END], version, 1.0)
            ref = ref[ref.result != "open"]
            got = (len(ref), round(float(ref.net_r.sum()), 1))
            want = REFERENCE.get((symbol, version))
            status = "OK" if want == got else ("a fixer" if want is None else "DIFFERENT")
            print(f"  controle reference {version}: {got[0]} trades, {got[1]:+.1f}R -> {status}")
            t = run(symbol, d, version, 1.0)
            live = t[t.entry_time >= FREEZE_START]
            closed, still_open = live[live.result != "open"], live[live.result == "open"]
            r = closed.net_r.to_numpy()
            totals[version].append(r)
            t3 = run(symbol, d, version, 3.0)
            r3 = t3[(t3.entry_time >= FREEZE_START) & (t3.result != "open")].net_r.to_numpy()
            print(f"  {version:5s} depuis le {FREEZE_START}, cout 1pt-eq: {len(r)} trades clos, {(r > 0).sum()} gagnants, "
                  f"net {r.sum():+.2f}R, capital {capital(r, args.capital):,.0f} EUR | cout 3pt-eq: net {r3.sum():+.2f}R")
            for x in live.itertuples():
                side = "call" if x.take > x.entry else "put"
                end = "OUVERT" if x.result == "open" else f"{x.result} {paris(x.exit_time)} {x.net_r:+.2f}R"
                print(f"     {paris(x.entry_time)} {side:4s} entree {x.entry:.2f} stop {x.stop:.2f} cible {x.take:.2f} -> {end}")
                rows.append({"marche": name, "version": version, "sens": side, "entree_paris": paris(x.entry_time),
                             "entree": x.entry, "stop": round(x.stop, 2), "cible": round(x.take, 2),
                             "sortie_paris": "" if x.result == "open" else paris(x.exit_time),
                             "resultat": x.result, "net_r": None if x.result == "open" else round(x.net_r, 3)})
    print(f"\n######## Les 4 marches ensemble, cout 1pt-eq, depuis le {FREEZE_START}")
    for version, parts in totals.items():
        r = np.concatenate(parts) if parts else np.array([])
        print(f"  {version:5s}: {len(r)} trades clos, {(r > 0).sum()} gagnants, net {r.sum():+.2f}R")
    pd.DataFrame(rows, columns=["marche", "version", "sens", "entree_paris", "entree", "stop", "cible",
                                "sortie_paris", "resultat", "net_r"]).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
