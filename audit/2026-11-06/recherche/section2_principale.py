"""Section 2 : historique (entrée < 28/10) vs suivi (>= 28/10) de la principale sma20,
bootstrap des différences, et probabilité de la règle séquentielle.
Usage : python3 section2_principale.py   (lit trades_15m.csv produit par gen_trades.py)"""
import numpy as np, pandas as pd
rng = np.random.default_rng(1)
t = pd.read_csv("/home/user/AutoTrader/audit/2026-11-06/recherche/trades_15m.csv", parse_dates=["entry_time", "exit_time"])
K = {"CAC 40": 1.0, "DAX": 3.2397, "Euro Stoxx 50": 0.8004, "S&P 500": 0.9799, "Nasdaq 100": 3.7619, "FTSE 100": 1.362,
     "SMI": 1.7999, "Dow Jones": 6.6697, "Russell 2000": 0.3678, "FTSE MIB": 6.5848}
# coût 3pt sur le MÊME trade : net_r - 2pt x k / risque (les listes 1pt et 3pt diffèrent car le filtre R:R dépend du coût)
t["net_r3"] = t.net_r - 2.0 * t.market.map(K) / (t["entry"] - t["stop"]).abs()
FREEZE = pd.Timestamp("2026-10-28", tz="UTC")
def desc(x):
    x = x[x.result != "open"].copy()
    hp = x.entry_time.dt.tz_convert("Europe/Paris").dt.hour
    x["night"] = (hp >= 22) | (hp < 8)
    x["hold_h"] = (x.exit_time - x.entry_time).dt.total_seconds() / 3600
    x["call"] = x["take"] > x["entry"]
    return x
def stats(x):
    return dict(n=len(x), moy=x.net_r.mean(), moy_cap=np.minimum(x.net_r, 5).mean(), moy3=x.net_r3.mean(),
                gain=(x.net_r > 0).mean(), gt5=(x.net_r > 5).mean(), hold_med=x.hold_h.median(),
                hold_moy=x.hold_h.mean(), nuit=x.night.mean(), calls=x.call.mean(), total=x.net_r.sum())
for strat in ("principale", "D", "simple", "ecart"):
    x = desc(t[t.strat == strat])
    if strat == "ecart":
        x["call"] = x["take"] > x["entry"]
    h, l = x[x.entry_time < FREEZE], x[x.entry_time >= FREEZE]
    sh, sl = stats(h), stats(l)
    print(f"\n=== {strat}")
    for k in sh:
        print(f"  {k:9s} historique {sh[k]:8.3f} | suivi {sl[k]:8.3f}")
    if strat in ("principale", "simple", "ecart") and len(l) > 5:
        # bootstrap : p-valeur bilatérale de la différence (permutation des étiquettes)
        both = pd.concat([h, l]); nh = len(h)
        for col, f in (("net_r", np.mean), ("cap", None), ("win", None), ("gt5", None), ("hold_h", np.median), ("night", np.mean)):
            v = both.net_r.to_numpy() if col == "net_r" else np.minimum(both.net_r, 5).to_numpy() if col == "cap" else \
                (both.net_r > 0).to_numpy().astype(float) if col == "win" else (both.net_r > 5).to_numpy().astype(float) if col == "gt5" else \
                both[col].to_numpy().astype(float)
            f = f or np.mean
            obs = f(v[nh:]) - f(v[:nh])
            # bootstrap des deux échantillons (IC 95 %) + permutation
            bs = [f(rng.choice(v[nh:], len(v) - nh)) - f(rng.choice(v[:nh], nh)) for _ in range(5000)]
            perm = []
            for _ in range(5000):
                p = rng.permutation(v); perm.append(f(p[nh:]) - f(p[:nh]))
            pval = (np.abs(perm) >= abs(obs)).mean()
            print(f"  diff {col:7s} suivi-hist {obs:+.3f}  IC95 [{np.percentile(bs,2.5):+.3f},{np.percentile(bs,97.5):+.3f}]  p(perm)={pval:.3f}")

# Règle séquentielle (frozen_15m_calls_trend.py) : cumul plafonné 5R (1pt), contrôles tous les 100,
# PASSE si >= 72 et net 3pt > 0 ; ABANDON <=0 dès 200, <= -15 à tout moment, 600 sans passer.
def seq_rule(r1, r3):
    cum = np.cumsum(np.minimum(r1, 5.0)); cum3 = np.cumsum(r3)
    below = np.flatnonzero(cum <= -15.0)
    first_brake = below[0] + 1 if len(below) else 10**9
    for k in range(100, 601, 100):
        if first_brake <= k:
            return "frein", first_brake
        if cum[k - 1] >= 72 and cum3[k - 1] > 0:
            return "passe", k
        if k >= 200 and cum[k - 1] <= 0:
            return "abandon", k
    return "abandon600", 600
def simulate(r1, r3, mu_cap, n_sim=20000, block=None):
    cap = np.minimum(r1, 5.0)
    shift = mu_cap - cap.mean()            # décalage additif de tous les trades
    out = {"passe": 0, "frein": 0, "abandon": 0, "abandon600": 0}; ks = []
    for _ in range(n_sim):
        idx = rng.integers(0, len(r1), 600)
        res, k = seq_rule(r1[idx] + shift, r3[idx] + shift)
        out[res] += 1
        if res == "passe": ks.append(k)
    return {k: v / n_sim for k, v in out.items()}, (np.mean(ks) if ks else np.nan)
x = desc(t[t.strat == "principale"]); h = x[x.entry_time < FREEZE]
r1, r3 = h.net_r.to_numpy(), h.net_r3.to_numpy()
mu = np.minimum(r1, 5).mean()
print(f"\nBacktest principale avant 28/10 : {len(r1)} trades, moyenne plafonnée 5R {mu:+.3f}R, brute {r1.mean():+.3f}, 3pt {r3.mean():+.3f}")
for lab, m in (("avantage nul", 0.0), ("avantage backtest plafonné", mu), ("moitié", mu / 2)):
    p, kbar = simulate(r1, r3, m)
    print(f"  {lab:28s} mu={m:+.3f} -> P(passe)={p['passe']:.3f}  frein={p['frein']:.3f}  abandon={p['abandon']:.3f}  600={p['abandon600']:.3f}  trades moyens si passe={kbar:.0f}")
xd = desc(t[t.strat == "D"]); hd = xd[xd.entry_time < pd.Timestamp("2026-11-06", tz="UTC")]
d3 = hd.net_r3.to_numpy(); mud = np.minimum(d3, 5).mean()
print(f"\nVariante D historique (info) : {len(d3)} trades, moyenne 3pt plafonnée {mud:+.3f}R, 1pt {hd.net_r.mean():+.3f}")
for lab, m in (("avantage nul", 0.0), ("avantage backtest D", mud), ("moitié", mud / 2)):
    p, kbar = simulate(d3, d3, m)
    print(f"  D {lab:26s} mu={m:+.3f} -> P(passe)={p['passe']:.3f}  frein={p['frein']:.3f}")
