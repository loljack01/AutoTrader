"""Live paper watch of the main strategy's turbo-executable form (variant D of
frozen_15m_variants.py, unchanged: entries 8:00-21:30 Paris, exit at 21:45 at the latest)
on FCE1! only, WITHOUT money (user's choice of 16/11/2026). Tooling only: no rule is changed
and the frozen scorecards are not affected.

Each run ingests the given TradingView tool-result files (FCE1! 15m), recomputes variant D on
the closed 15m bars with the 3-point cost (the cost at which D is judged) and prints only what
is new since the last run: entries of the day and exits, with the size of a 500 EUR order at
the turbo leverage of the CAC 40 (~2.8). The announced events are kept in a state file so that
each one is printed once.

Usage: python3 -W ignore scripts/live_fce1_turbo.py --state STATE.json [tool_result.json ...]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_variants import run

D_KW = {"entry_hours": (8, 21.5), "session_exit": 21.75}
ORDER, LEVERAGE = 500.0, 2.8


def day_extremes(now):
    """Running high / low of the day (from 8:00 and from the 9:00 cash open, forming bar included) and of the
    previous session, for display only: the variant's rules do not use them."""
    all_bars = bt.cache.load("FCE1!", "15m")
    all_bars = all_bars[all_bars.index <= now]
    p = all_bars.index.tz_convert("Europe/Paris")
    today = now.tz_convert("Europe/Paris").date()
    hhmm = lambda ts: ts.tz_convert("Europe/Paris").strftime("%Hh%M")
    out = []
    for label, m in (("depuis 8h", (p.date == today)), ("depuis 9h (cash)", (p.date == today) & (p.hour >= 9))):
        x = all_bars[m]
        if len(x):
            out.append(f"{label} : haut {x.High.max():.1f} ({hhmm(x.High.idxmax())}), bas {x.Low.min():.1f} ({hhmm(x.Low.idxmin())})")
    prev = sorted(set(d for d in p.date if d < today))
    if prev:
        y = all_bars[p.date == prev[-1]]
        out.append(f"veille : haut {y.High.max():.1f}, bas {y.Low.min():.1f}")
    return "Extremes : " + " | ".join(out) if out else "Extremes : pas encore de bougie aujourd'hui"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    for f in args.files:
        j = json.load(open(f))
        bars = j["bars"]
        if isinstance(bars, dict):
            bars = [dict(zip(bars.keys(), row)) for row in zip(*bars.values())]
        bt.cache.ingest(j["symbol"], j["interval"], bars)

    now = pd.Timestamp.now(tz="UTC")
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    d = bt.cache.closed_bars(bt.cache.load("FCE1!", "15m"), "15m", now)
    today = now.tz_convert("Europe/Paris").date()
    t = run("FCE1!", d, 3.0, **D_KW)
    t = t[(t.entry_time.dt.tz_convert("Europe/Paris").dt.date == today) | (t.result == "open")]

    path = Path(args.state)
    seen = set(json.loads(path.read_text())) if path.exists() else set()
    out = []
    for x in t.sort_values("entry_time").itertuples():
        side = "CALL" if x.take > x.entry else "PUT"
        key = f"{x.entry_time.isoformat()}|{side}"
        risk_pct = abs(x.entry - x.stop) / x.entry
        if key + "|entree" not in seen:
            seen.add(key + "|entree")
            out.append(f"ENTREE {side} (sans argent) : bougie close a {paris(x.entry_time + pd.Timedelta(minutes=15))}, "
                       f"entree {x.entry:.1f}, stop {x.stop:.1f} ({risk_pct:.2%}), cible {x.take:.1f} "
                       f"({abs(x.take - x.entry) / abs(x.entry - x.stop):.1f}R) ; ordre de {ORDER:.0f} EUR au levier ~{LEVERAGE} : "
                       f"perte au stop ~{ORDER * LEVERAGE * risk_pct:.1f} EUR ; sortie au plus tard a 21h45")
        if x.result != "open" and key + "|sortie" not in seen:
            seen.add(key + "|sortie")
            why = {"stop": "stop touche", "take": "cible touchee", "eod": "sortie de fin de journee (21h45)"}.get(x.result, x.result)
            out.append(f"SORTIE {side} entre a {x.entry:.1f} : {why} a {paris(x.exit_time)}, "
                       f"{x.net_r:+.2f}R soit {x.net_r * ORDER * LEVERAGE * risk_pct:+.1f} EUR (frais de 3 pts compris)")
    path.write_text(json.dumps(sorted(seen)))
    last = d.index[-1] + pd.Timedelta(minutes=15)
    opened = t[t.result == "open"]
    state = ("position ouverte : " + ", ".join(f"{'CALL' if x.take > x.entry else 'PUT'} a {x.entry:.1f} (stop {x.stop:.1f}, "
                                               f"cible {x.take:.1f})" for x in opened.itertuples())) if len(opened) else "aucune position"
    print(f"FCE1 version turbo, derniere bougie close a {paris(last)} (Paris), dernier cours {d.Close.iloc[-1]:.1f} ; {state}")
    print(day_extremes(now))
    print("\n".join(out) if out else "rien de nouveau")


if __name__ == "__main__":
    main()
