"""Audit du 14/11/2026 : l'intraday (strategie principale) avec PLUSIEURS ORDRES SUR UN MEME
INDICE. Demande de l'utilisateur : "Refais un audit complet sur strategie intraday avec
plusieurs ordres sur un meme indice".

Aujourd'hui le moteur n'a qu'un trade ouvert a la fois par indice et par sens (un call et un
put peuvent coexister) et un seul ordre par signal. Mesures fixees ICI, AVANT tout calcul des
variantes (seul le controle de reproduction a tourne) ; rien n'est regle apres coup :

  Ordres simultanes (un signal qui arrive pendant qu'un trade du meme sens est ouvert sur le
  meme indice n'est plus ignore ; toujours un trade par balayage) :
    S2  jusqu'a 2 trades ouverts par indice et par sens
    S3  jusqu'a 3
    Sx  sans limite
  Plusieurs ordres par signal (memes entrees que la base, deux ordres de meme taille) :
    P1  sortie partielle : l'ordre A sort a +1R, l'ordre B garde la cible de la base ; stop
        d'origine pour les deux ; stop d'abord si une bougie touche le stop et +1R
    P2  renfort : a la premiere cloture a +1R ou mieux, un ordre B est ajoute a cette cloture,
        avec la cible de la base et un stop au prix d'entree de A ; resultat en R de A

Base : la principale telle que figee (SMA20 : calls avec la tendance, puts toujours), 10
marches, 15 minutes, frais de 1 point et de 3 points equivalent CAC. Les variantes S sont
aussi mesurees sur la partie executable en turbo (variante D : entrees 8h-21h30, sortie a
21h45 au plus tard). Deux periodes : avant le 28/10/2026 (historique, deja exploite, pour
information) et depuis le 28/10 (suivi). 8 hypotheses, inscrites au registre comme AUDIT
(information) : aucune ne peut etre adoptee sur ces chiffres ; une piste retenue devrait etre
figee puis suivie en avant.

Controle : le simulateur de cet audit, limite a 1 trade ouvert, doit redonner exactement les
trades du moteur (bt.backtest) sur les 10 marches, les deux sens, les deux niveaux de frais,
pour la principale et pour D.

Usage : python3 -W ignore audit/2026-11-14/ordres_multiples.py [--controle]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from finta import TA

import backtest_liquidity_sweep_buy as bt
from frozen_15m_calls_trend import FREEZE_START, MARKETS
from levels import liquidity, structure
from ma_grid_test import trend_up
from setups import session
from setups.net_r import net_rr

START = pd.Timestamp(FREEZE_START, tz="UTC")
D_KW = {"entry_hours": (8, 21.5), "session_exit": 21.75}
OUT = Path(__file__).resolve().parent / "ordres_multiples_trades.csv"


def prepare(d, side):
    """Everything bt.backtest computes before its loop (frozen settings: swings n=2, pools not consumed)."""
    n = len(d)
    atr = TA.ATR(d, 14)
    is_hi, is_lo = structure.find_swings(d, n=2)
    sh = structure.confirmed_level(is_hi, d.High, 2)
    sl = structure.confirmed_level(is_lo, d.Low, 2)
    bull, bear = structure.bos_events(d.Close, sh, sl)
    choch = structure.choch_events(bull, bear)
    trig = (choch & (bull if side == 1 else bear)).to_numpy()
    hi_marks = structure.confirmed_marks(is_hi, d.High, 2)
    lo_marks = structure.confirmed_marks(is_lo, d.Low, 2)
    eqh = liquidity.find_sweeps(liquidity.find_pools(hi_marks, atr), d, "high")
    eql = liquidity.find_sweeps(liquidity.find_pools(lo_marks, atr), d, "low")
    pos = {ts: i for i, ts in enumerate(d.index)}
    swept, targets = (eql, eqh) if side == 1 else (eqh, eql)
    ext = (d.Low if side == 1 else d.High).to_numpy()
    sweeps = {}
    for p in swept:
        if p["swept_at"] is not None:
            i = pos[p["swept_at"]]
            sweeps[i] = min(sweeps.get(i, np.inf), ext[i]) if side == 1 else max(sweeps.get(i, -np.inf), ext[i])
    tg = [(p["level"], pos[p["members"][1][0]], pos[p["swept_at"]] if p["swept_at"] is not None else n + 1)
          for p in targets]
    paris = d.index.tz_convert("Europe/Paris")
    date = paris.date
    return {"n": n, "atr": atr.to_numpy(), "trig": trig, "sweeps": sweeps, "tg": tg,
            "fallback": (hi_marks if side == 1 else lo_marks).ffill().to_numpy(),
            "O": d.Open.to_numpy(), "H": d.High.to_numpy(), "L": d.Low.to_numpy(), "C": d.Close.to_numpy(),
            "idx": d.index, "date": date, "hour": np.asarray(paris.hour + paris.minute / 60),
            "allowed": np.array([session.entry_allowed(session.session_window(t)) for t in paris]),
            "last_of_day": np.append(date[1:] != date[:-1], True)}


def simulate(P, side, mask, k, cost, max_open=1, entry_hours=None, session_exit=None):
    """bt.backtest's loop with up to `max_open` trades open at once (None = no limit)."""
    rt, margin = cost * k, 8.0 * k
    H, L, C, atr, idx, n = P["H"], P["L"], P["C"], P["atr"], P["idx"], P["n"]
    last_of_day = P["last_of_day"]
    if session_exit:
        cut = P["hour"] >= float(session_exit) - 0.25
        same_day = np.append(False, P["date"][1:] == P["date"][:-1])
        last_of_day = last_of_day | (cut & ~(np.append(False, cut[:-1]) & same_day))
    cap = np.inf if max_open is None else max_open
    trades, open_tr, last_sweep, used = [], [], None, set()

    def close(tr, i, price, result):
        risk = abs(tr["entry"] - tr["stop"])
        cr = rt / risk
        net = (abs(tr["take"] - tr["entry"]) / risk - cr if result == "take" else -(1.0 + cr) if result == "stop"
               else side * (price - tr["entry"]) / risk - cr)
        trades.append({**tr, "exit_i": i, "exit_time": idx[i], "result": result, "net_r": net})

    for i in range(n):
        if i in P["sweeps"]:
            last_sweep = (i, P["sweeps"][i])
        still = []
        for tr in open_tr:
            if side == 1:
                hit = "stop" if L[i] <= tr["stop"] else ("take" if H[i] >= tr["take"] else None)
            else:
                hit = "stop" if H[i] >= tr["stop"] else ("take" if L[i] <= tr["take"] else None)
            if hit:
                close(tr, i, tr["stop"] if hit == "stop" else tr["take"], hit)
            elif session_exit and last_of_day[i]:
                close(tr, i, C[i], "eod")
            else:
                still.append(tr)
        open_tr = still
        if len(open_tr) >= cap or last_sweep is None:
            continue
        si, sx = last_sweep
        if idx[i] - idx[si] > bt.CHOCH_WINDOW or si in used:
            continue
        if not P["trig"][si:i + 1].any() or not P["allowed"][i]:
            continue
        if entry_hours is not None and not (entry_hours[0] <= P["hour"][i] < entry_hours[1]):
            continue
        if session_exit and last_of_day[i]:
            continue
        if mask is not None and not mask[i]:
            continue
        c = float(C[i])
        risk = max((c - (sx - side * margin)) * side, 2.0 * atr[i] if not np.isnan(atr[i]) else 0.0)
        stop = c - side * risk
        lv = [lvl for lvl, conf, sw in P["tg"] if conf <= i and sw > i and (lvl - c) * side > 0]
        take = (min(lv) if side == 1 else max(lv)) if lv else P["fallback"][i]
        if take is None or np.isnan(take) or (take - c) * side <= 0:
            continue
        if net_rr(c, stop, take, rt) < 1.3:
            continue
        open_tr.append({"entry_i": i, "entry_time": idx[i], "sweep_time": idx[si], "entry": c, "stop": float(stop),
                        "take": float(take), "deja_ouverts": len(open_tr)})
        used.add(si)
    for tr in open_tr:
        trades.append({**tr, "exit_i": None, "exit_time": None, "result": "open", "net_r": np.nan})
    return pd.DataFrame(trades, columns=["entry_i", "entry_time", "sweep_time", "entry", "stop", "take", "deja_ouverts",
                                         "exit_i", "exit_time", "result", "net_r"])


