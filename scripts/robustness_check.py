"""Robustness of the tracked versions to a few outsized winners, fixed on
2026-10-28 BEFORE running. Diagnostic only: no frozen version changes.

Trigger: the +39.3R FTSE 100 put of 26/08 (held 6 weeks) carries most of
the frozen 15m result on 10 markets. Are the tracked versions still
positive without their best trades?

For each tracked family, on its history (trades entered before
2026-10-28, closed, cost 1pt CAC-equivalent):
  brut          the frozen result
  sans top 1/3  the best 1 / 3 trades removed
  plafond 5R    every gain capped at +5R
  coupe 48h     a trade still open 48h after entry is closed at the close
                of the last bar before entry + 48h (no overnight carry
                beyond two days, closer to how turbos are held)
Verdict (fixed now): a family is "robuste" only if its net R stays > 0
in all three stressed versions: sans top 3, plafond 5R, coupe 48h.
Otherwise "fragile" (its history depends on a few exceptional trades).

Families: CAC puts 5m; CAC 15m sma20 / ema20 / none; 4 markets none /
sma20; candidate calls-with-trend sma20 / sma10 (10 markets); candidate
CHoCH frais (10 markets). "L'ecart continue" is left out (1:1 trades
closed within 3h, no outsized winner possible).

Usage: python scripts/robustness_check.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
import frozen_15m_calls_trend as ct
import frozen_15m_daily as cac15
import frozen_15m_fresh_choch as fc
import frozen_15m_markets as fm
import frozen_puts_5m as p5

END = "2026-10-28"
CUT = pd.Timedelta(hours=48)


def cut_48h(d, t, cost):
    """net R if the trade is closed at the last bar close before entry + 48h."""
    out = []
    close = d.Close
    for x in t.itertuples():
        if x.exit_time - x.entry_time <= CUT:
            out.append(x.net_r)
            continue
        side = 1 if x.take > x.entry else -1
        risk = abs(x.entry - x.stop)
        px = close[close.index <= x.entry_time + CUT].iloc[-1]
        out.append(side * (px - x.entry) / risk - cost / risk)
    return np.array(out)


def closed(t):
    return t[(t.result.isin(["stop", "take"])) & (t.entry_time < END)].reset_index(drop=True)


def families(now):
    """{family: [(d, trades, cost), ...]} at 1pt CAC-equivalent."""
    load = lambda s, iv: bt.cache.closed_bars(bt.cache.load(s, iv), iv, now)
    fam = {}
    d5 = load("FCE1!", "5m")
    fam["CAC puts 5m"] = [(d5, closed(p5.run(d5, 1.0)), 1.0)]
    d15 = load("FCE1!", "15m")
    for kind in ("sma20", "ema20", "none"):
        fam[f"CAC 15m {kind}"] = [(d15, closed(cac15.run(d15, kind, 1.0)), 1.0)]
    for version in ("none", "sma20"):
        fam[f"4 marches {version}"] = [(load(s, "15m"), closed(fm.run(s, load(s, "15m"), version, 1.0)), fm.SCALE[s])
                                       for s in fm.SCALE]
    for version, n in ct.VERSIONS.items():
        fam[f"calls tendance {version}"] = [(load(s, "15m"), closed(ct.run(s, load(s, "15m"), n, 1.0)), k)
                                            for s, (_, k) in ct.MARKETS.items()]
    fam["CHoCH frais"] = [(load(s, "15m"), closed(fc.run(s, load(s, "15m"), fc.VERSIONS["fix"], 1.0)), k)
                          for s, (_, k) in ct.MARKETS.items()]
    return fam


def main():
    now = pd.Timestamp.now(tz="UTC")
    print(f"{'famille':24s} {'n':>4s} {'brut':>7s} {'sans top1':>9s} {'sans top3':>9s} {'plaf. 5R':>8s} {'coupe 48h':>9s}  "
          f"meilleur trade   verdict")
    for name, parts in families(now).items():
        r = np.concatenate([t.net_r.to_numpy() for _, t, _ in parts])
        c48 = np.concatenate([cut_48h(d, t, cost) for d, t, cost in parts])
        s = np.sort(r)[::-1]
        top1, top3 = s[1:].sum(), s[3:].sum()
        cap = np.minimum(r, 5.0).sum()
        ok = top3 > 0 and cap > 0 and c48.sum() > 0
        print(f"{name:24s} {len(r):4d} {r.sum():+7.1f} {top1:+9.1f} {top3:+9.1f} {cap:+8.1f} {c48.sum():+9.1f}  "
              f"{s[0] if len(s) else 0:+6.1f}R         {'ROBUSTE' if ok else 'fragile'}")


if __name__ == "__main__":
    main()
