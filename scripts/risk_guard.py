"""Risk guard-rails for the strategies tracked for real money, fixed on
2026-11-05 after the quantitative audit, at the user's request, BEFORE any
real trade. They apply to the MAIN strategy (sma20 live trades) as soon as
it is traded with money, and are shown every evening meanwhile.

  risk per trade   0.5 % to 1 % of the capital (1 % is about a quarter of
                   the Kelly fraction estimated by the audit: never more)
  daily stop       once the day's realised result reaches -3R, no new trade
                   that day (orders already open keep their stop)
  pause            if the live cumulative result falls 15R below its best
                   level, stop trading with money and review before any
                   restart (the backtest's worst drawdown was -27.5R over 5
                   months: -15R live is a signal, not a certainty)

Usage: python scripts/risk_guard.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

TRADES = Path(__file__).resolve().parent.parent / "data" / "backtests" / "frozen_15m_calls_trend_trades.csv"
DAILY_STOP, PAUSE = -3.0, -15.0


def main():
    t = pd.read_csv(TRADES)
    t = t[(t.version == "sma20") & (t.resultat != "open")].copy()
    t["day"] = t.sortie_paris.str[:5]
    t["order"] = pd.to_datetime("2026/" + t.sortie_paris.str[3:5] + "/" + t.sortie_paris.str[:2] + " "
                                + t.sortie_paris.str[6:], format="%Y/%m/%d %H:%M")
    t = t.sort_values("order")
    eq = t.net_r.cumsum().to_numpy()
    dd = eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]
    day = t.groupby("day", sort=False).net_r.sum()
    bad = day[day <= DAILY_STOP]
    print(f"Garde-fous (principale, suivi depuis le 28/10) : cumul {eq[-1] if len(eq) else 0:+.2f}R, "
          f"ecart au plus haut {dd[-1] if len(dd) else 0:+.2f}R (pause a {PAUSE:+.0f}R), pire ecart {dd.min() if len(dd) else 0:+.2f}R")
    print(f"  journees a {DAILY_STOP:+.0f}R ou pire (arret du jour) : "
          f"{', '.join(f'{d} {v:+.1f}R' for d, v in bad.items()) if len(bad) else 'aucune'}")
    if len(dd) and dd[-1] <= PAUSE:
        print("  PAUSE : ecart de -15R atteint, pas d'argent avant revision")


if __name__ == "__main__":
    main()
