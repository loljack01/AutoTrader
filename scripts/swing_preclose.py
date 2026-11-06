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

RISK_EUR, CAP = 25.0, 5
TRADES = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_swing_rsi2_trades.csv"


def rsi2(c):
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def main():
    prices = dict(a.split("=") for a in sys.argv[1:])
    today = pd.Timestamp.now(tz="Europe/Paris").normalize()
    try:
        t = pd.read_csv(TRADES)
        opened = t[(t.pris == True) & t.sortie.isna()]  # noqa: E712
    except Exception:
        opened = pd.DataFrame(columns=["marche", "entree", "prix_entree", "stop"])
    names = {v: k for k, v in INDICES.items()}
    signals, lines = [], []
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
            lines.append(f"  {name}: position ouverte (entree {x.prix_entree}), cours {p:.2f}, SMA5 {s5:.2f} -> "
                         + (f"SORTIE avant la cloture ({why})" if why else "garder") + f", stop {x.stop}")
        elif p > s200 and r < 10:
            signals.append((r, name, p, atr))
        elif p > s200 and r < 20:
            lines.append(f"  {name}: a surveiller, RSI(2) {r:.1f} (signal sous 10 a la cloture)")
    free = CAP - len(opened)
    for k, (r, name, p, atr) in enumerate(sorted(signals)):
        risk = STOP_ATR * atr
        expo = RISK_EUR * p / risk
        take = k < free
        lines.append(f"  {name}: ENTREE {'a prendre' if take else 'ignoree (5 positions)'} avant la cloture, RSI(2) {r:.1f}, "
                     f"cours {p:.2f}, stop {p - risk:.2f} ({risk / p:.1%}), exposition {expo:.0f} EUR, levier pour 500 EUR "
                     f"{expo / 500:.1f}")
    print(f"Swing, verification avant la cloture ({len(opened)} position(s) ouverte(s), {max(free, 0)} place(s) libre(s)) :")
    print("\n".join(lines) if lines else "  rien a faire")


if __name__ == "__main__":
    main()
