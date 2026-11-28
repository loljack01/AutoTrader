"""Quantitative audit (2026-11-05) of the two strategies that survived:
the MAIN 15m strategy (sma20, 10 markets, all trades in the cache: reference
+ live) and the SWING rule (calls, 10 indices, 2012-2026). Descriptive only:
nothing here changes a rule. Prints per-trade statistics, dependence on the
best trades, clustering across markets, drawdowns, Kelly fractions, and the
power / false-positive rate of the go-live verdicts (bootstrap).

Findings (run on 2026-11-05):
  MAIN, 333 trades 26/05 -> 04/11/2026, 1pt: +0.316R/trade, sd 2.96R, t=1.95,
    34 % winners, profit factor 1.46, skew +7.6; +105.1R total but +42.3R
    without the 3 best trades and +47.8R with gains capped at 5R (t=1.46);
    one FTSE 100 put entered 26/08 06:15 Paris with a 9-point (CAC eq.) stop
    and held 43 days made +39.3R; entries 22h-8h Paris: 50 trades +62.5R
    (capped +13.0R) vs 8h-22h: 283 trades +42.6R (capped +34.8R); calls 97
    trades +0.086R/trade (t=0.5), puts 236 trades +0.41R/trade (t=1.9);
    worst drawdown -27.5R; Kelly 3.6 % per R (1/4 Kelly 0.9 %, i.e. the 1 %
    risk used is about a quarter Kelly). Verdict at 100 trades: passes 79 %
    of the time if the backtest edge is real, 19 % if there is no edge.
  SWING, 1322 trades: +0.074R/trade, sd 0.59R, t=4.6, PF 1.36, skew -1.0,
    worst drawdown -40.3R (2018: -24.7R); Kelly 21 % per R. Verdict at 50
    trades: passes 68 % if real, 34 % if no edge (weak as a test of edge,
    useful only as a check of the live implementation).

Usage: python scripts/audit_quant.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
import backtest_liquidity_sweep_buy as bt
import frozen_15m_calls_trend as fc
import test_swing_rsi2 as sw


def stats(r, label):
    r = np.asarray(r, float)
    w, l = r[r > 0], r[r <= 0]
    eq = np.cumsum(r)
    dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    top3 = np.sort(r)[-3:].sum()
    t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
    kelly = r.mean() / r.var(ddof=1)
    print(f"{label}: n={len(r)} moy {r.mean():+.3f}R ecart-type {r.std(ddof=1):.2f}R t={t:+.2f} | gagnants {len(w)/len(r):.0%} "
          f"gain moy {w.mean():+.2f}R perte moy {l.mean():+.2f}R facteur de profit {w.sum()/-l.sum():.2f} | "
          f"total {r.sum():+.1f}R, sans les 3 meilleurs {r.sum()-top3:+.1f}R, pire baisse {dd:+.1f}R | "
          f"asymetrie {pd.Series(r).skew():+.2f} | Kelly {kelly:.1%} du capital par R (1/4 Kelly {kelly/4:.1%})")
    return r


def power(r, n, rule, draws=20000, seed=0):
    rng = np.random.default_rng(seed)
    real = np.array([rule(rng.choice(r, n)) for _ in range(draws)]).mean()
    z = r - r.mean()
    null = np.array([rule(rng.choice(z, n)) for _ in range(draws)]).mean()
    return real, null


def main():
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for sym, (name, k) in fc.MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(sym, "15m"), "15m", now)
        for cost in (1.0, 3.0):
            t = fc.run(sym, d, 20, cost)
            t = t[t.result != "open"]
            rows.append(t.assign(market=name, cost=cost, side=np.where(t["take"] > t["entry"], "call", "put")))
    t = pd.concat(rows, ignore_index=True)
    m1, m3 = t[t.cost == 1.0], t[t.cost == 3.0]
    print(f"=== PRINCIPALE (sma20, 10 marches, cache 15m {m1.entry_time.min():%d/%m/%Y} -> {m1.entry_time.max():%d/%m/%Y})")
    r = stats(m1.net_r, "  tous, 1pt")
    stats(m3.net_r, "  tous, 3pt")
    for s in ("call", "put"):
        stats(m1[m1.side == s].net_r, f"  {s}s, 1pt")
    live = m1[m1.entry_time >= fc.FREEZE_START]
    stats(live.net_r, "  suivi reel depuis le 28/10, 1pt")
    day = m1.groupby(m1.entry_time.dt.tz_convert("Europe/Paris").dt.date).net_r.agg(["count", "sum"])
    print(f"  regroupement : {len(m1)} trades sur {len(day)} jours ; jours a 3 trades ou plus : {(day['count'] >= 3).sum()} "
          f"; pire journee {day['sum'].min():+.1f}R, meilleure {day['sum'].max():+.1f}R")
    piv = m1.assign(day=m1.entry_time.dt.tz_convert("Europe/Paris").dt.date).pivot_table(index="day", columns="market", values="net_r", aggfunc="sum").fillna(0)
    c = piv.corr().to_numpy()
    print(f"  correlation moyenne des resultats journaliers entre marches : {c[np.triu_indices_from(c, 1)].mean():+.2f}")
    g = lambda x: x.sum() > 0 and np.minimum(x, 5).sum() > 0
    real, null = power(r, 100, g)
    print(f"  verdict a 100 trades (net > 0 et plafonne > 0) : chance de passer si l'avantage est celui du backtest {real:.0%}, "
          f"si l'avantage est nul {null:.0%}")
    for n in (100, 200, 400):
        a, b = power(r, n, lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) > 2.0, draws=5000)
        print(f"  test t > 2 sur {n} trades : puissance {a:.0%}, faux positif {b:.0%}")

    print("\n=== SWING (calls, 10 indices, 2012-2026, frais 0,05 %)")
    tt = pd.concat([sw.run(sw.load(s), 1) for s in sw.INDICES], ignore_index=True).sort_values("exit")
    rs = stats(sw.net(tt, 0.0005).to_numpy(), "  ")
    real, null = power(rs, 50, lambda x: x.sum() > 0 and x.mean() >= 0.037)
    print(f"  verdict a 50 trades : chance de passer si l'avantage est celui du backtest {real:.0%}, si nul {null:.0%}")
    yr = pd.Series(rs, index=tt.exit.dt.year.to_numpy()).groupby(level=0).sum()
    print("  par annee : " + ", ".join(f"{y} {v:+.1f}" for y, v in yr.items()))


if __name__ == "__main__":
    main()
