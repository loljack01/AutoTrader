"""Section 3 : robustesse DESCRIPTIVE du swing RSI(2) de référence (limite 5 positions,
2012 -> dernier jour du cache, coût 0,05 %), sans aucune nouvelle règle.
Usage : python3 section3_swing.py   (écrit swing_trades.csv dans ce dossier)"""
import sys
sys.dont_write_bytecode = True
REPO = "/home/user/AutoTrader"; sys.path.insert(0, REPO + "/scripts"); sys.path.insert(0, REPO)
import numpy as np, pandas as pd
import swing_portfolio as sp
import test_swing_rsi2 as sw
rng = np.random.default_rng(2)
data = sp.load_all()
assert sp.check_reference(data)
c = sp.rsi2_candidates(data, ("2012-01-01", "2100-01-01"))
t = sp.select_book(c, 5).sort_values("exit").reset_index(drop=True)
t["market"] = t.sym.map(sw.INDICES)
t["zone"] = t.sym.map(lambda s: "US" if sp.ZONES[s] == "us" else "Europe")
t["days"] = (t.exit - t.entry).dt.days
t.to_csv("/home/user/AutoTrader/audit/2026-11-06/recherche/swing_trades.csv", index=False)
print(f"{len(t)} trades {t.entry.min():%Y-%m-%d} -> {t.exit.max():%Y-%m-%d}, total {t.r.sum():+.1f}R, {t.r.mean():+.4f}R/trade, gagnants {(t.r>0).mean():.0%}")
dd, w3, ry = sp.risk_stats(t, ("2012-01-01", "2100-01-01"))
print(f"pire baisse {dd:+.1f}R | pire 3 mois (91 j) {w3:+.1f}R | R/an {ry:+.2f}")
eq = t.set_index("exit").r.cumsum(); daily = eq.resample("D").last().ffill()
w6 = (daily - daily.shift(182)).min(); p3 = (daily - daily.shift(91)).dropna(); p6 = (daily - daily.shift(182)).dropna()
print(f"pire 6 mois (182 j) {w6:+.1f}R | 3 mois : 5e centile {np.percentile(p3,5):+.1f}R, part < 0 {(p3<0).mean():.0%} | 6 mois : 5e centile {np.percentile(p6,5):+.1f}R, part < 0 {(p6<0).mean():.0%}")
print(f"date pire 3 mois : fin {(daily - daily.shift(91)).idxmin():%Y-%m-%d} ; pire 6 mois : fin {(daily - daily.shift(182)).idxmin():%Y-%m-%d}")
for col in ("market", "zone"):
    g = t.groupby(col).r.agg(["count", "sum", "mean"]); print(f"\nPar {col}:\n{g.round(3).to_string()}")
g = t.groupby(t.exit.dt.year).r.agg(["count", "sum", "mean"]); print(f"\nPar annee (sortie):\n{g.round(2).to_string()}")
print(f"annees negatives : {(g['sum']<0).sum()} / {len(g)}")
t["dur"] = pd.cut(t.days, [-1, 1, 3, 7, 30], labels=["1 j", "2-3 j", "4-7 j", "8-14 j"])
print(f"\nPar duree (jours calendaires):\n{t.groupby('dur', observed=True).r.agg(['count','sum','mean']).round(3).to_string()}")
# concentration
s = np.sort(t.r.to_numpy())[::-1]; k = int(np.ceil(0.05 * len(s)))
print(f"\nTop 5 % ({k} trades) : {s[:k].sum():+.1f}R = {s[:k].sum()/s.sum():.0%} du total ; sans eux {s[k:].sum():+.1f}R ; top 1 % {s[:int(np.ceil(.01*len(s)))].sum()/s.sum():.0%}")
print(f"plus gros gain {s[0]:+.2f}R, plus grosse perte {s[-1]:+.2f}R")
# séries de pertes (ordre des sorties)
loss = (t.r < 0).to_numpy(); best = cur = 0; cumR = worstR = 0.0
for x, r in zip(loss, t.r):
    cur = cur + 1 if x else 0; best = max(best, cur)
    cumR = cumR + r if x else 0.0; worstR = min(worstR, cumR)
