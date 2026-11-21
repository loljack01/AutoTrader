"""Live watch for new sweep + CHoCH signals on FCE1!, calls and puts, 1m, 5m
and 15m (1m on its last 3000 bars only), no trend filter, frozen rule set (2x ATR stop floor, 8pt margin, 4h
window, net R:R >= 1.3, Paris session filter). Alerts only: the frozen
scorecards are not affected.

Each run ingests the given TradingView tool-result files into the cache,
then checks every closed bar not checked yet (from the last bar of each
interval already closed at the watch start): a bar
is a signal if the engine, started on that bar, opens a trade on it, and
no earlier bar already triggered on the same sweep (one trade per sweep).

Usage: python scripts/live_signals.py --state STATE.json [tool_result.json ...]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import backtest_liquidity_sweep_buy as bt

INTERVALS = {"1m": pd.Timedelta(minutes=1), "5m": pd.Timedelta(minutes=5), "15m": pd.Timedelta(minutes=15)}
KEEP = {"1m": 3000}  # recent bars only on 1m, to keep each check fast


def set_rules():
    bt.ROUND_TRIP_COST = 1.0
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()

    for f in args.files:
        j = json.load(open(f))
        bt.cache.ingest(bt.SYMBOL, j["interval"], j["bars"])

    now = pd.Timestamp.now(tz="UTC")
    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {"start": now.isoformat(), "checked": {}}
    start = pd.Timestamp(state["start"])
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%H:%M")
    set_rules()

    found = []
    for iv, bar in INTERVALS.items():
        d = bt.cache.closed_bars(bt.cache.load(bt.SYMBOL, iv), iv, now)
        if iv in KEEP:
            d = d.iloc[-KEEP[iv]:]
        for direction in ("buy", "sell"):
            key = f"{iv}-{direction}"
            # from the last bar already closed at the watch start, so a signal closing just before it is not missed
            first_ts = start - 2 * bar
            last = pd.Timestamp(state["checked"].get(key, (first_ts - bar).isoformat()))
            for ts in d.index[(d.index > last) & (d.index >= first_ts)]:
                t = bt.backtest(d, True, False, since=ts.tz_convert(None), direction=direction)
                t = t[t.entry_time == ts]
                for _, r in t.iterrows():
                    # one trade per sweep: only the first bar that triggers on this sweep is a new signal
                    first = bt.backtest(d, True, False, since=r.sweep_time.tz_convert(None), direction=direction)
                    if first[first.sweep_time == r.sweep_time].entry_time.min() != ts:
                        continue
                    side = "CALL" if direction == "buy" else "PUT"
                    found.append(f"{side} {iv} a {paris(ts + bar)} : entree {r.entry:.1f}, stop {r.stop:.1f}, "
                                 f"cible {r['take']:.1f} (balayage {paris(r.sweep_time)})")
                state["checked"][key] = ts.isoformat()
        print(f"{iv}: derniere barre close {paris(d.index[-1] + bar)}, cloture {d.Close.iloc[-1]:.1f}")

    state_path.write_text(json.dumps(state))
    print("\n".join(found) if found else "Aucun nouveau signal")


if __name__ == "__main__":
    main()
