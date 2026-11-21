"""Section 4 : corrélations journalières/hebdomadaires des R (par date de sortie, Paris)
entre principale (sma20), swing (limite 5), écart continue et simple balayage, sur la
période commune ; puis risque combiné vs la limite globale -500 EUR sur 3 mois.
Usage : python3 section4_correlations.py (après gen_trades.py et section3_swing.py)"""
import numpy as np, pandas as pd
rng = np.random.default_rng(4)
t = pd.read_csv("/home/user/AutoTrader/audit/2026-11-06/recherche/trades_15m.csv", parse_dates=["entry_time", "exit_time"])
t = t[t.result != "open"]
sw = pd.read_csv("/home/user/AutoTrader/audit/2026-11-06/recherche/swing_trades.csv", parse_dates=["entry", "exit"])
ser = {}
for s in ("principale", "D", "simple", "ecart"):
    x = t[t.strat == s]
    ser[s] = x.groupby(x.exit_time.dt.tz_convert("Europe/Paris").dt.date).net_r.sum()
ser["swing"] = sw.groupby(sw.exit.dt.date).r.sum()
start = max(pd.Timestamp(min(ser[s].index)) for s in ("principale", "simple", "ecart"))
start = pd.Timestamp("2026-08-03")  # 10 marchés présents (ES/NQ/YM/RTY dès le 02/08)
end = pd.Timestamp("2026-11-05")
days = pd.bdate_range(start, end)
df = pd.DataFrame({s: v.reindex(pd.to_datetime(v.index)).reindex(days).fillna(0) for s, v in ser.items()}) if False else \
     pd.DataFrame({s: pd.Series(v.values, index=pd.to_datetime(v.index)).groupby(level=0).sum().reindex(days).fillna(0) for s, v in ser.items()})
print(f"Periode commune {start:%d/%m/%Y} -> {end:%d/%m/%Y}, {len(df)} jours ouvres ; R totaux :\n{df.sum().round(1).to_string()}")
print("\nCorrelation journaliere (Pearson):\n", df.corr().round(2).to_string())
print("\nCorrelation journaliere (Spearman):\n", df.corr(method="spearman").round(2).to_string())
wk = df.resample("W").sum()
print(f"\nCorrelation hebdomadaire (Pearson, {len(wk)} semaines):\n", wk.corr().round(2).to_string())
# IC bootstrap de la corrélation principale-swing (journalière, blocs de 5 jours)
def boot(a, b, n=5000):
    out = []; idx = np.arange(len(a)); nb = len(a) // 5
    for _ in range(n):
        st = rng.integers(0, len(a) - 5, nb); i = (st[:, None] + np.arange(5)).ravel()
        out.append(np.corrcoef(a[i], b[i])[0, 1])
    return np.nanpercentile(out, [2.5, 97.5])
for a, b in (("principale", "swing"), ("principale", "ecart"), ("principale", "simple"), ("swing", "ecart")):
    lo, hi = boot(df[a].to_numpy(), df[b].to_numpy())
    print(f"  IC95 corr {a}-{b} : [{lo:+.2f}, {hi:+.2f}]")
# Risque combiné : 13 semaines, swing (semaines 2012-2026) + principale/D (semaines du backtest 15m)
sww = sw.groupby(sw.exit.dt.tz_localize(None).dt.to_period("W")).r.sum()
sw_weeks = sww.reindex(pd.period_range(sww.index.min(), sww.index.max(), freq="W")).fillna(0).to_numpy()
EUR = 25.0
for main in ("principale", "D"):
    x = t[(t.strat == main) & (t.entry_time < pd.Timestamp("2026-10-28", tz="UTC"))]
    x = x[x.exit_time >= pd.Timestamp("2026-08-03", tz="UTC")]
    mw = x.groupby(x.exit_time.dt.tz_convert(None).dt.to_period("W")).net_r.sum()
    mw = mw.reindex(pd.period_range("2026-08-03", "2026-10-27", freq="W")).fillna(0).to_numpy()
    for lab, shift in (("avantage backtest", 0.0), ("avantage nul", -mw.mean())):
        tot, dd = [], []
        for _ in range(40000):
            path = (rng.choice(sw_weeks, 13) + rng.choice(mw, 13) + shift) * EUR
            c = np.cumsum(path); tot.append(c[-1]); dd.append((c - np.maximum.accumulate(np.maximum(c, 0))).min())
        tot, dd = np.array(tot), np.array(dd)
        print(f"{main} ({lab}) + swing, 25 EUR chacun, 13 semaines : P(somme <= -500) {np.mean(tot<=-500):.1%}, "
              f"P(baisse intra <= -500) {np.mean(dd<=-500):.1%}, 5e centile somme {np.percentile(tot,5):+.0f} EUR | "
              f"principale seule : semaines moy {mw.mean():+.2f}R, ecart-type {mw.std():.2f}R, pire semaine {mw.min():+.1f}R")
tot = np.array([rng.choice(sw_weeks, 13).sum() * EUR for _ in range(40000)])
print(f"swing seul 25 EUR : P(13 semaines <= -500) {np.mean(tot<=-500):.2%}")
