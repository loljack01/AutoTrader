"""Monthly sector rotation (sector momentum) on the 11 S&P 500 sectors, rules
fixed on 2026-11-03 BEFORE fetching the data, at the user's request (18th
idea; a SWING idea, separate from the intraday CAC work). Origin: on 03/11
energy, health care and consumer staples led the S&P 500 over 3 months;
the question is whether "buy the strongest sectors of the last 3 months"
has worked as a rule, not whether it worked this time.

Data: daily closes of the S&P 500 sector PRICE indices from TradingView
(dividends excluded for every series, including the benchmarks), saved
in data/sectors/<code>.csv, turned into month-end closes. Universe:
  S5INFT tech, SPN energy, SPF financials, S5HLTH health care,
  S5COND consumer discretionary, S5CONS consumer staples, S5INDU
  industrials, S5UTIL utilities, S5MATR materials, S5REAS real estate,
  S5TELS communication services; benchmark SPX (S&P 500).
A sector is eligible at a month end once it has 4 month-end closes (3-month
return available). Period: from the first month end with at least 9
eligible sectors to the end of October 2026 (November 2026, still running,
is excluded).

Rule: at each month end, rank the eligible sectors by their 3-month price
return (close / close 3 month ends earlier - 1); hold the top 3, equally
weighted, during the next month; rebalance at the next month end. Cost:
c x (number of the 3 positions replaced / 3) charged each month (round trip
on the replaced share), c = 0.2 % (ETF-like) and 0.5 % (turbo-like spread);
the first month pays c in full.

Comparisons: "panier" = all eligible sectors equally weighted each month
(same universe, no selection, no cost: isolates the selection effect);
S&P 500 (price index); "hasard" = 2000 simulations (seed 0) picking 3
eligible sectors at random each month, same cost rule.

Decision rule (fixed before fetching the data): worth paper tracking as a
separate swing strategy WITHOUT money only if ALL of:
  - at least 120 monthly periods;
  - annualised return above the "panier" at c = 0.5 %;
  - return above the "panier" in BOTH halves of the period (split at the
    middle month) at c = 0.2 %;
  - final cumulative return above the 95th percentile of "hasard" at
    c = 0.2 %;
  - maximum drawdown (month-end) no worse than the S&P 500's by more than
    5 percentage points.
Otherwise REJETE, no re-tuning (no other look-back, number of sectors,
holding period or filter is tried).

Usage: python scripts/test_sector_momentum.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

DIR = Path(__file__).resolve().parent.parent / "data" / "sectors"
SECTORS = ["S5INFT", "SPN", "SPF", "S5HLTH", "S5COND", "S5CONS", "S5INDU", "S5UTIL", "S5MATR", "S5REAS", "S5TELS"]
NAMES = {"S5INFT": "Technologie", "SPN": "Energie", "SPF": "Finance", "S5HLTH": "Sante",
         "S5COND": "Conso. discretionnaire", "S5CONS": "Conso. de base", "S5INDU": "Industrie",
         "S5UTIL": "Services publics", "S5MATR": "Materiaux", "S5REAS": "Immobilier", "S5TELS": "Communication"}
END = "2026-10-31"
TOP, LOOK, MIN_SECTORS, MIN_MONTHS = 3, 3, 9, 120


def monthly(code):
    d = pd.read_csv(DIR / f"{code}.csv", parse_dates=["date"]).set_index("date").close
    return d.resample("ME").last().dropna()


def stats(r):
    eq = (1 + r).cumprod()
    years = len(r) / 12
    dd = (eq / eq.cummax() - 1).min()
    return eq.iloc[-1] - 1, eq.iloc[-1] ** (1 / years) - 1, dd


def strategy(px, cost, start, rng=None):
    """Monthly returns of the top-3 (or random-3 if rng) rotation, signals
    from the month end `start` on (momentum computed on the full history)."""
    ret = px.pct_change()
    mom = px / px.shift(LOOK) - 1
    out, held = [], set()
    for i in range(px.index.get_loc(start), len(px) - 1):
        elig = mom.iloc[i].dropna()
        if rng is None:
            pick = set(elig.sort_values(ascending=False).index[:TOP])
        else:
            pick = set(rng.choice(elig.index.to_numpy(), TOP, replace=False))
        changed = TOP if not held else len(pick - held)
        held = pick
        r = ret.iloc[i + 1][list(pick)].mean() - cost * changed / TOP
        out.append((px.index[i + 1], r, ",".join(sorted(pick))))
    return pd.DataFrame(out, columns=["month", "r", "held"]).set_index("month")


def main():
    px = pd.concat({c: monthly(c) for c in SECTORS}, axis=1)
    spx = monthly("SPX")
    px = px[px.index <= END]
    elig = (px / px.shift(LOOK) - 1).notna().sum(axis=1)
    start = elig[elig >= MIN_SECTORS].index[0]
    s2, s5 = strategy(px, 0.002, start), strategy(px, 0.005, start)
    ret = px.pct_change()
    mom_ok = (px / px.shift(LOOK) - 1).notna().shift(1)
    basket = ret.where(mom_ok).mean(axis=1)
    basket = basket[basket.index > start]
    bench = spx.reindex(px.index).pct_change()
    bench = bench[bench.index > start]
    n = len(s2)
    print(f"Periode : signal fin {start:%m/%Y} -> {px.index[-1]:%m/%Y}, {n} mois")
    rows = {"rotation top 3, cout 0,2 %": s2.r, "rotation top 3, cout 0,5 %": s5.r,
            "panier des secteurs": basket, "S&P 500": bench}
    for k, r in rows.items():
        tot, ann, dd = stats(r)
        print(f"  {k:28s} total {tot:+8.1%} | annualise {ann:+6.2%} | pire baisse {dd:+6.1%}")
    rng = np.random.default_rng(0)
    finals = np.array([(1 + strategy(px, 0.002, start, rng).r).prod() - 1 for _ in range(2000)])
    p95 = np.percentile(finals, 95)
    half = n // 2
    ex1 = (1 + s2.r.iloc[:half]).prod() - (1 + basket.iloc[:half]).prod()
    ex2 = (1 + s2.r.iloc[half:]).prod() - (1 + basket.iloc[half:]).prod()
    tot2, ann2, dd2 = stats(s2.r)
    tot5, ann5, dd5 = stats(s5.r)
    totb, annb, ddb = stats(basket)
    tots, anns, dds = stats(bench)
    print(f"\nMoities (coupure {s2.index[half]:%m/%Y}) : ecart sur le panier {ex1:+.1%} / {ex2:+.1%} (cout 0,2 %)")
    print(f"Hasard (3 secteurs tires au sort chaque mois) : mediane {np.median(finals):+.1%}, 95e centile {p95:+.1%} "
          f"contre {tot2:+.1%} pour la rotation")
    last12 = s2.r.iloc[-12:]
    print(f"12 derniers mois : rotation {(1 + last12).prod() - 1:+.1%}, panier {(1 + basket.iloc[-12:]).prod() - 1:+.1%}, "
          f"S&P 500 {(1 + bench.iloc[-12:]).prod() - 1:+.1%}")
    nov = (px.iloc[-1] / px.iloc[-1 - LOOK] - 1).dropna().sort_values(ascending=False).index[:TOP]
    print(f"Secteurs a detenir en novembre 2026 (signal fin octobre) : {', '.join(NAMES[c] for c in nov)}")
    ok = (n >= MIN_MONTHS and ann5 > annb and ex1 > 0 and ex2 > 0 and tot2 > p95 and dd2 >= dds - 0.05)
    print(f"\nRegle fixee avant : rotation sectorielle 3 mois {'A SUIVRE EN REEL SANS ARGENT' if ok else 'REJETE'}")


if __name__ == "__main__":
    main()
