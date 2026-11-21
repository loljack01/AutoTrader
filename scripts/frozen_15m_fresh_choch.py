"""FROZEN on 2026-10-27: candidate "CHoCH frais" (fix A+B of
scripts/fresh_choch_test.py, kept by its pre-fixed rule on the 9 markets
other than CAC: +56.2R at 1pt and +30.0R at 3pt over 271 trades, against
+39.5/+14.0R for the frozen rules; 6 of 9 markets > 0; t=+1.06, i.e. NOT
statistically significant). Tracked live on the 10 index futures, next to
the frozen versions (which do not change).

Rules: the frozen 15m sweep + CHoCH set (stop = max(sweep extreme +/- 8pt,
2x ATR), target = nearest unswept opposite pool, net R:R >= 1.3, 4h
window, Paris session filter, one trade per sweep), calls and puts with no
trend filter, plus:
  A  entry only on the most recent CHoCH bar or at most 3 bars after it
  B  no entry once a close has gone back beyond the level that CHoCH broke
Stop margin and cost in CAC points times a FIXED factor per market (as in
scripts/frozen_15m_calls_trend.py). Cost 1pt CAC-equivalent, 3pt shown.

Scorecard: only trades entered on or after FREEZE_START count. Reference
(bars before 2026-10-27, 1pt-eq) checked each run.

Usage: python scripts/frozen_15m_fresh_choch.py [tool_result.json ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from other_markets_test import ingest

FREEZE_START = "2026-10-28"
REFERENCE_END = "2026-10-27"
VERSIONS = {"fix": {"choch_max_age": 3, "choch_invalidation": True}}
REFERENCE = {("FCE1!", "fix"): (36, 1.2), ("FDAX1!", "fix"): (35, 2.2), ("FESX1!", "fix"): (32, -6.0),
             ("ES1!", "fix"): (34, 31.2), ("NQ1!", "fix"): (16, 15.4), ("ICEEUR:Z1!", "fix"): (36, 29.7),
             ("FSMI1!", "fix"): (37, -9.5), ("YM1!", "fix"): (21, -10.0), ("RTY1!", "fix"): (28, 0.6),
             ("FIB1!", "fix"): (32, 2.6)}
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_fresh_choch_trades.csv"


def run(symbol, d, opts, cost):
    """All trades, open ones included."""
    k = MARKETS[symbol][1]
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    t = pd.concat([bt.backtest(d, True, False, direction=dr, **opts) for dr in ("buy", "sell")], ignore_index=True)
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
        for version, opts in VERSIONS.items():
            ref = run(symbol, d[d.index < REFERENCE_END], opts, 1.0)
            ref = ref[ref.result != "open"]
            got = (len(ref), round(float(ref.net_r.sum()), 1))
            want = REFERENCE.get((symbol, version))
            status = "OK" if want == got else ("a fixer" if want is None else "DIFFERENT")
            t = run(symbol, d, opts, 1.0)
            live = t[t.entry_time >= FREEZE_START]
            r = live[live.result != "open"].net_r.to_numpy()
            totals[version].append(r)
            t3 = run(symbol, d, opts, 3.0)
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
