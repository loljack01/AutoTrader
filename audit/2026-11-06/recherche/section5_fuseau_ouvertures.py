"""Section 5 (fin) : (d) cohérence des fuseaux (heure locale des barres 1D cash et de la
1re barre 15m), (e) 15m vs 1D pour les futures US avec la bonne date de séance,
(f) effet des ouvertures fausses sur le swing (sorties « ouverture au-delà du stop »).
Usage : PYTHONDONTWRITEBYTECODE=1 python3 section5_fuseau_ouvertures.py"""
import sys; sys.dont_write_bytecode = True
REPO = "/home/user/AutoTrader"; sys.path.insert(0, REPO + "/scripts"); sys.path.insert(0, REPO)
import numpy as np, pandas as pd
import test_swing_rsi2 as sw
C = REPO + "/data/cache/"
def load(f):
    d = pd.read_csv(C + f, index_col=0); d.index = pd.to_datetime(d.index, utc=True)
    return d[~d.index.duplicated(keep="last")].sort_index()
TZ = {"EURONEXT_PX1": "Europe/Paris", "XETR_DAX": "Europe/Berlin", "TVC_SX5E": "Europe/Berlin", "SP_SPX": "America/New_York",
      "NASDAQ_NDX": "America/New_York", "TVC_UKX": "Europe/London", "SIX_SMI": "Europe/Zurich", "TVC_DJI": "America/New_York",
      "TVC_RUT": "America/New_York", "TVC_FTMIB": "Europe/Rome"}
print("(d) heure locale des barres 1D cash (2012 ->) :")
for s, tz in TZ.items():
    d = load(s + "_1D.csv"); d = d[d.index >= "2012"]
    h = pd.Series(d.index.tz_convert(tz).strftime("%H:%M")).value_counts()
    print(f"  {s:12s} {dict(h.head(3))}")
print("heure Paris de la 1re barre 15m de chaque jour (FCE1, ES1) :")
for f in ("FCE1", "ES1", "FDAX1"):
    m = load(f + "_15m.csv"); p = m.index.tz_convert("Europe/Paris")
    first = pd.Series(p).groupby(p.date).min().dt.strftime("%H:%M").value_counts()
    print(f"  {f}: {dict(first.head(4))}")
print("\n(e) futures US : 15m agregees (seance = heure NY + 6 h) vs 1D")
for fut in ("ES1", "NQ1", "YM1", "RTY1"):
    m = load(fut + "_15m.csv"); D = load(fut + "_1D.csv")
    m["s"] = (m.index + pd.Timedelta(hours=6)).tz_convert("America/New_York").date
    agg = m.groupby("s").agg(High=("High", "max"), Low=("Low", "min"), n=("High", "size"))
    D.index = (D.index + pd.Timedelta(hours=6)).tz_convert("America/New_York").date
    j = agg.join(D[["High", "Low", "Close"]], rsuffix="_1D", how="inner").iloc[1:-1]; j = j[j.n >= 60]
    tol = 0.0002 * j.Close
    print(f"  {fut}: {len(j)} seances, haut different {(np.abs(j.High-j.High_1D)>tol).mean():.0%}, bas different {(np.abs(j.Low-j.Low_1D)>tol).mean():.0%}")
print("\n(f) swing (regle de reference, sans limite) : sorties au stop et part sur ouverture au-dela du stop")
rows = []
for sym, name in sw.INDICES.items():
    d = sw.load(sym); a = tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "sma5", "atr"))
    o, h, l, c = a[0], a[1], a[2], a[3]
    t = sw.run(d, 1)
    nstop = ngap = 0; gap_extra = []
    for x in t.itertuples():
        i = d.index.get_loc(x.entry); j = d.index.get_loc(x.exit)
        risk = sw.STOP_ATR * a[5][i]; stop = c[i] - risk
        if l[j] <= stop and not c[j] > a[4][j] or (l[j] <= stop):
            if l[j] <= stop:
                nstop += 1
                if o[j] <= stop:
                    ngap += 1; gap_extra.append((stop - o[j]) / risk)
    stale = np.isclose(o[1:], c[:-1]).mean()
    rows.append((name, len(t), nstop, ngap, f"{ngap/max(nstop,1):.0%}", round(float(np.sum(gap_extra)), 2), f"{stale:.0%}"))
df = pd.DataFrame(rows, columns=["indice", "trades", "stops", "stops sur ouverture", "part", "R perdus en plus", "open=close veille"])
print(df.to_string(index=False))
eu = df[df.indice.isin(["CAC 40", "DAX", "Euro Stoxx 50", "FTSE MIB", "SMI"])]
rate = eu["stops sur ouverture"].sum() / eu.stops.sum(); per = eu["R perdus en plus"].sum() / max(eu["stops sur ouverture"].sum(), 1)
uk = df[df.indice == "FTSE 100"].iloc[0]
print(f"Estimation du biais FTSE 100 : {uk.stops} stops x {rate:.0%} (taux europeen) x {per:.2f}R = {uk.stops*rate*per:.1f}R surestimes")
