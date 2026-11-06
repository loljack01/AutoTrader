"""TEST 4 of docs/tests_figes_2026-11-06.md, frozen on 2026-11-06 (before
any computation on 15m data), at the user's request: rejection of the
previous day's high / low (P2, chart analysis expert). FORWARD tracking only,
without money, from Monday 2026-11-09; no computation on earlier 15m data
(earlier days are used only to read the previous day's levels).

Markets: FCE1!, FDAX1!, FESX1! in 15m (cost factors k: 1, 3.2397, 0.8004).
PDH / PDL: highest high / lowest low of the 15m bars of 9:00-17:30 Paris of
the previous session (bars starting 9:00 to 17:15). ATRd = ATR14 of the
future's daily bars (EWM, as the swing) up to the previous session.
PUT: a 15m bar starting between 9:15 and 15:15 Paris with High > PDH,
Close < PDH and High - PDH <= 0.3 x ATRd. Entry at the bar's close. Stop =
bar High + 0.1 x ATRd. Target = (PDH + PDL) / 2. Trade only if the net R:R
(reward - cost) / (risk + cost), cost = 3 points x k, is >= 1.3. Exit at the
target, at the stop (the stop first if both in the same bar) or at the close
of the 17:15-17:30 bar.
CALL: mirror on the PDL, only if the previous daily close is above SMA20.
At most 1 trade per side, per day and per market (the first signal).
Net R = (points won - cost) / risk, at 3 points x k (1 point x k shown for
information).

Verdict at 150 closed trades: net R > 0 at 3 points AND t (trades summed per
day) >= 2.24 -> candidate; otherwise the family of reactions to levels is
closed. Abandon as soon as the cumulative net R (exit order) reaches -15R.
Multiple-testing budget: 4 tests (tests 1-4); tests 1-3 used on 06/11.

Usage: python scripts/frozen_p2_prev_day_reject.py (reads data/cache: 15m
and 1D of the three futures, refreshed by the evening report)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache

START = pd.Timestamp("2026-11-09").date()
MARKETS = {"FCE1!": ("CAC 40", 1.0), "FDAX1!": ("DAX", 3.2397), "FESX1!": ("Euro Stoxx 50", 0.8004)}
COST_PTS, INFO_COST_PTS = 3.0, 1.0
MIN_RR, MAX_POKE, STOP_ATR = 1.3, 0.3, 0.1
VERDICT_N, T_MIN, BRAKE = 150, 2.24, -15.0
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_p2_trades.csv"


def daily_context(sym):
    d = cache.load(sym, "1D")
    d.index = pd.to_datetime(d.index, utc=True)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    c = d.Close
    tr = pd.concat([d.High - d.Low, (d.High - c.shift()).abs(), (d.Low - c.shift()).abs()], axis=1).max(axis=1)
    out = pd.DataFrame({"atr": tr.ewm(alpha=1 / 14, adjust=False).mean(), "close": c, "sma20": c.rolling(20).mean()})
    out.index = d.index.tz_convert("Europe/Paris").date
    return out


def day_trades(sym, day, bars, pdh, pdl, ctx):
    k = MARKETS[sym][1]
    atr, up = ctx.atr, ctx.close > ctx.sma20
    mid = (pdh + pdl) / 2
    hour = bars.index.hour + bars.index.minute / 60
    rows = []
    for side in ("put", "call"):
        if side == "call" and not up:
            continue
        for i in np.flatnonzero((hour >= 9.25) & (hour <= 15.25)):
            b = bars.iloc[i]
            if side == "put":
                ok = b.High > pdh and b.Close < pdh and b.High - pdh <= MAX_POKE * atr
                entry, stop, target = b.Close, b.High + STOP_ATR * atr, mid
            else:
                ok = b.Low < pdl and b.Close > pdl and pdl - b.Low <= MAX_POKE * atr
                entry, stop, target = b.Close, b.Low - STOP_ATR * atr, mid
            if not ok:
                continue
            s = 1 if side == "call" else -1
            risk, reward, cost = s * (entry - stop), s * (target - entry), COST_PTS * k
            if not (risk > 0 and reward > 0 and (reward - cost) / (risk + cost) >= MIN_RR):
                continue
            res, px, t_exit = "open", None, None
            for j in range(i + 1, len(bars)):
                x = bars.iloc[j]
                if (s == -1 and x.High >= stop) or (s == 1 and x.Low <= stop):
                    res, px, t_exit = "stop", stop, bars.index[j]
                    break
                if (s == -1 and x.Low <= target) or (s == 1 and x.High >= target):
                    res, px, t_exit = "take", target, bars.index[j]
                    break
                if hour[j] >= 17.25:
                    res, px, t_exit = "fin 17h30", x.Close, bars.index[j]
                    break
            pts = None if px is None else s * (px - entry)
            rows.append({"marche": MARKETS[sym][0], "jour": day, "sens": side,
                         "entree_paris": bars.index[i].strftime("%d/%m %H:%M"), "entree": round(entry, 2),
                         "stop": round(stop, 2), "cible": round(target, 2), "pdh": pdh, "pdl": pdl,
                         "resultat": res, "sortie_paris": None if t_exit is None else t_exit.strftime("%d/%m %H:%M"),
                         "prix_sortie": None if px is None else round(px, 2),
                         "net_r_3pt": None if pts is None else round((pts - COST_PTS * k) / risk, 3),
                         "net_r_1pt": None if pts is None else round((pts - INFO_COST_PTS * k) / risk, 3),
                         "exit_ts": t_exit})
            break  # first signal of this side only
    return rows


def main():
    now = pd.Timestamp.now(tz="UTC")
    rows, levels = [], []
    for sym in MARKETS:
        b = cache.closed_bars(cache.load(sym, "15m"), "15m", now)
        b.index = pd.to_datetime(b.index, utc=True).tz_convert("Europe/Paris")
        b = b[~b.index.duplicated(keep="last")].sort_index()
        hour = b.index.hour + b.index.minute / 60
        cash = b[(hour >= 9) & (hour < 17.5)]
        days = sorted(set(cash.index.date))
        ctx = daily_context(sym)
        lb = cash[cash.index.date == days[-1]]
        levels.append((MARKETS[sym][0], days[-1], float(lb.High.max()), float(lb.Low.min())))
        for prev, day in zip(days[:-1], days[1:]):
            pb = cash[cash.index.date == prev]
            pdh, pdl = float(pb.High.max()), float(pb.Low.min())
            if day < START:
                continue
            c_prev = ctx[ctx.index < day]
            if len(c_prev) < 20:
                continue
            rows += day_trades(sym, day, b[b.index.date == day], pdh, pdl, c_prev.iloc[-1])
    t = pd.DataFrame(rows)
    if len(t):
        t.drop(columns="exit_ts").to_csv(OUT, index=False)
    else:
        pd.DataFrame(columns=["marche", "jour", "sens", "entree_paris", "entree", "stop", "cible", "pdh", "pdl",
                              "resultat", "sortie_paris", "prix_sortie", "net_r_3pt", "net_r_1pt"]).to_csv(OUT, index=False)
    print(f"P2 rejet du plus haut / plus bas de la veille (suivi sans argent depuis le {START:%d/%m/%Y})")
    for name, day, hi, lo in levels:
        print(f"  {name:14s} seance du {day:%d/%m} (9h-17h30, provisoire si en cours) -> niveaux de la seance "
              f"suivante : PDH {hi:.2f}, PDL {lo:.2f}, milieu {(hi + lo) / 2:.2f}")
    if not len(t):
        print(f"  aucun trade depuis le {START:%d/%m} ; verdict a {VERDICT_N} trades clos")
        return
    for x in t.itertuples():
        end = "OUVERT" if x.resultat == "open" else f"{x.resultat} {x.sortie_paris} {x.net_r_3pt:+.2f}R"
        print(f"     {x.marche:14s} {x.entree_paris} {x.sens:4s} entree {x.entree:.2f} stop {x.stop:.2f} "
              f"cible {x.cible:.2f} -> {end}")
    cl = t[t.resultat != "open"].sort_values("exit_ts")
    cum = cl.net_r_3pt.cumsum().to_numpy()
    daily = cl.groupby("jour").net_r_3pt.sum()
    tday = daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily))) if len(daily) > 1 else float("nan")
    print(f"  {len(cl)} trades clos, {(cl.net_r_3pt > 0).sum()} gagnants, net {cl.net_r_3pt.sum():+.2f}R a 3 pts "
          f"({cl.net_r_1pt.sum():+.2f}R a 1 pt), t par jour {tday:+.2f}")
    if len(cum) and cum.min() <= BRAKE:
        print(f"  ABANDON : cumul {cum.min():+.1f}R <= {BRAKE:+.0f}R, la famille des reactions aux niveaux est fermee")
    elif len(cl) >= VERDICT_N:
        ok = cl.net_r_3pt.sum() > 0 and tday >= T_MIN
        print(f"  Verdict a {VERDICT_N} trades : {'CANDIDAT' if ok else 'REJETE, famille fermee'}")
    else:
        print(f"  Verdict a {VERDICT_N} trades clos (encore {VERDICT_N - len(cl)}), abandon a {BRAKE:+.0f}R")


if __name__ == "__main__":
    main()
