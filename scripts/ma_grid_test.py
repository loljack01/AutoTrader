"""Which daily moving average for the trend filter? Fixed on 2026-10-27
BEFORE running.

Only point 1+2 (direction) uses a moving average; points 3 (hours),
4 (freshness) and 5 (minimum R:R) have none.

Grid: SMA and EMA of the daily close, lengths 5, 10, 20, 50, 100, 200,
in two variants on the frozen 15m rules (cost scaled per market):
  calls  calls only if the previous daily close is above the average,
         puts always allowed (the "1+2" fix)
  both   calls only above, puts only below (like the frozen sma20)

Train / validation, to avoid picking a lucky length:
  - the best average of each variant is CHOSEN on the 5 markets where the
    losing points were found (CAC, DAX, Euro Stoxx 50, S&P 500, Nasdaq),
    by pooled net R at 1pt-equivalent;
  - it is then CHECKED on the 5 new markets (FTSE 100, SMI, Dow, Russell
    2000, FTSE MIB). It replaces the 20-day SMA as candidate only if, on
    the new markets, it beats the 20-day SMA of the same variant at BOTH
    1pt and 3pt-equivalent cost. Otherwise the 20-day SMA stays.

Usage: python scripts/ma_grid_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from improved_15m_test import IN_SAMPLE, NEW
from other_markets_test import CAC_LEVEL

BAR = pd.Timedelta(minutes=15)
LENGTHS = (5, 10, 20, 50, 100, 200)


def trend_up(symbol, d, kind, n):
    daily = bt.cache.load(symbol, "1D")
    daily.index = pd.to_datetime(daily.index, utc=True)
    c = daily.Close
    ma = c.rolling(n).mean() if kind == "SMA" else c.ewm(span=n, adjust=False).mean()
    up = (c > ma).to_numpy() & ma.notna().to_numpy()
    done_at = (daily.index + pd.Timedelta(days=1)).to_numpy()
    pos = np.searchsorted(done_at, (d.index + BAR).to_numpy(), side="right") - 1
    return np.where(pos >= 0, up[np.clip(pos, 0, None)], False).astype(bool)


def run(d, k, cost, up, variant):
    bt.ROUND_TRIP_COST = cost * k
    bt.MIN_RISK_ATR_MULT = 2.0
    bt.STOP_MARGIN = 8.0 * k
    bt.SWING_N = 2
    bt.MIN_NET_RR = 1.3
    bt.CHOCH_WINDOW = pd.Timedelta(hours=4)
    sell = ~up if variant == "both" else None
    t = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up),
                   bt.backtest(d, True, False, direction="sell", entry_mask=sell)], ignore_index=True)
    return t[t.result != "open"].net_r.sum()


def grid(markets, now):
    """{(variant, kind, n, cost): pooled net R}"""
    out = {}
    data = {}
    for symbol in markets:
        d = bt.cache.closed_bars(bt.cache.load(symbol, "15m"), "15m", now)
        data[symbol] = (d, float(d[d.index < "2026-10-27"].Close.median()) / CAC_LEVEL)
    for kind in ("SMA", "EMA"):
        for n in LENGTHS:
            ups = {s: trend_up(s, d, kind, n) for s, (d, k) in data.items()}
            for variant in ("calls", "both"):
                for cost in (1.0, 3.0):
                    out[(variant, kind, n, cost)] = sum(run(d, k, cost, ups[s], variant) for s, (d, k) in data.items())
    return out


def show(title, g):
    print(f"\n==================== {title} (R net 1pt-eq / 3pt-eq, marches cumules)")
    for variant in ("calls", "both"):
        print(f"  variante {variant}:")
        for kind in ("SMA", "EMA"):
            cells = "  ".join(f"{n:>3d}j {g[(variant, kind, n, 1.0)]:+6.1f}/{g[(variant, kind, n, 3.0)]:+6.1f}" for n in LENGTHS)
            print(f"    {kind}: {cells}")


def main():
    now = pd.Timestamp.now(tz="UTC")
    train, test = grid(IN_SAMPLE, now), grid(NEW, now)
    show("5 marches d'origine (choix)", train)
    show("5 nouveaux marches (verification)", test)
    print("\nRegle fixee avant:")
    for variant in ("calls", "both"):
        best = max(((k, n) for k in ("SMA", "EMA") for n in LENGTHS), key=lambda x: train[(variant, x[0], x[1], 1.0)])
        b1, b3 = test[(variant, *best, 1.0)], test[(variant, *best, 3.0)]
        r1, r3 = test[(variant, "SMA", 20, 1.0)], test[(variant, "SMA", 20, 3.0)]
        keep = b1 > r1 and b3 > r3 and best != ("SMA", 20)
        print(f"  {variant}: meilleure sur les marches d'origine = {best[0]} {best[1]} jours "
              f"({train[(variant, *best, 1.0)]:+.1f}R) ; sur les nouveaux {b1:+.1f}/{b3:+.1f}R contre SMA 20 {r1:+.1f}/{r3:+.1f}R "
              f"-> {'REMPLACE la SMA 20' if keep else 'la SMA 20 reste'}")


if __name__ == "__main__":
    main()