def set_engine(k, cost):
    bt.ROUND_TRIP_COST, bt.MIN_RISK_ATR_MULT, bt.STOP_MARGIN = cost * k, 2.0, 8.0 * k
    bt.SWING_N, bt.MIN_NET_RR, bt.CHOCH_WINDOW = 2, 1.3, pd.Timedelta(hours=4)


def split_orders(t, P, side, k, cost):
    """P1 and P2 on the base trades of one market and side (closed trades only)."""
    H, L, C = P["H"], P["L"], P["C"]
    p1, p2, added = [], [], []
    for x in t.itertuples():
        if x.result == "open":
            p1.append(np.nan), p2.append(np.nan), added.append(False)
            continue
        risk = abs(x.entry - x.stop)
        cr = cost * k / risk
        lvl = x.entry + side * risk
        a, b, add_i = x.net_r, 0.0, None
        for j in range(x.entry_i + 1, x.exit_i + 1):
            stop_hit = L[j] <= x.stop if side == 1 else H[j] >= x.stop
            if stop_hit:
                break
            if (H[j] >= lvl) if side == 1 else (L[j] <= lvl):
                a = 1.0 - cr
                break
        for j in range(x.entry_i + 1, x.exit_i):
            if (C[j] - lvl) * side >= 0 and (x.take - C[j]) * side > 0:
                add_i = j
                break
        if add_i is not None:
            eb = C[add_i]
            pnl = None
            for j in range(add_i + 1, x.exit_i + 1):
                if (L[j] <= x.entry) if side == 1 else (H[j] >= x.entry):
                    pnl = side * (x.entry - eb)
                    break
                if (H[j] >= x.take) if side == 1 else (L[j] <= x.take):
                    pnl = side * (x.take - eb)
                    break
            if pnl is None:
                pnl = side * (C[x.exit_i] - eb)
            b = pnl / risk - cr
        p1.append(0.5 * (a + x.net_r)), p2.append(x.net_r + b), added.append(add_i is not None)
    return p1, p2, added


