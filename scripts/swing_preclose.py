"""Pre-close check of the swing strategy (frozen_swing_rsi2.py): the rule
enters and exits AT THE CLOSE, so the decision must be known a few minutes
before it. Computed with the current price as a stand-in for the close
(cache = daily bars up to yesterday, refreshed by the evening report):
  ENTRY   price > SMA200 and RSI(2) < 10 with today's price -> call to buy
          just before the close (5 positions max, lowest RSI(2) first)
  EXIT    an open position (data/backtests/frozen_swing_rsi2_trades.csv)
          whose price is > SMA5 with today's price -> sell before the close;
          also the 10th day after entry
  WATCH   RSI(2) between 10 and 20: may become a signal at the close
The stop uses yesterday's ATR(14) (today's range is not known yet). The
evening report remains the reference; a signal that flips between the
pre-close check and the close is followed as the evening report says.
Size 25 EUR of risk (phase 1: 0.25 % of 10 000 EUR since 06/11, capped by the
user's 500 EUR / 3 months tolerance); order >= 500 EUR.

Tooling corrections of 06/11/2026 (full audit, replay of 91 sessions: 11
false and 5 missed entries out of 41), the trade rule is unchanged:
  - an index is BUSY (no new entry) while any candidate of the frozen book
    is still running on it, taken or skipped (as frozen_swing_rsi2.py);
  - places freed by today's exits are given back before today's entries;
  - entries already made today (data/journal_swing.csv, entree = today, e.g.
    the European ones of 17h25 seen at 21h42) take their places;
  - "A CONFIRMER" when the price is within 0.3 % of a threshold (RSI(2) = 10,
    SMA5, SMA200): the close can flip the decision;
  - the US close time of the day in Paris is printed (21h00 during the
    weeks when the US and Europe are not on the same summer time).

Order size (user reminder of 07/11/2026: every order is 500 EUR minimum):
order = max(500 EUR, exposure / 1.6) at leverage exposure / order. When the
exposure for 25 EUR of risk is below 500 EUR (2.5 % of the signals since
2012, wide stops), the order stays at 500 EUR with the lowest leverage (~1):
the real risk is then up to ~34 EUR (median ~27 EUR).

Usage: python scripts/swing_preclose.py SYMBOL=PRICE [SYMBOL=PRICE ...]
  e.g. EURONEXT:PX1=8205.4 XETR:DAX=26325
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from test_swing_rsi2 import INDICES, MAX_DAYS, STOP_ATR, load

RISK_EUR, CAP, NEAR = 25.0, 5, 0.003
MIN_ORDER, MAX_LEV = 500.0, 1.6  # user's minimum order (0 EUR fees) and turbo leverage cap
ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "data" / "backtests" / "frozen_swing_rsi2_trades.csv"
JOURNAL = ROOT / "data" / "journal_swing.csv"


def rsi2(c):
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def rsi_with(closes, p):
    return rsi2(pd.concat([closes, pd.Series([p])], ignore_index=True)).iloc[-1]


def rsi_threshold_price(closes, level=10.0):
    """Price at which today's RSI(2) equals `level` (RSI is increasing in the price)."""
    lo, hi = closes.iloc[-1] * 0.8, closes.iloc[-1] * 1.2
    for _ in range(60):
        mid = (lo + hi) / 2
        if rsi_with(closes, mid) < level:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def read_csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def us_close_paris(today):
    ny = pd.Timestamp(f"{today.date()} 16:00", tz="America/New_York")
    return ny.tz_convert("Europe/Paris").strftime("%Hh%M")


