"""Audit marche 06/11/2026 - section 3 : swing RSI(2) par regime, DESCRIPTIF.
Carnet de reference : swing_portfolio.select_book(rsi2_candidates(data, 2012 -> 2100), 5),
R net a 0,05 %. Decoupages : distance a la SMA200, VIX(J-1) en quintiles, mois, semaines
de krach (indice < -5 % sur 5 seances a l'entree), signaux dans les 10 seances apres un
jour Nasdaq 100 < -5 %, part US / Europe. Chaque decoupage donne aussi la part
developpement (2012-2021) et periode reservee (2022+) : rien ici n'est un test de regle.

Usage: PYTHONDONTWRITEBYTECODE=1 python3 /home/user/AutoTrader/audit/2026-11-06/marche/swing_regimes.py
"""
import sys
from pathlib import Path

REPO = Path("/home/user/AutoTrader")
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

import swing_portfolio as sp
import test_swing_rsi2 as sw

HERE = Path(__file__).resolve().parent
US = {"SP:SPX", "NASDAQ:NDX", "TVC:DJI", "TVC:RUT"}


def line(lab, x, extra=""):
    x = np.asarray(x, float)
    if len(x) < 2:
        print(f"  {lab:26s} n={len(x)}")
        return
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    print(f"  {lab:26s} n={len(x):4d} moy {x.mean():+.3f}R total {x.sum():+6.1f}R gagn {np.mean(x > 0):.0%} t={t:+.2f}{extra}")


def split(b, m):
    dv, rs = b.entry < sp.ts("2022-01-01"), b.entry >= sp.ts("2022-01-01")
    return f" | dev {b.r[m & dv].sum():+.1f}R/{(m & dv).sum()} ; 2022+ {b.r[m & rs].sum():+.1f}R/{(m & rs).sum()}"


