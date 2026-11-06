"""Section 5 (suite) : (a) futures vs cash avec la date de séance correcte (barres
futures US datées la veille à 18h ET) ; (b) 15m agrégées vs 1D du même future ;
(c) 15m reconstruites depuis le 1m vs 15m officielles, et effet sur la principale (CAC).
Usage : PYTHONDONTWRITEBYTECODE=1 python3 section5_suite.py"""
import sys; sys.dont_write_bytecode = True
import numpy as np, pandas as pd
C = "/home/user/AutoTrader/data/cache/"
def load(f):
    d = pd.read_csv(C + f, index_col=0); d.index = pd.to_datetime(d.index, utc=True)
    return d[~d.index.duplicated(keep="last")].sort_index()
CASH = {"EURONEXT_PX1": ("FCE1", "Europe/Paris"), "XETR_DAX": ("FDAX1", "Europe/Berlin"), "TVC_SX5E": ("FESX1", "Europe/Berlin"),
        "SP_SPX": ("ES1", "America/New_York"), "NASDAQ_NDX": ("NQ1", "America/New_York"), "TVC_UKX": ("ICEEUR_Z1", "Europe/London"),
        "SIX_SMI": ("FSMI1", "Europe/Zurich"), "TVC_DJI": ("YM1", "America/New_York"), "TVC_RUT": ("RTY1", "America/New_York"),
        "TVC_FTMIB": ("FIB1", "Europe/Rome")}
sd = lambda idx, tz: (idx + pd.Timedelta(hours=12)).tz_convert(tz).date
print("(a) futures vs cash, date de seance = (horodatage + 12 h) en heure locale, 2012 ->")
for cash, (fut, tz) in CASH.items():
    a, b = load(cash + "_1D.csv"), load(fut + "_1D.csv")
    a.index, b.index = sd(a.index, tz), sd(b.index, tz)
    a = a[~a.index.duplicated()]; b = b[~b.index.duplicated()]
    j = pd.concat([a.Close.pct_change(), b.Close.pct_change()], axis=1, keys=["cash", "fut"]).dropna()
    j = j[pd.to_datetime(j.index) >= "2012-01-01"]
    big = np.abs(j.cash - j.fut) > 0.02
    print(f"  {cash:12s}/{fut:10s} {len(j)} jours, corr {j.corr().iloc[0,1]:.3f}, |ecart| > 2 % : {big.sum()} jours ({big.mean():.1%}) ; cash sans future {len(set(a.index)-set(b.index))}, future sans cash {len(set(b.index)-set(a.index))}")
print("\n(b) 15m agregees par seance vs 1D du meme future (jours communs, 1 tick = tolerance 0,02 %)")
for fut, tz in [(f, tz) for _, (f, tz) in CASH.items()]:
    m = load(fut + "_15m.csv"); D = load(fut + "_1D.csv")
    m["s"] = sd(m.index, tz) if fut[:2] in ("ES", "NQ", "YM", "RT") else (m.index + pd.Timedelta(hours=2)).tz_convert(tz).date
    agg = m.groupby("s").agg(High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), n=("Close", "size"))
    D.index = sd(D.index, tz)
    j = agg.join(D[["High", "Low", "Close"]], rsuffix="_1D", how="inner").iloc[1:-1]
    j = j[j.n >= 20]
    tol = 0.0002 * j.Close_1D
    dc = (np.abs(j.Close - j.Close_1D) > tol).mean(); dh = (np.abs(j.High - j.High_1D) > tol).mean(); dl = (np.abs(j.Low - j.Low_1D) > tol).mean()
    print(f"  {fut:10s} {len(j)} seances : close differente {dc:.0%}, haut {dh:.0%}, bas {dl:.0%}, ecart median close {np.median(np.abs(j.Close-j.Close_1D)/j.Close_1D)*1e4:.1f} pb")
print("\n(c) 15m reconstruites depuis le 1m vs 15m officielles")
for fut in ("FCE1", "FDAX1", "ES1", "NQ1"):
    one = load(fut + "_1m.csv"); off = load(fut + "_15m.csv")
    r = one.resample("15min", label="left", closed="left").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum", })
    cnt = one.Close.resample("15min").size()
    r = r[cnt.reindex(r.index) > 0]
    j = r.join(off, rsuffix="_o", how="inner")
    full = j[cnt.reindex(j.index) == 15]
    diff = lambda col: (np.abs(full[col] - full[col + "_o"]) > 1e-9).mean()
    print(f"  {fut:6s} {len(j)} barres communes ({len(full)} completes), 1m manquantes dans {1 - len(full)/len(j):.1%} ; differentes : open {diff('Open'):.1%}, haut {diff('High'):.1%}, bas {diff('Low'):.1%}, close {diff('Close'):.1%}")
