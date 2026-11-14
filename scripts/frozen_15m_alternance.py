"""Test 11, FROZEN on 2026-11-14 BEFORE any forward trade, with the user's agreement ("Ok"),
after the audit of 14/11 (docs/audit_ordres_multiples_2026-11-14.md, sections 5 and 6): the
user's ALTERNATION rule on the main strategy's signals, tracked forward WITHOUT money, with and
without the calls trend filter side by side.

Rule (user, 14/11): on one index there can never be two calls or two puts in a row; after a
call the next trade is a put, after a put a call. Version kept from the audit, "A+R":
  - a signal is taken only if its direction is opposite to the last trade taken on that index;
  - when it is taken while the previous trade is still open, that trade is closed at the close
    of the signal bar (one position at a time on the index);
  - if a call and a put are possible on the same bar, only the one with the most recent sweep.
Everything else is the main strategy (frozen_15m_calls_trend.py): same engine, 10 markets,
factors, costs, 4h window. The rule is applied from the start of each market's history, so the
state at the start of the tracking (last direction, open trade) is the one the rule gives.

Versions, fixed now:
  E1  A+R WITH the filter (calls only above the 20-day SMA, puts always)
  E2  A+R WITHOUT the filter (calls and puts always allowed)
each also in its turbo-executable form (entries 8:00-21:30 Paris, exit at 21:45 at the latest),
shown as "E1 turbo" / "E2 turbo". Reference: the main strategy over the same period.

Tracked FORWARD ONLY: trades entered from Sunday 2026-11-15 23:00 Paris count (markets are
closed between the freeze and that time). The audit's figures are never used to judge.

Verdict for E1 and for E2, each when it has 100 closed forward trades (cut-off = the exit time
of its 100th trade; the main strategy and the turbo form are counted up to the same cut-off).
The version becomes the candidate that replaces the main strategy (after a discussion with the
user) only if ALL hold over that period:
  1. its net R with every gain capped at +5R (1pt) is above the main strategy's;
  2. its net R at 3pt-equivalent is > 0;
  3. its turbo-executable form has a net R at 3pt-equivalent > 0.
The filter is judged by E1 against E2: if both pass, E2 is preferred only if it is above E1 on
BOTH the capped net R (1pt) and the net R at 3pt, compared at E2's cut-off; otherwise E1.
Emergency brake: a version whose capped cumulative R (1pt) is <= -15R at any time is dropped.
A kept version does not go to real money: it would start its own sequential test (05/11 rule)
from zero. The main strategy is NOT changed.

Check at each run: the simulator (audit/2026-11-14) without alternation must give the engine's
trades for the main strategy at 1pt on the 10 markets.

Usage: python3 -W ignore scripts/frozen_15m_alternance.py (reads data/cache; run after
frozen_15m_calls_trend.py, which ingests the day's files)
"""

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "audit" / "2026-11-14"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from alternance import simulate_joint
from frozen_15m_calls_trend import MARKETS
from ma_grid_test import trend_up
from ordres_multiples import D_KW, prepare, set_engine

FORWARD_START = pd.Timestamp("2026-11-15 22:00", tz="UTC")  # Sunday 23:00 Paris
VERDICT_TRADES = 100
BRAKE = -15.0
# name: (alternate, reverse, calls filter, turbo-executable form)
VERSIONS = {"principale": (None, False, True, False), "E1 avec filtre": ("strict", True, True, False),
            "E1 turbo": ("strict", True, True, True), "E2 sans filtre": ("strict", True, False, False),
            "E2 turbo": ("strict", True, False, True)}
OUT = ROOT / "data" / "backtests" / "frozen_15m_alternance_trades.csv"


def job(symbol):
    now = pd.Timestamp.now(tz="UTC")
    d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
    k = MARKETS[symbol][1]
    up = trend_up(symbol, d, "SMA", 20)
    P = {1: prepare(d, 1), -1: prepare(d, -1)}
    out = {}
    for name, (alt, rev, filt, turbo) in VERSIONS.items():
        for cost in (1.0, 3.0):
            t = simulate_joint(P, up if filt else None, k, cost, alt, rev, **(D_KW if turbo else {}))
            if name == "principale" and cost == 1.0:
                set_engine(k, cost)
                ref = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up).assign(side=1),
                                 bt.backtest(d, True, False, direction="sell").assign(side=-1)])
                ref = ref.sort_values(["entry_time", "side"]).reset_index(drop=True)
                when = lambda x, c: pd.to_datetime(x[c], utc=True).fillna(pd.Timestamp(0, tz="UTC")).to_numpy()
                out["_ok"] = bool(len(ref) == len(t) and (ref.side.to_numpy() == t.side.to_numpy()).all()
                                  and (ref.result.to_numpy() == t.result.to_numpy()).all()
                                  and all((when(ref, c) == when(t, c)).all() for c in ("entry_time", "exit_time"))
                                  and np.allclose(ref.net_r.to_numpy(float), t.net_r.to_numpy(float), equal_nan=True))
            out[name, cost] = t[t.entry_time >= FORWARD_START].assign(marche=MARKETS[symbol][0])  # forward only
    return symbol, out


