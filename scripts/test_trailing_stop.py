"""TEST 8 of docs/test_8_stop_suiveur_fige_2026-11-10.md (frozen on 2026-11-10 BEFORE
running, at the user's request: "Execute tes recommandations"). NOT RUN: to be run
on a Sunday, on the user's explicit order (moratorium of 06/11, rule 12 of
docs/regles_execution.md). Only the reproduction check (--controle) has been
run: it prints no result of the variant.

Origin and honesty: idea born from the trade-by-trade audit of 10/11
(docs/audit_trades_principale_2026-11-10.md): 9 of the 30 stopped trades of the
live tracking (28/10 -> 09/11) had gone at least +1R in favour before coming back
to the stop, and open trades gave back large latent gains. It is POST-HOC for
the trades entered from 2026-10-28, so the test is judged ONLY on the trades
entered BEFORE 2026-10-28, which the audit did not look at. Its cousin "stop to
entry at +1R" was rejected on 26/10 (scripts/exit_variants_test.py).

Base: the main strategy as frozen (frozen_15m_variants.run, sma20: calls with
the daily trend, puts always), 10 markets, 15m bars of data/cache.
Variant "stop suiveur structurel" (the ONLY change; the entries are those of
the base, re-walked bar by bar; a slot freed earlier is not re-used):
  armed       once a bar after the entry bar has reached +1R in favour
              (high >= entry + risk for a call, low <= entry - risk for a put);
  trailing    from then on, at each bar close, the stop becomes the most recent
              CONFIRMED swing low formed after the entry bar, minus the engine's
              stop margin (8 points CAC-equivalent x the market factor), if that
              level is above the current stop and below the bar's close (calls;
              mirror with swing highs plus the margin for puts). A swing is the
              engine's: low strictly below the 2 previous lows and not above
              the 2 next ones, confirmed 2 bars later. The stop never moves back
              and applies from the next bar;
  exits       stop (original or trailed) or the ORIGINAL target, stop first when
              a bar touches both, filled at the level (as the base engine).
  result      side x (exit - entry) / initial risk - cost / initial risk.
Costs 1pt and 3pt CAC-equivalent (trades selected by the base at each cost).

Decision (fixed before running), on the closed trades entered BEFORE 2026-10-28,
10 markets pooled, ALL conditions:
  (a) net R of the variant > net R of the base at 1pt AND at 3pt;
  (b) the same at 1pt on both time halves (per-market halves, summed);
  (c) with every trade's result capped at +5R (the go-live measure): variant >
      base at 1pt;
  (d) variant >= base at 1pt on at least 6 of the 10 markets;
  (e) t-statistic of the daily sums of (variant - base) per trade, by entry day,
      at 1pt >= 2.50 (Bonferroni 5 % / 8 tests, one-sided).
If passed: a NEW candidate tracked forward WITHOUT money (verdict at 100 closed
trades against the main strategy, as variants A-D); the main strategy is not
changed and nothing goes to real money. Otherwise REJECTED, no re-tuning (no
other trigger, margin or swing length is tried). Trades entered from 2026-10-28
are printed for information only.
Multiple-testing budget: 8 tests (tests 1-8 of 2026).

Result: not run yet.

Usage: python scripts/test_trailing_stop.py            (full test)
       python scripts/test_trailing_stop.py --controle (reproduction check only)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
import frozen_15m_variants as fv
from frozen_15m_calls_trend import MARKETS

CUT = pd.Timestamp("2026-10-28", tz="UTC")
ARM_R, T_MIN, CAP = 1.0, 2.50, 5.0


def walk(d, pos, x, cost, margin, trailing):
    """Re-walk one base trade bar by bar. Returns (result, net_r) or None if still open."""
    o, h, l, c = (d[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    e = pos[x.entry_time]
    side = 1 if x.take > x.entry else -1
    risk = abs(x.entry - x.stop)
    stop, armed, swing, moved = x.stop, False, None, False
    for j in range(e + 1, len(d)):
        hit_stop = l[j] <= stop if side == 1 else h[j] >= stop
        hit_take = h[j] >= x.take if side == 1 else l[j] <= x.take
        if hit_stop:
            if not moved:
                return "stop", -(1.0 + cost / risk)
            return "trail", side * (stop - x.entry) / risk - cost / risk
        if hit_take:
            return "take", abs(x.take - x.entry) / risk - cost / risk
        if not trailing:
            continue
        if (h[j] - x.entry if side == 1 else x.entry - l[j]) >= ARM_R * risk:
            armed = True
        p = j - 2  # pivot confirmed at the close of bar j
        if p > e:
            if side == 1 and l[p] < l[p - 1] and l[p] < l[p - 2] and l[p] <= l[p + 1] and l[p] <= l[p + 2]:
                swing = l[p]
            if side == -1 and h[p] > h[p - 1] and h[p] > h[p - 2] and h[p] >= h[p + 1] and h[p] >= h[p + 2]:
                swing = h[p]
        if armed and swing is not None:
            cand = swing - side * margin
            if (side == 1 and stop < cand < c[j]) or (side == -1 and c[j] < cand < stop):
                stop, moved = cand, True
    return None


def collect(cost, trailing):
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for s, (name, k) in MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now)
        pos = {ts: i for i, ts in enumerate(d.index)}
        t = fv.run(s, d, cost)
        half = d.index[len(d) // 2]
        for x in t.itertuples():
            w = walk(d, pos, x, cost * k, 8.0 * k, trailing)
            rows.append({"market": name, "entry_time": x.entry_time, "base_result": x.result,
                         "base": x.net_r if x.result != "open" else np.nan,
                         "var_result": w[0] if w else "open", "var": w[1] if w else np.nan,
                         "second_half": x.entry_time >= half})
    return pd.DataFrame(rows)


def controle():
    ok = True
    for cost in (1.0, 3.0):
        r = collect(cost, trailing=False)
        same = ((r.base_result == r.var_result) & (np.isclose(r.base, r["var"]) | (r.base.isna() & r["var"].isna()))).all()
        ok &= bool(same)
        print(f"Controle a {cost:.0f}pt : {len(r)} trades de la base re-parcourus sans stop suiveur -> "
              f"{'IDENTIQUE' if same else 'DIFFERENT'}")
    return ok


def main():
    if "--controle" in sys.argv:
        controle()
        return
    if not controle():
        print("Re-parcours different de la base : test non lance.")
        return
    res = {cost: collect(cost, trailing=True) for cost in (1.0, 3.0)}
    out = {}
    for cost, r in res.items():
        r = r[(r.base_result != "open") & (r.var_result != "open")]
        hist, fw = r[r.entry_time < CUT], r[r.entry_time >= CUT]
        out[cost] = hist
        print(f"\nCout {cost:.0f}pt, trades entres avant le 28/10 : {len(hist)} | base {hist.base.sum():+.1f}R, variante "
              f"{hist['var'].sum():+.1f}R | plafonne 5R : base {np.minimum(hist.base, CAP).sum():+.1f}R, variante "
              f"{np.minimum(hist['var'], CAP).sum():+.1f}R | sorties au stop suiveur : {(hist.var_result == 'trail').sum()}")
        print(f"  (information, depuis le 28/10 : {len(fw)} trades, base {fw.base.sum():+.1f}R, variante {fw['var'].sum():+.1f}R)")
    h1, h3 = out[1.0], out[3.0]
    a = h1["var"].sum() > h1.base.sum() and h3["var"].sum() > h3.base.sum()
    halves = [(g["var"].sum(), g.base.sum()) for _, g in h1.groupby("second_half")]
    b = len(halves) == 2 and all(v > x for v, x in halves)
    c = np.minimum(h1["var"], CAP).sum() > np.minimum(h1.base, CAP).sum()
    mk = h1.groupby("market").apply(lambda g: g["var"].sum() >= g.base.sum())
    dd = (h1["var"] - h1.base).groupby(h1.entry_time.dt.tz_convert("Europe/Paris").dt.date).sum()
    t = dd.mean() / (dd.std(ddof=1) / np.sqrt(len(dd))) if len(dd) > 2 else float("nan")
    print(f"\n  moities (variante/base) : {' ; '.join(f'{v:+.1f}/{x:+.1f}R' for v, x in halves)} | marches ou la variante "
          f">= la base : {int(mk.sum())}/10 | t par jour d'entree de (variante - base) : {t:+.2f}")
    print(f"  (a) {a} | (b) {b} | (c) {c} | (d) {mk.sum() >= 6} | (e) {t >= T_MIN}")
    print(f"Regle fixee avant : {'NOUVELLE CANDIDATE A SUIVRE SANS ARGENT' if all((a, b, c, mk.sum() >= 6, t >= T_MIN)) else 'REJETEE'}")


if __name__ == "__main__":
    main()