def load():
    now = pd.Timestamp.now(tz="UTC")
    return {s: bt.cache.closed_bars(bt.cache.load(s, "15m"), "15m", now) for s in MARKETS}


def controle(data):
    bad = 0
    cols = ["entry_time", "entry", "stop", "take", "exit_time", "result", "net_r"]
    for s, d in data.items():
        k = MARKETS[s][1]
        up = trend_up(s, d, "SMA", 20)
        for side, direction, mask in ((1, "buy", up), (-1, "sell", None)):
            P = prepare(d, side)
            for cost in (1.0, 3.0):
                for kw in ({}, D_KW):
                    set_engine(k, cost)
                    ref = bt.backtest(d, True, False, direction=direction, entry_mask=mask, **kw)[cols]
                    got = simulate(P, side, mask, k, cost, 1, **kw)[cols]
                    when = lambda t, c: pd.to_datetime(t[c], utc=True).fillna(pd.Timestamp(0, tz="UTC")).to_numpy()
                    same = len(ref) == len(got) and (ref.result.to_numpy() == got.result.to_numpy()).all() and all(
                        (when(ref, c) == when(got, c)).all() for c in ("entry_time", "exit_time")) and np.allclose(
                        ref[["entry", "stop", "take", "net_r"]].to_numpy(float),
                        got[["entry", "stop", "take", "net_r"]].to_numpy(float), equal_nan=True)
                    bad += not same
                    if not same:
                        print(f"  DIFFERENT : {s} {direction} frais {cost} {'D' if kw else 'principale'} "
                              f"({len(ref)} vs {len(got)} trades)")
    n = len(data) * 2 * 2 * 2
    print(f"Controle de reproduction : {n - bad}/{n} configurations identiques au moteur -> {'OK' if not bad else 'ECHEC'}")
    return not bad


