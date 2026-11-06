"""Section 2 - le put CAC du 05/11 16h45 et le call du 06/11 15h45 : sont-ils
representatifs ? Fusionne EN MEMOIRE le cache FCE1! 15m du depot (lecture seule) avec
tv_FCE1_15m_20261104_20261106.json (TradingView, recu le 06/11, ce dossier), relance le
moteur officiel (frozen_15m_calls_trend.run, sma20, 1 pt) et situe chaque trade dans la
distribution historique (trades_principale.csv). Rien n'est ecrit dans le depot.

Usage: PYTHONDONTWRITEBYTECODE=1 python3 /home/user/AutoTrader/audit/2026-11-06/marche/case_cac.py
"""
import json
import sys
from pathlib import Path

REPO = Path("/home/user/AutoTrader")
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
from finta import TA

import backtest_liquidity_sweep_buy as bt
import frozen_15m_calls_trend as fc

HERE = Path(__file__).resolve().parent


def main():
    j = json.load(open(HERE / "tv_FCE1_15m_20261104_20261106.json"))["bars"]
    new = pd.DataFrame({"Open": j["o"], "High": j["h"], "Low": j["l"], "Close": j["c"], "Volume": j["v"]},
                       index=pd.to_datetime(j["t"], unit="s", utc=True))
    new = new.iloc[:-1]  # derniere bougie en formation
    d = bt.cache.load("FCE1!", "15m")
    d.index = pd.to_datetime(d.index, utc=True)
    ov = d.index.intersection(new.index)
    diff = (d.loc[ov, "Close"] - new.loc[ov, "Close"]).abs().max()
    d = pd.concat([d, new]).pipe(lambda x: x[~x.index.duplicated(keep="last")]).sort_index()
    print(f"fusion : {len(ov)} bougies communes (ecart max de cloture {diff}), derniere {d.index[-1].tz_convert('Europe/Paris')}")
    t = fc.run("FCE1!", d, 20, 1.0)
    atr = TA.ATR(d, 14)
    t = t[t.entry_time >= pd.Timestamp("2026-11-05", tz="UTC")].copy()
    t["entree"] = t.entry_time.dt.tz_convert("Europe/Paris").dt.strftime("%d/%m %H:%M")
    t["sortie"] = t.exit_time.dt.tz_convert("Europe/Paris").dt.strftime("%d/%m %H:%M")
    t["risk"] = (t.entry - t.stop).abs()
    t["risk_atr15"] = t.risk / atr.reindex(t.entry_time).to_numpy()
    t["rr"] = (t["take"] - t.entry).abs() / t.risk
    print(t[["entree", "entry", "stop", "take", "sortie", "result", "net_r", "risk", "risk_atr15", "rr"]].round(2).to_string(index=False))
    h = pd.read_csv(HERE / "trades_principale.csv")
    print("\nDistribution historique (339 trades) pour situer :")
    for col, lab in (("risk_cac", "stop en pts CAC-eq"), ("risk_atr15", "stop en ATR15m"), ("rr_target", "R:R vise")):
        print(f"  {lab:20s} p10 {h[col].quantile(.1):.1f} | mediane {h[col].median():.1f} | p90 {h[col].quantile(.9):.1f}")
    for _, r in t.iterrows():
        pr = lambda col, v: (h[col] <= v).mean()
        print(f"  {r.entree}: stop {r.risk:.1f} pts = centile {pr('risk_cac', r.risk):.0%} ; {r.risk_atr15:.2f} ATR = centile "
              f"{pr('risk_atr15', r.risk_atr15):.0%} ; R:R {r.rr:.2f} = centile {pr('rr_target', r.rr):.0%}")
    cac = h[h.market == "CAC 40"]
    hr = h.hour
    print(f"\nTranche 15h30-17h30, tous marches : n={((hr >= 15.5) & (hr < 17.5)).sum()}, moy {h.net_r[(hr >= 15.5) & (hr < 17.5)].mean():+.3f}R ; "
          f"puts CAC : n={(cac.side == 'put').sum()}, moy {cac.net_r[cac.side == 'put'].mean():+.3f}R ; calls CAC : n={(cac.side == 'call').sum()}, "
          f"moy {cac.net_r[cac.side == 'call'].mean():+.3f}R")


if __name__ == "__main__":
    main()