def main():
    paris = lambda ts: ts.tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    fw, ok = {}, True
    with ProcessPoolExecutor(max_workers=4) as pool:
        for symbol, out in pool.map(job, list(MARKETS)):
            ok &= out.pop("_ok")
            for key, t in out.items():
                fw.setdefault(key, []).append(t)
    fw = {key: pd.concat(v, ignore_index=True) for key, v in fw.items()}
    print(f"Test 11 - alternance (apres un call un put, apres un put un call), suivi en avant depuis le "
          f"{paris(FORWARD_START)} (Paris)")
    print(f"  controle : simulateur sans alternance identique au moteur sur les 10 marches -> {'OK' if ok else 'DIFFERENT'}")
    closed = lambda t: t[t.result != "open"].sort_values("exit_time")
    capped = lambda t: np.minimum(t.net_r.to_numpy(float), 5.0)

    def line(name, cutoff=None):
        c1, c3 = closed(fw[name, 1.0]), closed(fw[name, 3.0])
        if cutoff is not None:
            c1, c3 = c1[c1.exit_time <= cutoff], c3[c3.exit_time <= cutoff]
        return len(c1), float(c1.net_r.sum()), float(c3.net_r.sum()), float(capped(c1).sum())

    rows = []
    for name in VERSIONS:
        n, net, net3, cap = line(name)
        t1 = fw[name, 1.0]
        cum = capped(closed(t1)).cumsum()
        brake = f" | FREIN atteint ({cum.min():+.1f}R) : version abandonnee" if len(cum) and cum.min() <= BRAKE and name != "principale" else ""
        print(f"  {name:15s} : {n} trades clos, net {net:+.2f}R, 3pt {net3:+.2f}R, plafond 5R {cap:+.2f}R, "
              f"{int((t1.result == 'open').sum())} ouverts{brake}")
        for x in t1.sort_values("entry_time").itertuples():
            end = "OUVERT" if x.result == "open" else f"{x.result} {paris(x.exit_time)} {x.net_r:+.2f}R"
            if name != "principale":
                print(f"     {x.marche:14s} {paris(x.entry_time)} {'call' if x.side == 1 else 'put ':4s} entree {x.entry:.2f} "
                      f"stop {x.stop:.2f} cible {x.take:.2f} -> {end}")
            rows.append({"version": name, "marche": x.marche, "sens": "call" if x.side == 1 else "put",
                         "entree_paris": paris(x.entry_time), "entree": x.entry, "stop": round(x.stop, 2),
                         "cible": round(x.take, 2), "resultat": x.result,
                         "sortie_paris": None if x.result == "open" else paris(x.exit_time),
                         "net_r": None if x.result == "open" else round(x.net_r, 3)})
    pd.DataFrame(rows, columns=["version", "marche", "sens", "entree_paris", "entree", "stop", "cible", "resultat",
                                "sortie_paris", "net_r"]).to_csv(OUT, index=False)

    passed = {}
    for v in ("E1", "E2"):
        name = next(k for k in VERSIONS if k.startswith(v) and "turbo" not in k)
        c = closed(fw[name, 1.0])
        if len(c) < VERDICT_TRADES:
            print(f"{name} : verdict a {VERDICT_TRADES} trades clos (encore {VERDICT_TRADES - len(c)})")
            continue
        cutoff = c.exit_time.iloc[VERDICT_TRADES - 1]
        n, net, net3, cap = line(name, cutoff)
        _, _, _, cap_ref = line("principale", cutoff)
        _, _, turbo3, _ = line(f"{v} turbo", cutoff)
        cum = capped(c[c.exit_time <= cutoff]).cumsum()
        good = cap > cap_ref and net3 > 0 and turbo3 > 0 and cum.min() > BRAKE
        passed[v] = (good, cutoff)
        print(f"VERDICT {name} (coupure {paris(cutoff)}) : plafond 5R {cap:+.2f}R contre {cap_ref:+.2f}R pour la principale, "
              f"3pt {net3:+.2f}R, forme turbo a 3pt {turbo3:+.2f}R -> {'PASSE' if good else 'ne passe pas'}")
    if len(passed) == 2:
        if passed["E1"][0] and passed["E2"][0]:
            cut = passed["E2"][1]
            _, _, e1_3, e1_cap = line("E1 avec filtre", cut)
            _, _, e2_3, e2_cap = line("E2 sans filtre", cut)
            print("  -> nouvelle candidate : " + ("E2 sans filtre" if e2_cap > e1_cap and e2_3 > e1_3 else "E1 avec filtre")
                  + " (la principale n'est pas modifiee ; test sequentiel a zero avant tout argent reel)")
        elif passed["E1"][0] or passed["E2"][0]:
            print("  -> nouvelle candidate : " + ("E1 avec filtre" if passed["E1"][0] else "E2 sans filtre")
                  + " (la principale n'est pas modifiee ; test sequentiel a zero avant tout argent reel)")
        else:
            print("  -> aucune version ne passe ; l'alternance est abandonnee")


if __name__ == "__main__":
    main()
