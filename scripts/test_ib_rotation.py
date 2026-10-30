"""Range days: fading a failed auction at the Initial Balance (Market
Profile), rules fixed on 2026-10-30 BEFORE running, at the user's request
("sell the top, buy the bottom" of days like 30/10). 13th idea tested in
two days; a pass only means live tracking without money.

Professional concepts used, nothing tuned on our data:
  Initial Balance (IB)  high and low of the first hour of the cash session,
                        9:00-10:00 Paris (four 15m bars 9:00, 9:15, 9:30,
                        9:45; all four required).
  Balance day filter    known at 9:00: the session opens (open of the 9:00
                        bar) INSIDE the previous day's range [low, high]
                        (previous closed daily bar of the data feed). An
                        open inside the prior range is the classic sign of
                        a balance / rotation day; an open outside, of a
                        trend day.
  Failed auction        after 10:00, price trades beyond the IB extreme
                        then a 15m bar CLOSES back inside the IB, before
                        two consecutive 15m closes beyond it (two closes
                        beyond = acceptance = trend: that side is void for
                        the day).

Trade (15m bars, from the 10:00 bar to the 17:15 bar Paris):
  put   failed auction above the IB high: entry at the close of the bar
        that closes back at or below the IB high; stop = highest high since
        price first traded above the IB high + 8pt x k; target = IB low.
  call  mirror below the IB low; target = IB high.
  Taken only if the net R:R (target and stop distances, cost included) is
  >= 1.3. One attempt per side per day (the first failed auction; if it is
  refused, or a trade of the other side is open, that side is done for the
  day). Never two positions at once. Exit: stop, target, or the close of
  the 17:15 bar (17:30, intraday only). A bar touching both stop and target
  counts as a stop. The entry bar is never checked for an exit.
Costs 1pt and 3pt CAC-equivalent (x fixed factor k of
frozen_15m_calls_trend.MARKETS: CAC 1, DAX 3.2397, Euro Stoxx 50 0.8004).
Data: 15m bars before REFERENCE_END (CAC from 22/05/2026, DAX and Euro
Stoxx 50 from 01/07/2026; 30/10 itself, which inspired the idea, is
excluded).

Decision rule (fixed before running), balance days (open inside the prior
range) only: worth live tracking WITHOUT money (frozen, from the next
session) only if ALL of:
  - CAC: at least 30 closed trades;
  - CAC: net > 0 at 3pt cost;
  - CAC: net > 0 at 1pt with every gain capped at +5R;
  - CAC: both halves of the period (split at the middle date) > 0 at 1pt;
  - DAX + Euro Stoxx 50 pooled (replication): net > 0 at 3pt-equivalent.
Otherwise REJETEE, no re-tuning (no other IB length, margin, target,
filter or exit is tried). All days and trend days (open outside) are
shown for information only.

Usage: python scripts/test_ib_rotation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import cache
from frozen_15m_calls_trend import MARKETS

REFERENCE_END = "2026-10-30"
SYMBOLS = ("FCE1!", "FDAX1!", "FESX1!")
MARGIN, MIN_NET_RR, MIN_TRADES = 8.0, 1.3, 30
IB_BARS = ("09:00", "09:15", "09:30", "09:45")


def day_trades(day, prev_hi, prev_lo, k, cost):
    """Trades of one Paris session; `day` = its 15m bars indexed by Paris time."""
    hm = day.index.strftime("%H:%M")
    ib = day[np.isin(hm, IB_BARS)]
    if len(ib) != 4:
        return None, []
    ibh, ibl = ib.High.max(), ib.Low.min()
    inside = prev_lo <= ib.Open.iloc[0] <= prev_hi
    after = day[(hm >= "10:00") & (hm <= "17:15")]
    c = cost * k
    state = {"sell": "idle", "buy": "idle"}
    ext, beyond = {}, {"sell": 0, "buy": 0}
    pos, trades = None, []
    for ts, b in after.iterrows():
        last = ts.strftime("%H:%M") == "17:15" or ts == after.index[-1]
        if pos is not None:
            s = pos["side"]
            hit_stop = b.High >= pos["stop"] if s == "sell" else b.Low <= pos["stop"]
            hit_take = b.Low <= pos["take"] if s == "sell" else b.High >= pos["take"]
            exit_px, res = None, None
            if hit_stop:
                exit_px, res = pos["stop"], "stop"
            elif hit_take:
                exit_px, res = pos["take"], "take"
            elif last:
                exit_px, res = b.Close, "eod"
            if res:
                sign = -1 if s == "sell" else 1
                trades.append({**pos, "exit_time": ts, "result": res,
                               "net_r": (sign * (exit_px - pos["entry"]) - c) / pos["risk"]})
                pos = None
        for s in ("sell", "buy"):
            if state[s] in ("done", "void"):
                continue
            level = ibh if s == "sell" else ibl
            outside_now = b.High > level if s == "sell" else b.Low < level
            if state[s] == "idle" and outside_now:
                state[s], ext[s] = "outside", (b.High if s == "sell" else b.Low)
            if state[s] != "outside":
                continue
            ext[s] = max(ext[s], b.High) if s == "sell" else min(ext[s], b.Low)
            closed_beyond = b.Close > level if s == "sell" else b.Close < level
            if closed_beyond:
                beyond[s] += 1
                if beyond[s] >= 2:
                    state[s] = "void"
                continue
            state[s] = "done"
            if pos is not None or last:
                continue
            entry = b.Close
            stop = ext[s] + MARGIN * k if s == "sell" else ext[s] - MARGIN * k
            take = ibl if s == "sell" else ibh
            risk, reward = abs(stop - entry), abs(entry - take)
            if risk <= 0 or (entry - take) * (1 if s == "sell" else -1) <= 0:
                continue
            if (reward - c) / (risk + c) < MIN_NET_RR:
                continue
            pos = {"side": "put" if s == "sell" else "call", "entry_time": ts, "entry": entry,
                   "stop": stop, "take": take, "risk": risk, "ibh": ibh, "ibl": ibl}
    return inside, trades


def run(symbol, cost, end=REFERENCE_END):
    now = pd.Timestamp.now(tz="UTC")
    k = MARKETS[symbol][1]
    d = cache.closed_bars(cache.load(symbol, "15m"), "15m", now)
    d = d[d.index < end]
    d.index = d.index.tz_convert("Europe/Paris")
    daily = cache.closed_bars(cache.load(symbol, "1D"), "1D", now)
    ddate = pd.Index(daily.index.tz_convert("Europe/Paris").date)
    rows = []
    for date, day in d.groupby(d.index.date):
        prev = daily[ddate < date]
        if prev.empty:
            continue
        inside, trades = day_trades(day, prev.High.iloc[-1], prev.Low.iloc[-1], k, cost)
        if inside is None:
            continue
        for t in trades:
            rows.append({**t, "date": date, "inside": inside})
        if not trades:
            rows.append({"date": date, "inside": inside, "net_r": np.nan})
    return pd.DataFrame(rows)


def line(label, t):
    t = t.dropna(subset=["net_r"])
    r = t.net_r.to_numpy()
    if not len(r):
        return f"  {label:34s} 0 trade"
    return (f"  {label:34s} {len(r):3d} trades, {(r > 0).mean():4.0%} gagnants, net {r.sum():+6.1f}R, "
            f"plafond 5R {np.minimum(r, 5).sum():+6.1f}R | calls {t[t.side == 'call'].net_r.sum():+.1f}R "
            f"({(t.side == 'call').sum()}), puts {t[t.side == 'put'].net_r.sum():+.1f}R ({(t.side == 'put').sum()}) | "
            f"sorties cible {(t.result == 'take').sum()}, stop {(t.result == 'stop').sum()}, 17h30 {(t.result == 'eod').sum()}")


def main():
    res = {}
    for s in SYMBOLS:
        r1, r3 = run(s, 1.0), run(s, 3.0)
        res[s] = (r1, r3)
        days = r1.drop_duplicates("date")
        print(f"{MARKETS[s][0]} : {len(days)} seances ({days.date.min()} -> {days.date.max()}), "
              f"ouverture dans le range de la veille {days.inside.mean():.0%}")
        print(line("tous les jours (info), 1pt", r1))
        print(line("ouverture hors range (info), 1pt", r1[~r1.inside.astype(bool)]))
        print(line("ouverture dans le range, 1pt", r1[r1.inside.astype(bool)]))
        print(line("ouverture dans le range, 3pt", r3[r3.inside.astype(bool)]))

    c1 = res["FCE1!"][0]
    c1 = c1[c1.inside.astype(bool)].dropna(subset=["net_r"])
    c3 = res["FCE1!"][1]
    c3 = c3[c3.inside.astype(bool)].dropna(subset=["net_r"])
    r = c1.net_r.to_numpy()
    dates = sorted(res["FCE1!"][0].date.unique())
    mid = dates[len(dates) // 2]
    h1, h2 = c1[c1.date < mid].net_r.sum(), c1[c1.date >= mid].net_r.sum()
    rep = pd.concat([res[s][1][res[s][1].inside.astype(bool)] for s in ("FDAX1!", "FESX1!")]).net_r.sum()
    cap = np.minimum(r, 5).sum()
    print(f"\nCAC, jours d'equilibre : moities (coupure {mid}) {h1:+.1f}R / {h2:+.1f}R | "
          f"DAX + Euro Stoxx 50 a 3pt-eq {rep:+.1f}R")
    for x in c1.sort_values("entry_time").itertuples():
        print(f"     {x.entry_time:%d/%m %H:%M} {x.side:4s} IB {x.ibl:.1f}-{x.ibh:.1f} entree {x.entry:.1f} "
              f"stop {x.stop:.1f} cible {x.take:.1f} -> {x.result} {x.exit_time:%H:%M} {x.net_r:+.2f}R")
    ok = len(r) >= MIN_TRADES and c3.net_r.sum() > 0 and cap > 0 and h1 > 0 and h2 > 0 and rep > 0
    print(f"\nRegle fixee avant : enchere ratee a l'Initial Balance {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETEE'}")


if __name__ == "__main__":
    main()
