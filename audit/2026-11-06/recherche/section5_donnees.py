"""Section 5 : qualité des données de data/cache (lecture seule).
Usage : python3 section5_donnees.py"""
import numpy as np, pandas as pd, glob, os
C = "/home/user/AutoTrader/data/cache/"
def load(f):
    d = pd.read_csv(C + f, index_col=0); d.index = pd.to_datetime(d.index, utc=True); return d
CASH = {"EURONEXT_PX1": ("FCE1", "Europe/Paris"), "XETR_DAX": ("FDAX1", "Europe/Berlin"), "TVC_SX5E": ("FESX1", "Europe/Berlin"),
        "SP_SPX": ("ES1", "America/New_York"), "NASDAQ_NDX": ("NQ1", "America/New_York"), "TVC_UKX": ("ICEEUR_Z1", "Europe/London"),
        "SIX_SMI": ("FSMI1", "Europe/Zurich"), "TVC_DJI": ("YM1", "America/New_York"), "TVC_RUT": ("RTY1", "America/New_York"),
        "TVC_FTMIB": ("FIB1", "Europe/Rome")}
print("=== 1D : indices cash (2012 ->) et futures")
rows = []
for cash, (fut, tz) in CASH.items():
    for name in (cash, fut):
        d = load(name + "_1D.csv"); dup = d.index.duplicated().sum()
        d = d[~d.index.duplicated(keep="last")].sort_index(); d = d[d.index >= "2012-01-01"]
        loc = d.index.tz_convert(tz)
        hours = pd.Series(d.index.hour).value_counts()
        wkend = (loc.dayofweek >= 5).sum()
        gaps = pd.Series(loc.normalize()).diff().dt.days
        big = (gaps > 4).sum()
        stale = (np.isclose(d.Open.to_numpy()[1:], d.Close.to_numpy()[:-1], atol=1e-6)).mean()
        flat = ((d.High == d.Low)).sum()
        bad = ((d.High < d[["Open", "Close"]].max(axis=1) - 1e-9) | (d.Low > d[["Open", "Close"]].min(axis=1) + 1e-9)).sum()
        vol0 = (d.Volume.isna() | (d.Volume == 0)).mean()
        rows.append((name, len(d), dup, wkend, big, f"{stale:.1%}", flat, bad, f"{vol0:.0%}", dict(hours.head(3))))
print(pd.DataFrame(rows, columns=["serie", "barres", "doublons", "week-end", "trous>4j", "open=close veille", "H=L", "OHLC incoh.", "volume nul", "heures UTC"]).to_string(index=False))
# cohérence future / cash : corrélation des rendements journaliers, décalage
print("\n=== Futures vs cash (rendements journaliers par date locale, 2012 ->)")
for cash, (fut, tz) in CASH.items():
    a, b = load(cash + "_1D.csv"), load(fut + "_1D.csv")
    for x in (a, b):
        x.drop(x.index[x.index.duplicated()], inplace=True)
    ra = a.Close.pct_change(); rb = b.Close.pct_change()
    ra.index = ra.index.tz_convert(tz).date; rb.index = rb.index.tz_convert(tz).date
    j = pd.concat([ra, rb], axis=1, keys=["cash", "fut"]).dropna()
    j = j[pd.to_datetime(j.index) >= "2012-01-01"]
    c0 = j.corr().iloc[0, 1]; c1 = j.cash.corr(j.fut.shift(1)); cm1 = j.cash.corr(j.fut.shift(-1))
    big = (np.abs(j.cash - j.fut) > 0.02).sum()
    print(f"  {cash:12s}/{fut:10s} {len(j):5d} jours communs, corr J {c0:.3f} (J-1 {c1:+.3f}, J+1 {cm1:+.3f}), jours |ecart| > 2 % : {big} ({big/len(j):.1%})")
print("\n=== 15m futures")
for f in sorted(glob.glob(C + "*_15m.csv")):
    n = os.path.basename(f); d = load(n); dup = d.index.duplicated().sum(); d = d[~d.index.duplicated()]
    loc = d.index.tz_convert("Europe/Paris")
    step = pd.Series(d.index).diff().dt.total_seconds() / 60
    off = (d.index.minute % 15 != 0).sum()
    wk = ((loc.dayofweek == 5) | ((loc.dayofweek == 6) & (loc.hour < 22))).sum()
    gaps_in = ((step > 15) & (step < 60 * 3)).sum()   # trous intra-séance (< 3 h)
    vol0 = (d.Volume.isna() | (d.Volume == 0)).mean()
    print(f"  {n:22s} {len(d):5d} barres {d.index[0]:%d/%m/%Y} -> {d.index[-1]:%d/%m}, doublons {dup}, hors grille {off}, samedi/dimanche avant 22h {wk}, trous intra-seance {gaps_in}, volume nul {vol0:.1%}")
