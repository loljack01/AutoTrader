"""Exit variants test (scripts/exit_variants_test.py) in euros: every trade
risks a fixed 500 EUR (1R = 500 EUR, no compounding), calls and puts,
1m/5m/15m, costs 1pt and 3pt. Writes the full trade list to
data/backtests/exit_variants_trades_500eur.csv and prints a summary.

Usage: python scripts/exit_variants_euros.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from exit_variants_test import VARIANTS, set_rules

RISK_EUR = 500.0
OUT = Path(__file__).resolve().parent.parent / "data" / "backtests" / "exit_variants_trades_500eur.csv"


def main():
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for iv in ("1m", "5m", "15m"):
        d = bt.cache.closed_bars(bt.cache.load(bt.SYMBOL, iv), iv, now)
        for cost in (1.0, 3.0):
            set_rules(cost)
            for name, kwargs in VARIANTS.items():
                for direction in ("buy", "sell"):
                    t = bt.backtest(d, True, False, direction=direction, **kwargs)
                    t = t[t.result != "open"]
                    for r in t.itertuples():
                        rows.append({"unite": iv, "cout_pt": cost, "version": name,
                                     "sens": "call" if direction == "buy" else "put",
                                     "entree_paris": r.entry_time.tz_convert("Europe/Paris").strftime("%Y-%m-%d %H:%M"),
                                     "entree": r.entry, "stop": round(r.stop, 1), "cible": round(r.take, 1),
                                     "sortie_paris": r.exit_time.tz_convert("Europe/Paris").strftime("%Y-%m-%d %H:%M"),
                                     "resultat": r.result, "net_r": round(r.net_r, 3),
                                     "eur": round(r.net_r * RISK_EUR, 2)})
    x = pd.DataFrame(rows).sort_values(["unite", "cout_pt", "version", "entree_paris"])
    x.to_csv(OUT, index=False)
    print(f"{len(x)} trades -> {OUT.name} (1R = {RISK_EUR:.0f} EUR)\n")
    for (iv, cost, name), g in x.groupby(["unite", "cout_pt", "version"], sort=False):
        eq = g.eur.cumsum()
        dd = (eq - eq.cummax().clip(lower=0)).min()
        losing = (g.eur < 0).astype(int)
        streak = losing.groupby((losing != losing.shift()).cumsum()).cumsum().max()
        print(f"{iv:3s} {cost:.0f}pt {name:24s} n={len(g):3d} gagnants={(g.eur > 0).mean():4.0%} "
              f"total={g.eur.sum():+9,.0f} EUR  moy/trade={g.eur.mean():+6.0f}  meilleur={g.eur.max():+6.0f}  "
              f"pire={g.eur.min():+6.0f}  baisse max={dd:+8,.0f}  pertes d'affilee={streak}")


if __name__ == "__main__":
    main()
