"""Section 3 (suite) : stabilité dans le temps du swing de référence (limite 5),
lit swing_trades.csv (section3_swing.py). Descriptif seulement.
Usage : python3 section3_periodes.py"""
import numpy as np, pandas as pd
t = pd.read_csv("/home/user/AutoTrader/audit/2026-11-06/recherche/swing_trades.csv", parse_dates=["entry", "exit"])
rng = np.random.default_rng(3)
def tw(x):
    w = x.groupby(x.exit.dt.tz_localize(None).dt.to_period("W")).r.sum(); return w.mean() / (w.std(ddof=1) / np.sqrt(len(w))), w
for a, b in (("2012", "2018"), ("2018", "2027"), ("2012", "2022"), ("2022", "2027")):
    x = t[(t.exit >= pd.Timestamp(a, tz="UTC")) & (t.exit < pd.Timestamp(b, tz="UTC"))]
    tt, w = tw(x)
    print(f"{a}-{int(b)-1}: {len(x)} trades {x.r.sum():+.1f}R {x.r.mean():+.4f}R/trade t hebdo {tt:+.2f} Kelly hebdo {w.mean()/w.var():.1%}")
# différence 2012-2017 vs 2018-2026 (permutation par semaines)
t["wk"] = t.exit.dt.tz_localize(None).dt.to_period("W")
w = t.groupby("wk").r.agg(["sum", "count"])
late = (w.index.start_time >= "2018-01-01")
obs = w["sum"][late].sum() / w["count"][late].sum() - w["sum"][~late].sum() / w["count"][~late].sum()
perm = []
for _ in range(5000):
    p = rng.permutation(late); perm.append(w["sum"][p].sum() / w["count"][p].sum() - w["sum"][~p].sum() / w["count"][~p].sum())
print(f"diff R/trade 2018+ moins 2012-2017 = {obs:+.4f}, p(permutation semaines) = {(np.abs(perm) >= abs(obs)).mean():.3f}")
# P(30 premiers trades < 0) si l'avantage réel est celui de 2018-2026 (blocs hebdo décalés)
blocks = [g.r.to_numpy() for _, g in t.groupby("wk")]
mu_recent = t[t.exit >= pd.Timestamp("2018", tz="UTC")].r.mean(); shift = mu_recent - t.r.mean()
def first_n(n, s):
    tot = 0.0; cnt = 0
    while cnt < n:
        b = blocks[rng.integers(len(blocks))][: n - cnt]; tot += (b + s).sum(); cnt += len(b)
    return tot
sims = np.array([first_n(30, shift) for _ in range(20000)])
print(f"P(30 premiers < 0 | avantage 2018-2026 = {mu_recent:+.4f}R/trade) = {(sims < 0).mean():.1%}")
