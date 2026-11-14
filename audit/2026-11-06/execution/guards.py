"""Regle globale -500 EUR sur 3 mois (docs/regles_execution.md point 8), simulation descriptive.
1) SWING seul, livre a 5 positions, 2012-2026, 25 EUR par trade (et 37,5 / 50 EUR pour comparaison) :
   resultat REALISE glissant sur 91 jours (dates de sortie), et version avec le latent des positions ouvertes
   (clotures journalieres). Episode = passage sous -500 EUR (rearme quand le glissant remonte au-dessus de -250 EUR).
2) + PRINCIPALE hypothetique (variante D "executable turbo", 10 marches, cache 15m 26/05 -> 05/11/2026, cout 3 pts,
   25 EUR par trade) : a) sur la periode commune reelle ; b) fenetres de 3 mois tirees au hasard (swing : fenetre
   historique ; principale : 63 jours tires par blocs de 5 jours dans son historique), 20 000 tirages, avec
   l'avantage du backtest puis avec un avantage nul (resultats centres).
Usage : python3 guards.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_all, cap5_trades, sw
import numpy as np
import pandas as pd
import backtest_liquidity_sweep_buy as bt
from frozen_15m_variants import run as vrun
from frozen_15m_calls_trend import MARKETS


def episodes(s, lim, rearm):
    n, armed = 0, True
    for v in s:
        if armed and v <= lim:
            n, armed = n + 1, False
        elif not armed and v > rearm:
            armed = True
    return n


data = load_all()
t = cap5_trades(data)
days = pd.date_range(t.entry.min(), t.exit.max(), freq="D")
for col, lab in (("net005", "0,05 %"), ("net010", "0,10 %")):
    real = t.groupby("exit")[col].sum().reindex(days, fill_value=0.0)
    roll = real.rolling(91, min_periods=1).sum()
    print(f"Swing {lab} : {len(t)} trades, pire 3 mois realise {roll.min():+.1f}R ({roll.idxmin():%m/%Y}), 5e centile {roll.quantile(.05):+.1f}R")
    for eur in (25, 37.5, 50):
        print(f"   {eur:>4} EUR/trade : pire 3 mois {roll.min() * eur:+.0f} EUR, declenchements -500 EUR : "
              f"{episodes(roll * eur, -500, -250)}")
# latent (mark-to-market) : P&L journalier de chaque trade sur les clotures
mtm = pd.Series(0.0, index=days)
for x in t.itertuples():
    d = data[x.sym]
    seg = d.Close[(d.index.normalize() >= x.entry) & (d.index.normalize() <= x.exit)]
    path = (seg.to_numpy() - x.entry_px) / x.risk
    path[-1] = x.move_r - 0.0005 * x.cost_frac
    pnl = np.diff(np.r_[0.0, path])
    mtm = mtm.add(pd.Series(pnl, index=seg.index.normalize()).groupby(level=0).sum(), fill_value=0.0)
rm = mtm.rolling(91, min_periods=1).sum()
print(f"Swing avec latent (0,05 %) : pire 3 mois {rm.min():+.1f}R ; 25 EUR -> {rm.min() * 25:+.0f} EUR, declenchements "
      f"{episodes(rm * 25, -500, -250)} ; 37,5 EUR -> {episodes(rm * 37.5, -500, -250)} ; 50 EUR -> {episodes(rm * 50, -500, -250)}")
eq = t.sort_values("exit").net005.cumsum()
print(f"Pire baisse du swing (cumul dans l'ordre des sorties) : {(eq - np.maximum(eq.cummax(), 0)).min():+.1f}R")

# principale, variante D
now = pd.Timestamp.now(tz="UTC")
parts = []
for s in MARKETS:
    d = bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now)
    x = vrun(s, d, 3.0, entry_hours=(8, 21.5), session_exit=21.75)
    parts.append(x[x.result != "open"])
m = pd.concat(parts, ignore_index=True)
m["day"] = m.exit_time.dt.tz_convert("Europe/Paris").dt.normalize().dt.tz_localize(None)
print(f"\nPrincipale D (3 pts) : {len(m)} trades {m.entry_time.min():%d/%m/%Y} -> {m.exit_time.max():%d/%m/%Y}, "
      f"{m.net_r.mean():+.3f}R/trade, total {m.net_r.sum():+.1f}R")
mday = m.groupby("day").net_r.sum()
bd = pd.bdate_range(mday.index.min(), mday.index.max())
mday = mday.reindex(bd, fill_value=0.0)
eqm = mday.cumsum()
print(f"  pire baisse {(eqm - np.maximum(eqm.cummax(), 0)).min():+.1f}R ; pire journee {mday.min():+.1f}R ; "
      f"journees a -3R ou pire : {(mday <= -3).sum()} sur {len(mday)}")
# periode commune
sday = t.assign(day=t.exit.dt.tz_localize(None)).groupby("day").net005.sum().reindex(bd, fill_value=0.0)
comb = (sday + mday)
rc = comb.rolling(63, min_periods=1).sum()
rs, rmn = sday.rolling(63, min_periods=1).sum(), mday.rolling(63, min_periods=1).sum()
print(f"  periode commune ({bd[0]:%d/%m} -> {bd[-1]:%d/%m/%Y}) : pire 3 mois swing {rs.min():+.1f}R, principale {rmn.min():+.1f}R, "
      f"ensemble {rc.min():+.1f}R = {rc.min() * 25:+.0f} EUR a 25 EUR ; declenchements -500 EUR : {episodes(rc * 25, -500, -250)}")
# tirages
rng = np.random.default_rng(0)
sw_daily = t.assign(day=t.exit.dt.tz_localize(None)).groupby("day").net005.sum().reindex(
    pd.bdate_range("2012-02-01", "2026-11-05"), fill_value=0.0)
sw3 = sw_daily.rolling(63).sum().dropna().to_numpy()
mv = mday.to_numpy()
for lab, arr in (("avantage du backtest", mv), ("avantage nul", mv - mv.mean())):
    sims = []
    for _ in range(20000):
        starts = rng.integers(0, len(arr) - 5, 13)
        msum = np.concatenate([arr[s:s + 5] for s in starts])[:63].sum()
        sims.append(rng.choice(sw3) + msum)
    sims = np.array(sims)
    print(f"  tirages ({lab}) : P(3 mois <= -20R) = {(sims <= -20).mean():.1%} ; 5e centile {np.percentile(sims, 5):+.1f}R ; "
          f"principale seule P = {np.mean([np.concatenate([arr[s:s + 5] for s in rng.integers(0, len(arr) - 5, 13)])[:63].sum() <= -20 for _ in range(5000)]):.1%}")
