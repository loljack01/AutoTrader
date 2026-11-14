"""Audit du 14/11/2026, suite : la regle d'ALTERNANCE de l'utilisateur sur un meme indice.
"Il ne peut y avoir 2 calls en meme temps et 2 puts en meme temps. Si on est en call, derriere
on fait un put. Si on a un put, derriere on fait un call."

Appliquee aux signaux de la strategie principale (15 minutes, SMA20, 10 marches), sans rien
changer d'autre. Mesures fixees ICI, AVANT tout calcul (seul le controle de reproduction a
tourne) ; rien n'est regle apres coup :

  A    alternance stricte : sur un indice, un signal n'est pris que s'il est de sens oppose au
       dernier trade pris sur cet indice (le premier trade est libre)
  Aj   alternance remise a zero chaque jour : meme regle, mais le premier trade de chaque
       journee (heure de Paris) est libre
  R    retournement : quand un signal de sens oppose est pris alors qu'un trade est ouvert,
       ce trade est ferme a la cloture de la bougie du signal
  A+R  alternance stricte et retournement (une seule position a la fois sur l'indice)
  Aj+R alternance du jour et retournement

Si un call et un put sont possibles sur la meme bougie, seul celui dont le balayage est le
plus recent est pris. Mesure sur la principale et sur sa partie executable en turbo (D :
entrees 8h-21h30, sortie a 21h45 au plus tard), frais de 1 et 3 points equivalent CAC, deux
periodes (avant le 28/10/2026 : historique deja exploite, information ; depuis le 28/10 :
suivi). 10 hypotheses, inscrites au registre comme AUDIT (information) : aucune ne peut etre
adoptee sur ces chiffres.

Controle : le simulateur a deux sens de cet audit, sans alternance ni retournement, doit
redonner exactement les trades du moteur (bt.backtest, calls + puts).

Usage : python3 -W ignore audit/2026-11-14/alternance.py [--controle]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from ordres_multiples import D_KW, MARKETS, START, bt, load, net_rr, prepare, set_engine, stats, trend_up

OUT = Path(__file__).resolve().parent / "alternance_trades.csv"
COLS = ["side", "entry_i", "entry_time", "sweep_time", "entry", "stop", "take", "exit_i", "exit_time", "result", "net_r"]
VARIANTS = {"base": (None, False), "A alternance stricte": ("strict", False), "Aj alternance du jour": ("day", False),
            "R retournement": (None, True), "A+R": ("strict", True), "Aj+R": ("day", True)}


def simulate_joint(P, mask, k, cost, alternate=None, reverse=False, entry_hours=None, session_exit=None):
    """Calls and puts of one market in a single loop, with the alternation / reversal rules."""
    rt, margin = cost * k, 8.0 * k
    A = P[1]
    H, L, C, atr, idx, n, date, hour = A["H"], A["L"], A["C"], A["atr"], A["idx"], A["n"], A["date"], A["hour"]
    last_of_day = A["last_of_day"]
    if session_exit:
        cut = hour >= float(session_exit) - 0.25
        same_day = np.append(False, date[1:] == date[:-1])
        last_of_day = last_of_day | (cut & ~(np.append(False, cut[:-1]) & same_day))
    trades = []
    open_tr, last_sweep, used = {1: None, -1: None}, {1: None, -1: None}, {1: set(), -1: set()}
    last_dir = last_day = None

    def close(s, i, price, result):
        tr = open_tr[s]
        risk = abs(tr["entry"] - tr["stop"])
        cr = rt / risk
        net = (abs(tr["take"] - tr["entry"]) / risk - cr if result == "take" else -(1.0 + cr) if result == "stop"
               else s * (price - tr["entry"]) / risk - cr)
        trades.append({**tr, "exit_i": i, "exit_time": idx[i], "result": result, "net_r": net})
        open_tr[s] = None

    for i in range(n):
        for s in (1, -1):
            if i in P[s]["sweeps"]:
                last_sweep[s] = (i, P[s]["sweeps"][i])
        for s in (1, -1):
            tr = open_tr[s]
            if tr is None:
                continue
            if s == 1:
                hit = "stop" if L[i] <= tr["stop"] else ("take" if H[i] >= tr["take"] else None)
            else:
                hit = "stop" if H[i] >= tr["stop"] else ("take" if L[i] <= tr["take"] else None)
            if hit:
                close(s, i, tr["stop"] if hit == "stop" else tr["take"], hit)
            elif session_exit and last_of_day[i]:
                close(s, i, C[i], "eod")
        cands = []
        for s in (1, -1):
            if open_tr[s] is not None or last_sweep[s] is None:
                continue
            si, sx = last_sweep[s]
            if idx[i] - idx[si] > bt.CHOCH_WINDOW or si in used[s]:
                continue
            if not P[s]["trig"][si:i + 1].any() or not A["allowed"][i]:
                continue
            if entry_hours is not None and not (entry_hours[0] <= hour[i] < entry_hours[1]):
                continue
            if session_exit and last_of_day[i]:
                continue
            if s == 1 and mask is not None and not mask[i]:
                continue
            c = float(C[i])
            risk = max((c - (sx - s * margin)) * s, 2.0 * atr[i] if not np.isnan(atr[i]) else 0.0)
            stop = c - s * risk
            lv = [lvl for lvl, conf, sw in P[s]["tg"] if conf <= i and sw > i and (lvl - c) * s > 0]
            take = (min(lv) if s == 1 else max(lv)) if lv else P[s]["fallback"][i]
            if take is None or np.isnan(take) or (take - c) * s <= 0:
                continue
            if net_rr(c, stop, take, rt) < 1.3:
                continue
            cands.append((s, si, c, float(stop), float(take)))
        if (alternate or reverse) and len(cands) == 2:
            cands = [max(cands, key=lambda x: x[1])] if cands[0][1] != cands[1][1] else []
        for s, si, c, stop, take in cands:
            if alternate:
                ld = None if (alternate == "day" and last_day != date[i]) else last_dir
                if ld == s:
                    continue
            if reverse and open_tr[-s] is not None:
                close(-s, i, C[i], "retourne")
            open_tr[s] = {"side": s, "entry_i": i, "entry_time": idx[i], "sweep_time": idx[si], "entry": c,
                          "stop": stop, "take": take}
            used[s].add(si)
            last_dir, last_day = s, date[i]
    for s in (1, -1):
        if open_tr[s] is not None:
            trades.append({**open_tr[s], "exit_i": None, "exit_time": None, "result": "open", "net_r": np.nan})
    return pd.DataFrame(trades, columns=COLS).sort_values(["entry_time", "side"]).reset_index(drop=True)


def controle(data):
    bad = 0
    cols = ["entry_time", "entry", "stop", "take", "exit_time", "result", "net_r"]
    when = lambda t, c: pd.to_datetime(t[c], utc=True).fillna(pd.Timestamp(0, tz="UTC")).to_numpy()
    for s, d in data.items():
        k = MARKETS[s][1]
        up = trend_up(s, d, "SMA", 20)
        P = {1: prepare(d, 1), -1: prepare(d, -1)}
        for cost in (1.0, 3.0):
            for kw in ({}, D_KW):
                set_engine(k, cost)
                ref = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up, **kw).assign(side=1),
                                 bt.backtest(d, True, False, direction="sell", **kw).assign(side=-1)])
                ref = ref.sort_values(["entry_time", "side"]).reset_index(drop=True)
                got = simulate_joint(P, up, k, cost, **kw)
                same = (len(ref) == len(got) and (ref.side.to_numpy() == got.side.to_numpy()).all()
                        and (ref.result.to_numpy() == got.result.to_numpy()).all()
                        and all((when(ref, c) == when(got, c)).all() for c in ("entry_time", "exit_time"))
                        and np.allclose(ref[["entry", "stop", "take", "net_r"]].to_numpy(float),
                                        got[["entry", "stop", "take", "net_r"]].to_numpy(float), equal_nan=True))
                bad += not same
                if not same:
                    print(f"  DIFFERENT : {s} frais {cost} {'D' if kw else 'principale'} ({len(ref)} vs {len(got)} trades)")
    n = len(data) * 2 * 2
    print(f"Controle de reproduction : {n - bad}/{n} configurations identiques au moteur -> {'OK' if not bad else 'ECHEC'}")
    return not bad


def main():
    data = load()
    if not controle(data) or "--controle" in sys.argv:
        return
    paris = lambda ts: "" if ts is None or pd.isna(ts) else pd.Timestamp(ts).tz_convert("Europe/Paris").strftime("%d/%m/%Y %H:%M")
    runs = {}
    for s, d in data.items():
        k = MARKETS[s][1]
        up = trend_up(s, d, "SMA", 20)
        P = {1: prepare(d, 1), -1: prepare(d, -1)}
        for cost in (1.0, 3.0):
            for cfg, kw in (("principale", {}), ("D", D_KW)):
                for name, (alt, rev) in VARIANTS.items():
                    t = simulate_joint(P, up, k, cost, alt, rev, **kw).assign(marche=MARKETS[s][0])
                    runs.setdefault((cfg, name, cost), []).append(t)
    runs = {key: pd.concat(v, ignore_index=True) for key, v in runs.items()}
    periods = (("avant le 28/10 (historique, information)", lambda t: t[t.entry_time < START]),
               ("depuis le 28/10 (suivi)", lambda t: t[t.entry_time >= START]))

    base = runs["principale", "base", 1.0]
    print("\n== 1. Etat des lieux (base, frais 1 pt) ==")
    b = base.sort_values(["marche", "entry_time"])
    prev = b.groupby("marche").side.shift()
    same_dir = (b.side == prev) & prev.notna()
    print(f"  {len(b)} trades ; de meme sens que le trade precedent sur le meme indice : {int(same_dir.sum())} "
          f"({same_dir.sum() / prev.notna().sum():.0%}) ; de sens oppose : {int((~same_dir & prev.notna()).sum())}")
    print(f"  calls {int((b.side == 1).sum())}, puts {int((b.side == -1).sum())}")
    both = 0
    for _, g in b.groupby("marche"):
        calls, puts = g[g.side == 1], g[g.side == -1]
        end = lambda x: x.exit_time.fillna(pd.Timestamp.now(tz="UTC"))
        for c in calls.itertuples():
            ce = c.exit_time if c.exit_time is not None and not pd.isna(c.exit_time) else pd.Timestamp.now(tz="UTC")
            both += int(((puts.entry_time < ce) & (end(puts) > c.entry_time)).sum())
    print(f"  paires call + put ouvertes en meme temps sur le meme indice : {both}")
    for label, f in periods:
        x = f(b)
        sd = f(b[same_dir])
        print(f"  {label} : trades de meme sens que le precedent : {stats(sd)}")
        print(f"  {'':{len(label)}s}   trades de sens oppose ou premiers  : {stats(x[~x.index.isin(sd.index)])}")

    print("\n== 2. Alternance et retournement ==")
    for cfg in ("principale", "D"):
        for cost in (1.0, 3.0):
            print(f"  -- {cfg}, frais {cost:.0f} pt --")
            for label, f in periods:
                print(f"   {label}")
                for name in VARIANTS:
                    print(f"     {name:22s} {stats(f(runs[cfg, name, cost]))}")

    print("\n== 3. Les trades retournes (principale, frais 1 pt, variante R) ==")
    r = runs["principale", "R retournement", 1.0]
    key = lambda t: t.marche + "|" + t.side.astype(str) + "|" + t.entry_time.astype(str)
    bnet = dict(zip(key(base), base.net_r))
    bres = dict(zip(key(base), base.result))
    for label, f in periods:
        x = f(r[r.result == "retourne"])
        kx = key(x)
        m = kx.isin(bnet.keys()) & kx.map(bres).ne("open")
        print(f"  {label} : {len(x)} trades fermes par retournement, net {x.net_r.sum():+.2f}R ; les memes trades dans la base "
              f"({int(m.sum())} retrouves, clos) : {kx[m].map(bnet).sum():+.2f}R contre {x.net_r[m].sum():+.2f}R retournes")

    rows = []
    for (cfg, name, cost), t in runs.items():
        if cost != 1.0:
            continue
        for x in t.itertuples():
            rows.append({"config": cfg, "variante": name, "marche": x.marche, "sens": "call" if x.side == 1 else "put",
                         "entree_paris": paris(x.entry_time), "entree": x.entry, "stop": round(x.stop, 2),
                         "cible": round(x.take, 2), "sortie_paris": paris(x.exit_time), "resultat": x.result,
                         "net_r": None if x.result == "open" else round(x.net_r, 3)})
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nDetail (frais 1 pt) : {OUT.name}")


if __name__ == "__main__":
    main()