print(f"pire serie de pertes consecutives : {best} trades ; pire serie en R {worstR:+.2f}R")
# Probabilité que les 30 premiers trades soient négatifs, avantage réel = celui de l'historique
wk = t.groupby(t.exit.dt.tz_localize(None).dt.to_period("W"))
blocks = [g.r.to_numpy() for _, g in wk]
def first_n(n, shift=0.0):
    out = []; tot = 0.0; cnt = 0
    while cnt < n:
        b = blocks[rng.integers(len(blocks))]
        take = b[: n - cnt]; tot += (take + shift).sum(); cnt += len(take)
    return tot
for n in (30, 50, 100):
    sims = np.array([first_n(n) for _ in range(20000)])
    print(f"P(somme des {n} premiers trades < 0 | avantage historique) = {(sims<0).mean():.1%} (blocs hebdo) ; 5e centile {np.percentile(sims,5):+.1f}R")
iid = np.array([rng.choice(t.r.to_numpy(), 30).sum() for _ in range(20000)])
print(f"  (iid, pour comparaison : {(iid<0).mean():.1%})")
sims0 = np.array([first_n(30, -t.r.mean()) for _ in range(20000)])
print(f"P(30 premiers > 0 | avantage nul) = {(sims0>0).mean():.1%}")
sims10 = np.array([first_n(50, 0) for _ in range(20000)]); print(f"P(frein -10R touche en 50 trades) ~ part des sommes <= -10 : {(sims10<=-10).mean():.1%}")
# Kelly
mu, var = t.r.mean(), t.r.var()
w = wk.r.sum(); years = (t.exit.max() - t.entry.min()).days / 365.25
print(f"\nKelly par trade (independant) f* = mu/var = {mu:.4f}/{var:.4f} = {mu/var:.1%} du capital risque par trade")
print(f"Kelly hebdomadaire (positions simultanees) f* = {w.mean():.4f}/{w.var():.4f} = {w.mean()/w.var():.1%} par trade")
# Tolérance −500 € sur 3 mois, capital 10 000 €
p3m = p3.to_numpy()
print(f"pire 3 mois {p3m.min():+.1f}R, 1er centile {np.percentile(p3m,1):+.1f}R, 5e {np.percentile(p3m,5):+.1f}R")
# Monte Carlo 3 mois par blocs hebdo (13 semaines)
wv = w.to_numpy()
sim3 = np.array([rng.choice(wv, 13).sum() for _ in range(50000)])
print(f"Monte Carlo 13 semaines (blocs hebdo iid) : 1er centile {np.percentile(sim3,1):+.1f}R, 5e {np.percentile(sim3,5):+.1f}R, 0,1 % {np.percentile(sim3,0.1):+.1f}R")
for eur in (25, 37.5, 50, 0.5*10000*w.mean()/w.var()*0.25):
    print(f"  risque {eur:6.1f} EUR ({eur/100:.3f} % de 10 000) : pire 3 mois historique {p3m.min()*eur:+.0f} EUR, P(3 mois <= -500 EUR) MC = {(sim3*eur <= -500).mean():.2%}, hist = {(p3m*eur<=-500).mean():.2%}")
fk = w.mean() / w.var()
print(f"fraction de Kelly compatible (pire 3 mois historique = -500 EUR) : {500/abs(p3m.min())/10000:.3%} du capital = {500/abs(p3m.min())/10000/fk:.2f} x Kelly hebdo")
print(f"fraction de Kelly compatible (1er centile MC = -500 EUR) : {500/abs(np.percentile(sim3,1))/10000:.3%} = {500/abs(np.percentile(sim3,1))/10000/fk:.2f} x Kelly")
