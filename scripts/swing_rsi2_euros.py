"""The swing rule "Repli en tendance" (calls, frozen, see test_swing_rsi2.py)
translated into euros with index turbos. NOT a strategy test: the trades
are exactly those of the frozen rule on the 10 indices, 2012-2026; only
the turbo costs and sizing below are applied, with stated assumptions.

Assumptions (Boursorama-style index turbos, to be checked on the real
products before any money is used):
  capital 1000 EUR, risk 1 % = 10 EUR per trade (fixed, no compounding);
  stop = the rule's stop (2.5 ATR under the entry), so the position is
  10 EUR / (stop distance) per index point;
  turbo call with its barrier (knock-out) 1 ATR under the stop, i.e. 3.5
  ATR under the entry: leverage = entry / 3.5 ATR, money put in the turbo
  = 10 x 3.5 / 2.5 = 14 EUR per trade; if the index opens under the
  barrier the turbo is worth 0: loss capped at -14 EUR (-1.4R);
  spread: 0.02 % of the exposure per round trip (about 1.6 CAC points);
  financing: 4.5 % a year of the exposure, per calendar day held;
  brokerage: 0, 1 or 2 EUR per order (2 orders per trade) - the real fee
  of the user's account must be checked: at 10 EUR of risk it matters most.

Result (run on 2026-11-05, 1322 trades 2012-2026, 10 indices): with 0 EUR
brokerage +0.066R/trade, +878 EUR in 14.7 years (+60 EUR/year, +6 % of the
1000 EUR capital a year), worst drawdown -403 EUR, 12 positive years of 15;
with 1 EUR per order -0.134R/trade (-120 EUR/year), with 2 EUR -0.334R/trade:
at 10 EUR of risk per trade a fixed fee wipes out the edge. Break-even
brokerage is about 0.066 x 10 / 2 = 0.33 EUR per order; with 1 EUR per order
the risk per trade must be at least about 30 EUR (90 EUR for the fees to
take only a third of the edge). 8 trades of 1322 opened under the barrier.

Usage: python scripts/swing_rsi2_euros.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import test_swing_rsi2 as sw

RISK_EUR, SPREAD, FIN_YEAR, KO_R = 10.0, 0.0002, 0.045, -1.4
FEES = (0.0, 1.0, 2.0)
BOURSO = {"CAC 40", "DAX", "Euro Stoxx 50", "S&P 500", "Nasdaq 100", "Dow Jones"}


def main():
    rows = []
    for s, name in sw.INDICES.items():
        t = sw.run(sw.load(s), 1)
        rows.append(t.assign(market=name))
    t = pd.concat(rows, ignore_index=True).sort_values("exit").reset_index(drop=True)
    days = (t.exit - t.entry).dt.days
    gross = t.move_r.clip(lower=KO_R)
    var = (SPREAD + FIN_YEAR * days / 365) * t.cost_frac  # % costs in R (exposure = 10 EUR x cost_frac)
    years = (t.exit.max() - t.entry.min()).days / 365.25
    print(f"Swing repli en tendance (calls), {len(t)} trades, {t.entry.min():%m/%Y} -> {t.exit.max():%m/%Y} "
          f"({years:.1f} ans), detention moyenne {days.mean():.1f} jours calendaires")
    print(f"Hypotheses : risque {RISK_EUR:.0f} EUR/trade, mise dans le turbo 14 EUR, ecart {SPREAD:.2%}, "
          f"financement {FIN_YEAR:.1%}/an, perte max 1,4R si ouverture sous la barriere "
          f"({(t.move_r < KO_R).sum()} cas)")
    # capital immobilise : positions ouvertes en meme temps
    ev = pd.concat([pd.Series(1, index=t.entry), pd.Series(-1, index=t.exit)]).sort_index()
    print(f"Positions simultanees : max {int(ev.groupby(level=0).sum().cumsum().max())}, "
          f"soit au plus {14 * int(ev.groupby(level=0).sum().cumsum().max())} EUR places en turbos")
    for scope, m in (("10 indices", np.ones(len(t), bool)), ("6 indices a turbos courants", t.market.isin(BOURSO))):
        print(f"\n=== {scope} ({m.sum()} trades, {m.sum() / years:.0f} par an)")
        for fee in FEES:
            r = (gross - var - 2 * fee / RISK_EUR)[m]
            eur = r * RISK_EUR
            eq = eur.cumsum()
            dd = (eq - eq.cummax()).min()
            per_year = eur.groupby(t.exit[m].dt.year).sum()
            print(f"  courtage {fee:.0f} EUR/ordre : net {r.mean():+.3f}R/trade, total {eur.sum():+7.0f} EUR, "
                  f"{eur.sum() / years:+5.0f} EUR/an ({eur.sum() / years / 10:+.1f} % du capital/an), "
                  f"pire baisse {dd:+.0f} EUR, annees positives {(per_year > 0).sum()}/{len(per_year)}")
    r = gross - var
    last = t.exit >= t.exit.max() - pd.Timedelta(days=365)
    print(f"\n12 derniers mois (courtage 0) : {last.sum()} trades, {(r[last] * RISK_EUR).sum():+.0f} EUR")


if __name__ == "__main__":
    main()
