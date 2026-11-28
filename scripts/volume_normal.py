"""Volume of FCE1! bars against the normal of their Paris slot, following the most traded contract
(tooling for the reading rules of rule 31 of docs/regles_execution.md; user's decision of 20/11/2026).

Why: CAC 40 futures expire every month on the third Friday at 16:00. During the expiry week the trading
moves to the next month while TradingView's FCE1! stays on the expiring contract until the expiry day, so
the FCE1! volume collapses (19/11/2026: 13 260 contracts on the November contract against 32 519 on
December, the "historically low volume" read that day was the roll, not a lack of sellers).

What this tool does, for display only (no strategy rule uses volume, rule 31):
- the normal of a slot is the median of the same Paris slot over the previous sessions, EXCLUDING every
  expiry week (Monday to the expiry Friday): their FCE1! volume is either shrinking (roll) or swollen by
  the final settlement, so they are not a normal;
- the volume of a bar in an expiry week is the expiring contract (FCE1!) PLUS the next contract when its
  bars are in the cache (fetch it as EURONEXT:FCE<month code><year>, e.g. EURONEXT:FCEZ2026, and ingest it
  under that name). If FCE1! has already rolled (same prices as the next contract), it is not added twice.
  Without the next contract's bars, the bar is flagged "lecture non fiable";
- the rank is the share of the reference sessions with a lower volume; abnormal only at the 90th rank or
  above (strong) or the 10th or below (weak); the excluded minutes of rule 31.3 (9h00 auction, 15h30-15h45
  US open, 17h30-17h35 closing auction, and on an expiry day 15h40-16h00, the final settlement window)
  are shown but never read as signals.

Usage: python3 -W ignore scripts/volume_normal.py --date 2026-11-19 [--interval 15m] [--start 16:00]
       [--end 22:00] [--sessions 60]
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from data import cache

MONTH_CODES = "FGHJKMNQUVXZ"
FRONT = "FCE1!"


def expiry(year, month):
    """Third Friday of the month (CAC 40 futures expiry, Euronext)."""
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(4 - first.weekday()) % 7 + 14)


def front_expiry(day):
    """Expiry of the contract that FCE1! follows on `day` (it rolls on the expiry day itself at the latest)."""
    e = expiry(day.year, day.month)
    if day <= e:
        return e
    y, m = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return expiry(y, m)


def in_expiry_week(day):
    """Monday to Friday of the week that ends with the front contract's expiry."""
    return 0 <= (front_expiry(day) - day).days <= 4


def next_contract(day):
    """TradingView ticker of the contract after the front one on `day`, e.g. EURONEXT:FCEZ2026 in Nov 2026."""
    e = front_expiry(day)
    y, m = (e.year + 1, 1) if e.month == 12 else (e.year, e.month + 1)
    return f"EURONEXT:FCE{MONTH_CODES[m - 1]}{y}"


def excluded_minute(ts):
    """Rule 31.3 minutes (Paris time), plus the final settlement window on an expiry day."""
    hm = ts.hour * 60 + ts.minute
    if hm == 9 * 60 or 15 * 60 + 30 <= hm < 15 * 60 + 45 or 17 * 60 + 30 <= hm <= 17 * 60 + 35:
        return True
    return ts.date() == front_expiry(ts.date()) and 15 * 60 + 40 <= hm < 16 * 60


def _paris(df):
    return df.index.tz_convert("Europe/Paris")


def combined_volume(interval, day):
    """Bars of FCE1! on `day` with the volume of the most traded contract: in an expiry week, FCE1! plus the
    next contract if its bars are cached and differ from FCE1! (not rolled yet). Returns (frame, note)."""
    front = cache.load(FRONT, interval)
    front = front[_paris(front).date == day].copy()
    front["Volume_front"] = front.Volume
    front["Volume_next"] = 0.0
    front["Close_next"] = float("nan")
    if not in_expiry_week(day):
        return front, ""
    sym = next_contract(day)
    nxt = cache.load(sym, interval)
    nxt = nxt[_paris(nxt).date == day] if len(nxt) else nxt
    if not len(nxt):
        return front, (f"semaine d'echeance : volume du seul contrat sortant, LECTURE NON FIABLE "
                       f"(recuperer {sym} en {interval} et l'ingerer sous ce nom)")
    common = front.index.intersection(nxt.index)
    if len(common) and (front.Close[common] - nxt.Close[common]).abs().median() < 1.0:
        return front, f"semaine d'echeance : FCE1! suit deja {sym} (meme prix), volume non double"
    front.loc[common, "Volume_next"] = nxt.Volume[common].astype(float)
    front.loc[common, "Close_next"] = nxt.Close[common]
    front["Volume"] = front.Volume_front + front.Volume_next
    return front, f"semaine d'echeance : volume = contrat sortant + {sym}"


def reference(interval, before_day, sessions=60):
    """FCE1! bars of the `sessions` previous sessions outside expiry weeks, with a Paris 'slot' column."""
    allb = cache.load(FRONT, interval)
    days = sorted({d for d in _paris(allb).date if d < before_day and not in_expiry_week(d)})[-sessions:]
    ref = allb[pd.Index(_paris(allb).date).isin(days)].copy()
    ref["slot"] = _paris(ref).strftime("%H:%M")
    return ref, len(days)


def rank_bar(ref, ts, volume):
    """(median, rank in %, number of sessions) of `volume` against the same slot in `ref`."""
    hist = ref.Volume[ref.slot == ts.strftime("%H:%M")]
    if len(hist) < 10:
        return float("nan"), float("nan"), len(hist)
    return float(hist.median()), float((hist < volume).mean() * 100), len(hist)


def verdict(ts, rank, n):
    if excluded_minute(ts):
        return "minute exclue (regle 31.3)"
    if n < 10:
        return "historique trop court"
    if rank >= 90:
        return "ANORMALEMENT FORT"
    if rank <= 10:
        return "ANORMALEMENT FAIBLE"
    return "normal"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--interval", default="15m")
    ap.add_argument("--start", default="08:00")
    ap.add_argument("--end", default="22:00")
    ap.add_argument("--sessions", type=int, default=60)
    a = ap.parse_args()
    day = dt.date.fromisoformat(a.date)
    bars, note = combined_volume(a.interval, day)
    ref, nref = reference(a.interval, day, a.sessions)
    print(f"FCE1! {a.interval} du {day:%d/%m/%Y} ; normale = mediane du meme creneau sur {nref} seances hors semaines "
          f"d'echeance (prochaine echeance {front_expiry(day):%d/%m}, contrat suivant {next_contract(day)})")
    if note:
        print(note)
    p = _paris(bars)
    hm = p.strftime("%H:%M")
    bars = bars[(hm >= a.start) & (hm < a.end)]
    for ts, r in zip(_paris(bars), bars.itertuples()):
        med, rk, n = rank_bar(ref, ts, r.Volume)
        split = f" (sortant {r.Volume_front:.0f} + suivant {r.Volume_next:.0f})" if r.Volume_next else ""
        nxt = f" | suivant {r.Close_next:.1f}" if r.Close_next == r.Close_next else ""
        print(f"{ts:%H:%M} O {r.Open:.1f} H {r.High:.1f} B {r.Low:.1f} C {r.Close:.1f}{nxt} | vol {r.Volume:.0f}{split} "
              f"normale {med:.0f} rang {rk:.0f} : {verdict(ts, rk, n)}")


if __name__ == "__main__":
    main()