def main():
    data = sp.load_all()
    assert sp.check_reference(data)
    b = sp.select_book(sp.rsi2_candidates(data, ("2012-01-01", "2100-01-01")), 5)
    vix = pd.read_csv(REPO / "data/cache/TVC_VIX_1D.csv", index_col=0, parse_dates=True)
    vix.index = pd.to_datetime(vix.index, utc=True).normalize()
    vix = vix.Close[~vix.index.duplicated(keep="last")].sort_index()
    feats = []
    for _, r in b.iterrows():
        d = data[r.sym]
        dn = d.index.normalize()
        i = int(np.flatnonzero(dn == r.entry)[0])
        c = d.Close.iloc[i]
        v = vix[vix.index < r.entry]
        feats.append({"dist200": c / d.sma200.iloc[i] - 1, "ret5": c / d.Close.iloc[i - 5] - 1,
                      "vix_prev": v.iloc[-1] if len(v) else np.nan, "rsi2": d.rsi2.iloc[i]})
    b = pd.concat([b, pd.DataFrame(feats)], axis=1)
    b["us"] = b.sym.isin(US)
    b["market"] = b.sym.map(sw.INDICES)
    b.to_csv(HERE / "swing_book.csv", index=False)
    print(f"Carnet swing 5 positions : {len(b)} trades {b.entry.min():%d/%m/%Y} -> {b.exit.max():%d/%m/%Y}, "
          f"total {b.r.sum():+.1f}R, moy {b.r.mean():+.3f}R")

    print("\n--- Distance a la SMA200 a l'entree")
    bins = [0, 0.02, 0.05, 0.10, 1]
    b["d200"] = pd.cut(b.dist200, bins, labels=["0-2 %", "2-5 %", "5-10 %", ">10 %"])
    for g in b.d200.cat.categories:
        m = b.d200 == g
        line(g, b.r[m], split(b, m))

    print("\n--- VIX de la veille, quintiles")
    b["vq"] = pd.qcut(b.vix_prev, 5)
    for g in b.vq.cat.categories:
        m = b.vq == g
        line(str(g), b.r[m], split(b, m))
    for thr in (25, 30):
        m = b.vix_prev > thr
        line(f"VIX > {thr}", b.r[m], split(b, m))

    print("\n--- Mois d'entree")
    for mth in range(1, 13):
        m = b.entry.dt.month == mth
        line(f"mois {mth:02d}", b.r[m])
    mon = b.groupby(b.entry.dt.month).r.mean()
    print(f"  ecart-type des moyennes mensuelles {mon.std():.3f}R ; erreur type attendue d'un mois ~{b.r.std() / np.sqrt(len(b) / 12):.3f}R (bruit)")

    print("\n--- Semaine de krach : l'indice a perdu > 5 % sur 5 seances a l'entree")
    for lab, m in (("krach (ret5 < -5 %)", b.ret5 < -0.05), ("ret5 -5 a -3 %", (b.ret5 >= -0.05) & (b.ret5 < -0.03)), ("ret5 >= -3 %", b.ret5 >= -0.03)):
        line(lab, b.r[m], split(b, m))

    print("\n--- Apres un jour Nasdaq 100 < -5 % (cloture/cloture), signaux du carnet dans les 10 seances suivantes")
    ndx = data["NASDAQ:NDX"]
    ret = ndx.Close.pct_change()
    crash = ndx.index[(ret < -0.05) & (ndx.index >= sp.ts("2012-01-01"))]
    days = ndx.index.normalize()
    rows = []
    for cd in crash:
        i = int(np.flatnonzero(ndx.index == cd)[0])
        w0, w1 = days[i], days[min(i + 10, len(days) - 1)]
        m = (b.entry > w0) & (b.entry <= w1)
        rows.append((w0.date(), ret.loc[cd], m.sum(), b.r[m].sum(), ", ".join(f"{x.market} {x.r:+.2f}" for _, x in b[m].iterrows())))
    for r in rows:
        print(f"  {r[0]} NDX {r[1]:+.1%} : {r[2]} trades, {r[3]:+.2f}R  [{r[4]}]")
    allm = np.zeros(len(b), bool)
    for cd in crash:
        i = int(np.flatnonzero(ndx.index == cd)[0])
        allm |= ((b.entry > days[i]) & (b.entry <= days[min(i + 10, len(days) - 1)])).to_numpy()
    line("dans les 10 j apres", b.r[allm])
    line("autres trades", b.r[~allm])
    # 05/11/2026 : signaux du jour (le 05/11 est-il dans le cache cash ?)
    last = {s: d.index[-1].date() for s, d in data.items()}
    print(f"  derniere seance cash en cache par indice : {sorted(set(last.values()))}")
    for s, d in data.items():
        x = d.iloc[-1]
        print(f"    {sw.INDICES[s]:14s} {d.index[-1].date()} close {x.Close:.1f} RSI2 {x.rsi2:5.1f} > SMA200 {bool(x.Close > x.sma200)} "
              f"dist {x.Close / x.sma200 - 1:+.1%}")

    print("\n--- Part US / Europe")
    for lab, m in (("US (SPX, NDX, DJI, RUT)", b.us), ("Europe (6 indices)", ~b.us)):
        line(lab, b.r[m], split(b, m))
    print(f"  part du gain total venant des US : {b.r[b.us].sum() / b.r.sum():.0%} pour {b.us.mean():.0%} des trades")
    for s, g in b.groupby("market"):
        print(f"    {s:14s} n={len(g):4d} total {g.r.sum():+6.1f}R moy {g.r.mean():+.3f}R")
    lo = b.r[b.r < -1.10]
    print(f"\nSorties pires que -1,10R (ouverture au-dela du stop ; le cout seul fait ~-1,02R) : {len(lo)} trades, pire {b.r.min():+.2f}R, "
          f"surcout total au-dela de -1,02R {(lo + 1.02).sum():+.1f}R ; pires : " + ", ".join(f"{x.market} {x.exit:%d/%m/%Y} {x.r:+.2f}" for _, x in b[b.r < -1.10].sort_values('r').head(6).iterrows()))
    print(f"  dont sorties un lundi (ecart de week-end) : {(b[b.r < -1.10].exit.dt.dayofweek == 0).sum()}")
    cac = data["EURONEXT:PX1"].iloc[-1]
    print(f"CAC cash 05/11 : cloture {cac.Close:.1f}, SMA200 {cac.sma200:.1f}")


if __name__ == "__main__":
    main()
