"""Audit trade par trade de la principale (sma20, suivi sans argent depuis le 28/10/2026).
Descriptif seulement : aucune regle n'est testee ni modifiee (moratoire du 06/11).

Pour chaque trade de data/backtests/frozen_15m_calls_trend_trades.csv (version sma20), relu sur
les bougies 15m de data/cache :
  duree, MFE (meilleur gain latent en R avant la sortie), MAE (pire perte latente en R),
  distance du stop en ATR(14) 15m (2,0 = stop minimal de la regle), objectif en R,
  sens par rapport a la tendance journaliere (SMA20), executable par un turbo (condition D : bougie
  d'entree commencant entre 8h00 et 21h15), heure du stop, et pour les stops : l'objectif a-t-il ete
  atteint dans les 48 h suivantes, et jusqu'ou le prix est-il alle contre le trade dans les 24 h.
Usage : python3 audit/2026-11-10/audit_trades_principale.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import MARKETS
from ma_grid_test import trend_up

OPENS = {(9, 0), (9, 15), (15, 30), (15, 45)}  # bougies des ouvertures cash Europe et Etats-Unis


def main():
    t = pd.read_csv(ROOT / "data" / "backtests" / "frozen_15m_calls_trend_trades.csv")
    s = t[t.version == "sma20"].copy()
    name2sym = {v[0]: k for k, v in MARKETS.items()}
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for mk, g in s.groupby("marche"):
        sym = name2sym[mk]
        d = bt.cache.closed_bars(bt.cache.load(sym, "15m"), "15m", now)
        idx = d.index.tz_convert("Europe/Paris")
        up = np.asarray(trend_up(sym, d, "SMA", 20), bool)
        h, l, c = d.High.to_numpy(), d.Low.to_numpy(), d.Close.to_numpy()
        tr = np.maximum.reduce([h - l, np.abs(h - np.roll(c, 1)), np.abs(np.roll(c, 1) - l)])
        atr = pd.Series(tr).rolling(14).mean().to_numpy()
        for x in g.itertuples():
            e = pd.Timestamp(f"2026/{x.entree_paris[3:5]}/{x.entree_paris[:2]} {x.entree_paris[6:]}", tz="Europe/Paris")
            i = np.flatnonzero(idx == e)[0]
            side = 1 if x.sens == "call" else -1
            risk = abs(x.entree - x.stop)
            mfe = mae = 0.0
            j_end = None
            for j in range(i + 1, len(d)):
                fav = (h[j] - x.entree) if side == 1 else (x.entree - l[j])
                adv = (x.entree - l[j]) if side == 1 else (h[j] - x.entree)
                stop = (l[j] <= x.stop) if side == 1 else (h[j] >= x.stop)
                take = (h[j] >= x.cible) if side == 1 else (l[j] <= x.cible)
                if not stop:
                    mfe = max(mfe, fav / risk)
                mae = max(mae, min(adv / risk, 1.0))
                if stop or take:
                    j_end = j
                    break
            if j_end is None:
                j_end_eff = len(d) - 1
            else:
                j_end_eff = j_end
            later_take, worse = False, np.nan
            if x.resultat == "stop":
                w = range(j_end + 1, min(len(d), j_end + 193))
                later_take = any((h[j] >= x.cible) if side == 1 else (l[j] <= x.cible) for j in w)
                w24 = range(j_end, min(len(d), j_end + 97))
                worse = max(((x.entree - l[j]) if side == 1 else (h[j] - x.entree)) / risk for j in w24)
            rows.append({
                "entree": e, "marche": mk, "sens": x.sens, "resultat": x.resultat,
                "net_r": x.net_r if x.resultat != "open" else np.nan,
                "objectif_r": abs(x.cible - x.entree) / risk, "stop_atr": risk / atr[i],
                "stop_pct": risk / x.entree * 100, "duree_h": (j_end_eff - i) * 0.25,
                "mfe": mfe, "mae": mae,
                "tendance": "avec" if (side == 1 or not up[i]) else "contre",
                "executable": 8 <= e.hour + e.minute / 60 < 21.5,
                "sortie": idx[j_end] if j_end is not None else pd.NaT,
                "a_l_ouverture": (j_end is not None and (idx[j_end].hour, idx[j_end].minute) in OPENS),
                "objectif_apres": later_take, "pire_24h": worse,
            })
    r = pd.DataFrame(rows).sort_values("entree").reset_index(drop=True)

    def cause(x):
        if x.resultat != "stop":
            return ""
        if x.mfe >= 1.0:
            return "parti dans le bon sens (>= 1R) puis retour au stop"
        if x.mfe >= 0.25:
            return "petit gain latent puis retournement"
        return "faux des le depart"
    r["cause"] = r.apply(cause, axis=1)
    pd.set_option("display.width", 320); pd.set_option("display.max_rows", 200)
    v = r.copy()
    v["entree"] = v.entree.dt.strftime("%d/%m %H:%M"); v["sortie"] = v.sortie.dt.strftime("%d/%m %H:%M")
    for k in ("net_r", "objectif_r", "stop_atr", "stop_pct", "mfe", "mae", "pire_24h"):
        v[k] = v[k].round(2)
    print(v.to_string(index=True))
    r.to_csv(Path(__file__).with_name("audit_trades_principale.csv"), index=False)

    cl = r[r.resultat != "open"]; ko = cl[cl.resultat == "stop"]; ok = cl[cl.resultat == "take"]
    print(f"\n{len(r)} trades : {len(ok)} OK, {len(ko)} KO, {len(r) - len(cl)} ouverts | net {cl.net_r.sum():+.2f}R, "
          f"plafonne 5R {np.minimum(cl.net_r, 5).sum():+.2f}R")
    srt = cl.net_r.sort_values(ascending=False)
    print(f"Concentration : les 2 meilleurs {srt.iloc[:2].sum():+.2f}R, les 4 meilleurs {srt.iloc[:4].sum():+.2f}R, "
          f"les {len(cl) - 4} autres {srt.iloc[4:].sum():+.2f}R")
    print(f"Gain moyen d'un OK {ok.net_r.mean():+.2f}R (objectif moyen {ok.objectif_r.mean():.1f}R) ; objectif moyen des KO "
          f"{ko.objectif_r.mean():.1f}R (median {ko.objectif_r.median():.1f}R) ; seuil d'equilibre {1 / (1 + ok.net_r.mean()):.0%}, reel {len(ok) / len(cl):.0%}")
    print("\nCauses des KO :")
    print(ko.cause.value_counts().to_string())
    print(f"\nKO stoppes sur une bougie d'ouverture (9h00, 9h15, 15h30, 15h45) : {int(ko.a_l_ouverture.sum())}/{len(ko)}")
    print(f"KO dont l'objectif est atteint dans les 48 h apres le stop : {int(ko.objectif_apres.sum())}/{len(ko)}")
    print(f"KO ou le prix va au moins 1R plus loin contre le trade dans les 24 h (signal vraiment faux) : "
          f"{int((ko.pire_24h >= 2).sum())}/{len(ko)}")
    print(f"Stop minimal (<= 2,05 ATR 15m) : KO {int((ko.stop_atr <= 2.05).sum())}/{len(ko)}, OK {int((ok.stop_atr <= 2.05).sum())}/{len(ok)} ; "
          f"stop median KO {ko.stop_pct.median():.2f} %, OK {ok.stop_pct.median():.2f} %")
    print(f"MFE des KO : median {ko.mfe.median():.2f}R ; >= 1R : {int((ko.mfe >= 1).sum())} ; >= 2R : {int((ko.mfe >= 2).sum())}")
    print(f"MAE des OK (pire latent avant le gain) : median {ok.mae.median():.2f}R ; >= 0,5R : {int((ok.mae >= 0.5).sum())}/{len(ok)}")

    def tab(key):
        g = cl.groupby(key, observed=True)
        o = pd.DataFrame({"n": g.size(), "OK": g.apply(lambda a: int((a.resultat == "take").sum())),
                          "net_R": g.net_r.sum().round(2), "plafonne_5R": g.apply(lambda a: round(np.minimum(a.net_r, 5).sum(), 2))})
        print(f"\nPar {key} :"); print(o.to_string())
    cl = cl.assign(tranche=pd.cut(cl.entree.dt.hour, [-1, 7, 11, 15, 19, 24], labels=["0-7h", "8-11h", "12-15h", "16-19h", "20-23h"]),
                   jour=cl.entree.dt.strftime("%d/%m"))
    for key in ("sens", "tendance", "executable", "tranche", "marche", "jour"):
        tab(key)


if __name__ == "__main__":
    main()
