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


AUCTION_SLOTS = {"09h00": "ouverture du cash", "17h30": "fixing de cloture"}


def volume_line(d, sessions=60):
    """Volume of the last closed 15m bar against the same Paris slot over the previous sessions (median and
    rank), for display only: the variant's rules do not use it. Comparing with the previous bars instead would
    flag the scheduled surges (9h00 cash open, 15h30 US open, 17h30 closing auction) as signals (see the
    analysis of 16/11/2026). A bar is called abnormal only above the 90th or below the 10th percentile of its
    slot; the 9h00 and 17h30 bars are auctions and are not read as signals at all."""
    allb = bt.cache.load("FCE1!", "15m")
    p = allb.index.tz_convert("Europe/Paris")
    last = d.index[-1].tz_convert("Europe/Paris")
    slot = last.strftime("%Hh%M")
    hist = allb.Volume[(p.strftime("%Hh%M") == slot) & (p.date < last.date())].tail(sessions)
    v = float(d.Volume.iloc[-1])
    if len(hist) < 10:
        return f"Volume : bougie de {slot} {v:.0f} contrats ; historique de ce creneau trop court ({len(hist)} seances)"
    med = float(hist.median())
    rank = (hist < v).mean() * 100
    if slot in AUCTION_SLOTS:
        verdict = f"{AUCTION_SLOTS[slot]} : volume toujours fort a cette heure, a ne pas lire comme un signal"
    elif rank >= 90:
        verdict = "ANORMALEMENT FORT pour cette heure"
    elif rank <= 10:
        verdict = "ANORMALEMENT FAIBLE pour cette heure"
    else:
        verdict = "normal pour cette heure"
    return (f"Volume : bougie de {slot} {v:.0f} contrats ; normale du creneau {med:.0f} (mediane de {len(hist)} seances) ; "
            f"{v / med:.1f}x la normale, {rank:.0f}e centile : {verdict}")


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
    # The engine flags the LAST bar of its input as the last bar of the day (end of data). Live, that bar is
    # mid-session, so the engine would refuse an entry on the newest closed bar and close any open position
    # "eod" on it (bug seen on 16/11 at 13h00). A flat sentinel bar at the last close is appended so that the
    # newest real bar is judged like any intraday bar; the sentinel itself cannot touch a stop or target that
    # the real bar did not already touch. Entries on the sentinel are dropped, exits on it mean "still open".
    sentinel = d.index[-1] + pd.Timedelta(minutes=15)
    c = float(d.Close.iloc[-1])
    flat = pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 0}, index=[sentinel])
    t = run("FCE1!", pd.concat([d, flat[d.columns]]), 3.0, **D_KW)
    t = t[t.entry_time < sentinel].copy()
    still_open = t.exit_time == sentinel
    t.loc[still_open, "result"] = "open"
    t.loc[still_open, ["exit_time", "net_r"]] = [pd.NaT, float("nan")]
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
    print(volume_line(d))
    print("\n".join(out) if out else "rien de nouveau")


if __name__ == "__main__":
    main()