def main():
    prices = dict(a.split("=") for a in sys.argv[1:])
    today = pd.Timestamp.now(tz="Europe/Paris").normalize()
    t = read_csv(TRADES)
    if len(t):
        busy_rows = t[t.sortie.isna()]
        opened = t[(t.pris == True) & t.sortie.isna()]  # noqa: E712
    else:
        busy_rows = opened = pd.DataFrame(columns=["marche", "entree", "prix_entree", "stop", "pris", "sortie"])
    j = read_csv(JOURNAL)
    today_fills = j[(j.entree.astype(str) == str(today.date()))] if len(j) and "entree" in j.columns else pd.DataFrame()
    names_busy = set(busy_rows.marche) | set(today_fills.marche if len(today_fills) else [])
    n_open = len(opened) + len([m for m in (today_fills.marche if len(today_fills) else []) if m not in set(opened.marche)])
    signals, lines, exits = [], [], 0
    for sym, p in prices.items():
        p = float(p)
        d = load(sym)
        d = d[d.index.tz_convert("Europe/Paris").normalize() < today]
        c = pd.concat([d.Close, pd.Series([p])], ignore_index=True)
        r, s200, s5 = rsi2(c).iloc[-1], c.rolling(200).mean().iloc[-1], c.rolling(5).mean().iloc[-1]
        name = INDICES[sym]
        atr = d.atr.iloc[-1]
        pos = opened[opened.marche == name]
        if len(pos):
            x = pos.iloc[0]
            days = int(np.busday_count(pd.Timestamp(x.entree).date(), today.date()))
            why = "cours > SMA5" if p > s5 else (f"{MAX_DAYS}e jour" if days >= MAX_DAYS else "")
            near = abs(p - s5) / p < NEAR
            if why:
                exits += 1
            lines.append(f"  {name}: position ouverte (entree {x.prix_entree}), cours {p:.2f}, SMA5 {s5:.2f} -> "
                         + (f"SORTIE avant la cloture ({why})" if why else "garder") + f", stop {x.stop}"
                         + (" -- A CONFIRMER (cours a moins de 0,3 % de la SMA5)" if near and why != f"{MAX_DAYS}e jour" else ""))
            continue
        if name in names_busy:
            if p > s200 and r < 10:
                lines.append(f"  {name}: signal RSI(2) {r:.1f} mais indice OCCUPE (trade du modele en cours, pris ou "
                             f"ignore, ou entree deja faite aujourd'hui) -> pas d'entree")
            continue
        p_rsi = rsi_threshold_price(d.Close)
        near = abs(p - p_rsi) / p < NEAR or abs(p - s200) / p < NEAR
        if p > s200 and r < 10:
            signals.append((r, name, p, atr, near, p_rsi, s200))
        elif p > s200 and r < 20:
            lines.append(f"  {name}: a surveiller, RSI(2) {r:.1f} (signal sous 10 a la cloture, soit un cours sous "
                         f"{p_rsi:.2f})" + (f" -- A CONFIRMER (SMA200 a {s200:.2f})" if abs(p - s200) / p < NEAR else ""))
        elif near and r < 20:
            lines.append(f"  {name}: RSI(2) {r:.1f}, cours a moins de 0,3 % de la SMA200 ({s200:.2f}) -- A CONFIRMER a la cloture")
    free = CAP - n_open + exits
    for k, (r, name, p, atr, near, p_rsi, s200) in enumerate(sorted(signals)):
        risk = STOP_ATR * atr
        expo = RISK_EUR * p / risk
        take = k < free
        order = max(MIN_ORDER, expo / MAX_LEV)
        size = (f"ordre {order:.0f} EUR au levier {expo / order:.1f}" if expo >= MIN_ORDER else
                f"ordre {MIN_ORDER:.0f} EUR minimum au levier le plus bas (~1) : exposition {MIN_ORDER:.0f} EUR, risque reel "
                f"~{RISK_EUR * MIN_ORDER / expo:.0f} EUR au lieu de {RISK_EUR:.0f}")
        lines.append(f"  {name}: ENTREE {'a prendre' if take else 'ignoree (5 positions)'} avant la cloture, RSI(2) {r:.1f}, "
                     f"cours {p:.2f}, stop {p - risk:.2f} ({risk / p:.1%}), exposition {expo:.0f} EUR pour {RISK_EUR:.0f} EUR "
                     f"de risque -> {size}" + (f" -- A CONFIRMER (seuil RSI a {p_rsi:.2f}, SMA200 {s200:.2f})" if near else ""))
    print(f"Swing, verification avant la cloture ({n_open} position(s) ouverte(s), {exits} sortie(s) du jour, "
          f"{max(free, 0)} place(s) libre(s)) ; cloture US aujourd'hui a {us_close_paris(today)} (heure de Paris) :")
    print("\n".join(lines) if lines else "  rien a faire")


if __name__ == "__main__":
    main()
