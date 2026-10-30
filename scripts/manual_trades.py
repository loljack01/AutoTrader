"""Manual trades tracked outside the frozen strategies (FCE1!).

Each row of data/backtests/manual_trades.csv is one trade with fixed entry,
stop and target, decided by the user. It does not change any frozen version
and is reported separately. Exit rules match the backtest engine: the bars
after the entry bar are scanned, the stop is checked before the target in
the same bar, and the result is in R net of the round-trip cost.

Usage: python scripts/manual_trades.py [--capital 1000]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from data import cache

SYMBOL = "FCE1!"
FILE = Path(__file__).resolve().parent.parent / "data" / "backtests" / "manual_trades.csv"
RISK_PCT = 0.01


def evaluate(row, d, cost):
    side = 1 if row.side == "call" else -1
    risk = abs(row.entry - row.stop)
    after = d[d.index > row.entry_time]
    for ts, bar in after.iterrows():
        hit_stop = bar.Low <= row.stop if side == 1 else bar.High >= row.stop
        hit_take = bar.High >= row["take"] if side == 1 else bar.Low <= row["take"]
        if hit_stop:
            return "stop", ts, -(1.0 + cost / risk)
        if hit_take:
            return "take", ts, abs(row["take"] - row.entry) / risk - cost / risk
    latent = side * (d.Close.iloc[-1] - row.entry) / risk - cost / risk
    return "open", None, latent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capital", type=float, default=1000.0)
    args = parser.parse_args()

    trades = pd.read_csv(FILE)
    trades["entry_time"] = pd.to_datetime(trades.entry_time, utc=True)
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    for cost in (1.0, 3.0):
        closed_r = 0.0
        print(f"=== Trades manuels, cout {cost:.0f}pt ===")
        for _, t in trades.iterrows():
            d = cache.closed_bars(cache.load(SYMBOL, t.interval), t.interval, pd.Timestamp.now(tz="UTC"))
            result, exit_time, r = evaluate(t, d, cost)
            head = f"  {paris(t.entry_time)} {t.interval} {t.side} entree {t.entry:.1f} stop {t.stop:.1f} cible {t['take']:.1f}"
            if result == "open":
                print(f"{head} -> OUVERT, dernier {d.Close.iloc[-1]:.1f} ({paris(d.index[-1])}), latent {r:+.2f}R")
            else:
                closed_r += r
                print(f"{head} -> {result} {paris(exit_time)} {r:+.2f}R")
        print(f"  net clos {closed_r:+.2f}R, soit {closed_r * RISK_PCT * args.capital:+.0f} EUR sur {args.capital:,.0f} EUR a {RISK_PCT:.0%} de risque")


if __name__ == "__main__":
    main()
