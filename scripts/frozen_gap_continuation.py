"""FROZEN on 2026-10-27: candidate "l'ecart continue", tracked live on the 10
index futures WITHOUT money. It is a POST-HOC idea: the pre-registered
gap-fill test (scripts/gap_fill_test.py) was rejected, losing -44.1R over
378 trades at 1pt (t=-3.54), so the exact opposite trade looked good on
the same history (+27.0R over 378 trades at 1pt, 6 of 10 markets > 0).
That history therefore proves nothing about it; only trades entered on
or after FREEZE_START count.

Rules (the exact mirror of scripts/gap_fill_test.py, which must not
change), 15m bars, each market's cash session (Europe 9:00 Paris, US 9:30
New York):
  reference   R = previous official daily close (1D bar close)
  entry       at the close C0 of the first 15m bar of the cash session,
              AWAY from R (sell if C0 < R, buy if C0 > R), only if
              0.25 x daily ATR(14) <= |C0 - R| <= 1.0 x daily ATR(14)
              and that first bar has not already touched R
  stop        R
  target      same distance on the other side: C0 +/- |C0 - R| (1:1)
  time exit   close of the bar ending 3h after the cash open
A bar that touches both stop and target counts as a stop. A stop is
filled at the stop, or at the open if the bar opens beyond it. One trade
per market per day. Cost 1pt CAC-equivalent (3pt shown as a check),
fixed per-market factors from scripts/frozen_15m_calls_trend.py.

Verdict rule (fixed now, before any live trade): once at least 100 live
trades are closed on the 10 markets together, the candidate is confirmed
only if its pooled net R is > 0 at 1pt AND 3pt and its t-stat at 1pt is
>= 1.65. Otherwise it is dropped.

Reference (bars before 2026-10-27, 1pt-eq), checked each run.

Usage: python scripts/frozen_gap_continuation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from gap_fill_test import daily_ref, local_clock, session
from other_markets_test import tstat

FREEZE_START = "2026-10-28"
REFERENCE_END = "2026-10-27"
MIN_LIVE_TRADES = 100
REFERENCE = {"FCE1!": (45, -0.8), "FDAX1!": (41, 7.1), "FESX1!": (39, 5.8), "ES1!": (35, 3.7), "NQ1!": (31, 2.8),
             "ICEEUR:Z1!": (33, -1.5), "FSMI1!": (37, -4.5), "YM1!": (26, -1.5), "RTY1!": (34, 6.4), "FIB1!": (57, 9.5)}
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_gap_continuation_trades.csv"


def trades(symbol, d, cost):
    """All trades; result 'open' while the 3h window is not complete."""
    _, open_h, _ = session(symbol)
    h, date = local_clock(symbol, d)
    ref, datr = daily_ref(symbol, d)
    rows = []
    for i in np.flatnonzero(np.isclose(h, open_h + 0.25)):
        r, a, c0 = ref[i], datr[i], d.Close.iat[i]
        if np.isnan(r) or np.isnan(a):
            continue
        gap = c0 - r
        side = 1 if gap > 0 else -1
        touched = d.Low.iat[i] <= r if side == 1 else d.High.iat[i] >= r
        if not (0.25 * a <= abs(gap) <= 1.0 * a) or touched:
            continue
        dist = abs(gap)
        stop, take = c0 - side * dist, c0 + side * dist
        window = np.flatnonzero((date == date[i]) & (h <= open_h + 3.0) & (np.arange(len(d)) > i))
        complete = len(window) and np.isclose(h[window[-1]], open_h + 3.0)
        row = {"entry_time": d.index[i], "side": side, "entry": c0, "stop": stop, "take": take}
        px, result, j = None, "open", None
        for j in window:  # same fills as gap_fill_test.walk, but knowing which exit happened
            if (side == 1 and d.Low.iat[j] <= stop) or (side == -1 and d.High.iat[j] >= stop):
                beyond = (d.Open.iat[j] <= stop) if side == 1 else (d.Open.iat[j] >= stop)
                px, result = (d.Open.iat[j] if beyond else stop), "stop"
                break
            if (side == 1 and d.High.iat[j] >= take) or (side == -1 and d.Low.iat[j] <= take):
                px, result = take, "target"
                break
        else:
            if complete:
                j = window[-1]
                px, result = d.Close.iat[j], "time"
        if result == "open":
            rows.append({**row, "result": "open", "exit_time": pd.NaT, "net_r": np.nan})
            continue
        rows.append({**row, "result": result, "exit_time": d.index[j] + pd.Timedelta(minutes=15),
                     "net_r": side * (px - c0) / dist - cost / dist})
    return pd.DataFrame(rows, columns=["entry_time", "side", "entry", "stop", "take", "result", "exit_time", "net_r"])


def main():
    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    rows, live1, live3 = [], [], []
    for symbol, (name, k) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        ref = trades(symbol, d[d.index < REFERENCE_END], 1.0 * k)
        ref = ref[ref.result != "open"]
        got = (len(ref), round(float(ref.net_r.sum()), 1))
        want = REFERENCE.get(symbol)
        status = "OK" if want == got else ("a fixer" if want is None else "DIFFERENT")
        t = trades(symbol, d, 1.0 * k)
        live = t[t.entry_time >= FREEZE_START]
        r = live[live.result != "open"].net_r.to_numpy()
        live1.append(r)
        t3 = trades(symbol, d, 3.0 * k)
        live3.append(t3[(t3.entry_time >= FREEZE_START) & (t3.result != "open")].net_r.to_numpy())
        print(f"{name:14s} controle reference {got[0]} trades {got[1]:+.1f}R -> {status} | depuis le {FREEZE_START}: "
              f"{len(r)} trades clos, {(r > 0).sum()} gagnants, net {r.sum():+.2f}R")
        for x in live.itertuples():
            side = "achat" if x.side == 1 else "vente"
            end = "OUVERT" if x.result == "open" else f"{x.result} {paris(x.exit_time)} {x.net_r:+.2f}R"
            print(f"     {paris(x.entry_time)} {side:5s} entree {x.entry:.2f} stop {x.stop:.2f} cible {x.take:.2f} -> {end}")
            rows.append({"marche": name, "sens": side, "entree_paris": paris(x.entry_time), "entree": x.entry,
                         "stop": round(x.stop, 2), "cible": round(x.take, 2),
                         "sortie_paris": "" if x.result == "open" else paris(x.exit_time),
                         "resultat": x.result, "net_r": None if x.result == "open" else round(x.net_r, 3)})
    r1, r3 = np.concatenate(live1), np.concatenate(live3)
    print(f"\n10 marches ensemble depuis le {FREEZE_START}: {len(r1)} trades clos, {(r1 > 0).sum()} gagnants, "
          f"net {r1.sum():+.2f}R (3pt-eq {r3.sum():+.2f}R)")
    if len(r1) >= MIN_LIVE_TRADES:
        ok = r1.sum() > 0 and r3.sum() > 0 and tstat(r1) >= 1.65
        print(f"Verdict ({len(r1)} trades, t={tstat(r1):+.2f}): {'CONFIRMEE' if ok else 'ABANDONNEE'}")
    else:
        print(f"Verdict a {MIN_LIVE_TRADES} trades clos (encore {MIN_LIVE_TRADES - len(r1)})")
    pd.DataFrame(rows, columns=["marche", "sens", "entree_paris", "entree", "stop", "cible", "sortie_paris",
                                "resultat", "net_r"]).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