def stats(t, col="net_r"):
    c = t[t.result != "open"]
    r = c[col].to_numpy(float)
    if not len(r):
        return "0 trade"
    day = pd.Series(r, index=pd.to_datetime(c.exit_time, utc=True).dt.tz_convert("Europe/Paris").dt.date.to_numpy()).groupby(level=0).sum()
    cum = pd.Series(r, index=pd.to_datetime(c.exit_time, utc=True).to_numpy()).sort_index().cumsum()
    dd = (cum - cum.cummax().clip(lower=0)).min()
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    t_stat = r.mean() / (sd / np.sqrt(len(r))) if sd > 0 else 0.0
    return (f"{len(r):4d} trades, {int((r > 0).sum()):3d} gagnants, net {r.sum():+7.2f}R (moy {r.mean():+.3f}, t {t_stat:+.2f}), "
            f"plafond 5R {np.minimum(r, 5).sum():+7.2f}R, pire jour {day.min():+.2f}R, jours <= -3R {int((day <= -3).sum()):2d}, "
            f"pire creux {dd:+.2f}R")


def main():
    data = load()
    if not controle(data) or "--controle" in sys.argv:
        return
    paris = lambda ts: "" if ts is None or pd.isna(ts) else pd.Timestamp(ts).tz_convert("Europe/Paris").strftime("%d/%m/%Y %H:%M")
    runs = {}  # (config, cap, cost) -> trades of the 10 markets
    for s, d in data.items():
        k = MARKETS[s][1]
        up = trend_up(s, d, "SMA", 20)
        for side, mask in ((1, up), (-1, None)):
            P = prepare(d, side)
            for cost in (1.0, 3.0):
                for cfg, kw in (("principale", {}), ("D", D_KW)):
                    for cap in (1, 2, 3, None):
                        t = simulate(P, side, mask, k, cost, cap, **kw)
                        t = t.assign(marche=MARKETS[s][0], sens="call" if side == 1 else "put")
                        if cfg == "principale" and cap == 1:
                            t["p1"], t["p2"], t["renfort"] = split_orders(t, P, side, k, cost)
                            t["stop_pct"] = (t.entry - t.stop).abs() / t.entry * 100
                        runs.setdefault((cfg, cap, cost), []).append(t)
    runs = {key: pd.concat(v, ignore_index=True) for key, v in runs.items()}
    periods = (("avant le 28/10 (historique, information)", lambda t: t[t.entry_time < START]),
               ("depuis le 28/10 (suivi)", lambda t: t[t.entry_time >= START]))
    name = {1: "base (1 a la fois)", 2: "S2 (2 max)", 3: "S3 (3 max)", None: "Sx (sans limite)"}

    base = runs["principale", 1, 1.0]
    print("\n== 1. Etat des lieux (base, frais 1 pt) ==")
    b = base.assign(jour=base.entry_time.dt.tz_convert("Europe/Paris").dt.date)
    per = b.groupby(["marche", "jour"]).size()
    print(f"  {len(b)} trades ; jours x indice avec au moins un trade : {len(per)} ; avec 1 trade {int((per == 1).sum())}, "
          f"2 trades {int((per == 2).sum())}, 3 ou plus {int((per >= 3).sum())} (maximum {per.max()})")
    c = b[b.result != "open"]
    hours = (c.exit_time - c.entry_time).dt.total_seconds() / 3600
    print(f"  duree d'un trade clos : mediane {hours.median():.1f} h, quart {hours.quantile(.25):.1f} h, trois quarts "
          f"{hours.quantile(.75):.1f} h, maximum {hours.max() / 24:.1f} jours")
    sx = runs["principale", None, 1.0]
    for label, f in periods:
        a, x = f(base), f(sx)
        print(f"  {label} : {len(a)} trades dans la base, {len(x)} sans limite, dont {int((x.deja_ouverts >= 1).sum())} "
              f"pris pendant qu'un trade du meme sens etait ouvert ; maximum ouverts en meme temps "
              f"{int(x.deja_ouverts.max()) + 1 if len(x) else 0}")

    print("\n== 2. Ordres simultanes ==")
    for cfg in ("principale", "D"):
        for cost in (1.0, 3.0):
            print(f"  -- {cfg}, frais {cost:.0f} pt --")
            for label, f in periods:
                print(f"   {label}")
                for cap in (1, 2, 3, None):
                    print(f"     {name[cap]:20s} {stats(f(runs[cfg, cap, cost]))}")
    print("  -- les trades AJOUTES seuls (pris pendant qu'un autre du meme sens etait ouvert, sans limite) --")
    for cfg in ("principale", "D"):
        for cost in (1.0, 3.0):
            for label, f in periods:
                x = f(runs[cfg, None, cost])
                print(f"   {cfg:10s} {cost:.0f} pt, {label} : {stats(x[x.deja_ouverts >= 1])}")
    x = sx[(sx.deja_ouverts >= 1) & (sx.result != "open")]
    print(f"  sort des trades ajoutes (principale, 1 pt, tout l'historique) : stop {int((x.result == 'stop').sum())}, "
          f"cible {int((x.result == 'take').sum())} ; par sens : calls {stats(x[x.sens == 'call'])}")
    print(f"                                                                    puts  {stats(x[x.sens == 'put'])}")

    print("\n== 3. Plusieurs ordres par signal (memes entrees que la base) ==")
    for cost in (1.0, 3.0):
        t = runs["principale", 1, cost]
        print(f"  -- frais {cost:.0f} pt --")
        for label, f in periods:
            p = f(t)
            print(f"   {label}")
            print(f"     base (un ordre)            {stats(p)}")
            print(f"     P1 sortie partielle a +1R  {stats(p, 'p1')}")
            print(f"     P2 renfort a +1R           {stats(p, 'p2')}   (renforts poses : {int(p.renfort.sum())})")
    c = base[base.result != "open"]
    reached = c[(c.p1 - c.net_r).abs() > 1e-9]
    print(f"  trades clos ayant atteint +1R avant leur sortie (1 pt) : {len(reached)} sur {len(c)} "
          f"({len(reached) / len(c):.0%}) ; parmi eux, finis au stop : {int((reached.result == 'stop').sum())}, "
          f"a la cible : {int((reached.result == 'take').sum())}")

    print("\n== 4. Taille et risque en turbo (base, frais 1 pt) ==")
    q = base.stop_pct.quantile([.25, .5, .75])
    print(f"  distance du stop : quart {q[.25]:.2f} %, mediane {q[.5]:.2f} %, trois quarts {q[.75]:.2f} %")
    for lev in (2.8, 5.0, 10.0):
        print(f"  ordre de 500 EUR, levier {lev:>4} : perte au stop quart {5 * lev * q[.25]:.1f} EUR, mediane "
              f"{5 * lev * q[.5]:.1f} EUR, trois quarts {5 * lev * q[.75]:.1f} EUR")
    med = base.groupby("marche").stop_pct.median()
    print("  mediane par marche : " + ", ".join(f"{m} {v:.2f} %" for m, v in med.items()))
    cost_r = (1.0 * base.marche.map({v[0]: v[1] for v in MARKETS.values()}) / (base.entry - base.stop).abs())
    print(f"  frais d'un aller-retour en part du risque : 1 pt = {cost_r.median():.3f}R (mediane), 3 pt = {3 * cost_r.median():.3f}R")

    rows = []
    for (cfg, cap, cost), t in runs.items():
        if cost != 1.0:
            continue
        for x in t.itertuples():
            rows.append({"config": cfg, "limite": "sans" if cap is None else cap, "marche": x.marche, "sens": x.sens,
                         "entree_paris": paris(x.entry_time), "entree": x.entry, "stop": round(x.stop, 2),
                         "cible": round(x.take, 2), "deja_ouverts": x.deja_ouverts, "sortie_paris": paris(x.exit_time),
                         "resultat": x.result, "net_r": None if x.result == "open" else round(x.net_r, 3)})
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nDetail (frais 1 pt) : {OUT.name}")


if __name__ == "__main__":
    main()
