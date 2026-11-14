"""Rejeu de bout en bout : swing_preclose.py (17h12 / 21h42) contre frozen_swing_rsi2.py (bilan de 22h15).

Pour chaque seance D du 01/07/2026 au 05/11/2026 :
  - etat du soir D-1 : frozen_swing_rsi2.main() lance avec les donnees coupees a D-1 (FREEZE avance au 01/06/2026,
    sorties ecrites dans /tmp, jamais dans le depot) -> fichier des trades lu par swing_preclose ;
  - controle avant cloture : swing_preclose.main() lance tel quel, horloge forcee a D, avec le cours proxy :
      proxy(D) = cloture cash(D-1) x future(D, bougie 15m fermant a 17h15 Paris pour l'Europe, 21h45 pour les USA)
                 / future(D-1, bougie fermant a l'heure de cloture du cash)
    (l'"avant-derniere cloture" 15m avant la cloture du cash ; futures : FCE1 FDAX1 FESX1 Z1 FSMI1 FIB1 ES1 NQ1 YM1 RTY1).
    Si le cash US est deja clos a 21h42 (semaines de decalage d'heure), le proxy est la cloture reelle (ce que
    TradingView renverrait) et le cas est marque "apres la cloture".
    Deux appels separes (EU puis US), comme les routines, chacun lisant le meme fichier du soir D-1.
  - verite : frozen_swing_rsi2.main() coupe a D (signaux "pris" du jour, sorties du jour).
Usage : python3 replay_preclose.py
"""
import contextlib, io, re, sys, tempfile
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import REPO, sw, ZONE
import numpy as np
pd = pandas
import frozen_swing_rsi2 as fs
import swing_preclose as sp
from data import cache

FUT = {"EURONEXT:PX1": "FCE1!", "XETR:DAX": "FDAX1!", "TVC:SX5E": "FESX1!", "TVC:UKX": "ICEEUR:Z1!", "SIX:SMI": "FSMI1!",
       "TVC:FTMIB": "FIB1!", "SP:SPX": "ES1!", "NASDAQ:NDX": "NQ1!", "TVC:DJI": "YM1!", "TVC:RUT": "RTY1!"}
PAR, NY = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York")
TMP = Path(tempfile.mkdtemp(prefix="replay_"))
FULL = {s: sw.load(s) for s in sw.INDICES}
F15 = {}
for s, f in FUT.items():
    x = cache.load(f, "15m"); x.index = pd.to_datetime(x.index, utc=True)
    F15[s] = x[~x.index.duplicated(keep="last")].sort_index()


def cut_loader(cutoff):
    def ld(sym):
        d = FULL[sym]
        return d[d.index.tz_convert(PAR).normalize() <= cutoff].copy()
    return ld


def evening(day):
    """frozen_swing_rsi2.main() sur les donnees coupees au soir de `day` ; renvoie le fichier des trades."""
    out = TMP / f"trades_{day:%Y%m%d}.csv"
    fs.load, fs.FREEZE, fs.OUT, fs.JOURNAL = cut_loader(day), pd.Timestamp("2026-06-01", tz="UTC"), out, TMP / "none.csv"
    sys.argv = ["x"]
    with contextlib.redirect_stdout(io.StringIO()):
        fs.main()
    return out


def cash_close_utc(day, sym):
    if ZONE[sym] == "us":
        return pd.Timestamp(day.year, day.month, day.day, 16, 0, tzinfo=NY).tz_convert("UTC")
    return pd.Timestamp(day.year, day.month, day.day, 17, 30, tzinfo=PAR).tz_convert("UTC")


def fut_close_at(sym, t_utc):
    x = F15[sym]
    bar = x[(x.index + pd.Timedelta(minutes=15)) <= t_utc]
    if not len(bar) or (t_utc - (bar.index[-1] + pd.Timedelta(minutes=15))) > pd.Timedelta(minutes=16):
        return None
    return float(bar.Close.iloc[-1])


def proxy(sym, day, prev):
    hh, mm = (17, 15) if ZONE[sym] == "eu" else (21, 45)
    t_now = pd.Timestamp(day.year, day.month, day.day, hh, mm, tzinfo=PAR).tz_convert("UTC")
    d = FULL[sym]; dd = d.index.tz_convert(PAR).normalize()
    if ZONE[sym] == "us" and t_now > cash_close_utc(day, sym):
        return float(d.Close[dd == day].iloc[0]), "apres_cloture"
    f_now, f_prev = fut_close_at(sym, t_now), fut_close_at(sym, cash_close_utc(prev, sym))
    if f_now is None or f_prev is None:
        return None, "pas_de_future"
    return float(d.Close[dd == prev].iloc[0]) * f_now / f_prev, "proxy"


class _TS:
    FIXED = None
    def __new__(cls, *a, **k):
        return pandas.Timestamp(*a, **k)
    @staticmethod
    def now(tz=None):
        return _TS.FIXED


class _PD:
    def __getattr__(self, n):
        return _TS if n == "Timestamp" else getattr(pandas, n)


def preclose(day, trades_file, prices):
    _TS.FIXED = pd.Timestamp(day.year, day.month, day.day, 17, 12, tz="Europe/Paris")
    sp.pd, sp.TRADES = _PD(), trades_file
    sys.argv = ["x"] + [f"{s}={p}" for s, p in prices.items()]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sp.main()
    return buf.getvalue()


def main():
    days = sorted(set(FULL["EURONEXT:PX1"].index.tz_convert(PAR).normalize()) | set(FULL["SP:SPX"].index.tz_convert(PAR).normalize()))
    days = [d for d in days if pd.Timestamp("2026-07-01", tz=PAR) <= d <= pd.Timestamp("2026-11-05", tz=PAR)]
    rows, perr, stopdiff = [], [], []
    for k in range(1, len(days)):
        day, prev = days[k], days[k - 1]
        f_prev = evening(prev)
        truth = pd.read_csv(evening(day))
        tday = truth[pd.to_datetime(truth.entree) == day.tz_localize(None)]
        texit = truth[(truth.pris == True) & (pd.to_datetime(truth.sortie) == day.tz_localize(None))]  # noqa
        name2sym = {v: k2 for k2, v in sw.INDICES.items()}
        out_txt = {}
        for zone in ("eu", "us"):
            prices, flags = {}, {}
            for s in sw.INDICES:
                if ZONE[s] != zone:
                    continue
                dd = FULL[s].index.tz_convert(PAR).normalize()
                if day not in set(dd) or prev not in set(dd):
                    continue
                p, fl = proxy(s, day, dd[dd < day][-1])
                if p is not None:
                    prices[s], flags[s] = round(p, 2), fl
                    close = float(FULL[s].Close[dd == day].iloc[0])
                    if fl == "proxy":
                        perr.append(abs(p / close - 1))
            if prices:
                out_txt[zone] = (preclose(day, f_prev, prices), prices, flags)
        for zone, (txt, prices, flags) in out_txt.items():
            for s in prices:
                name = sw.INDICES[s]
                line = next((l for l in txt.splitlines() if l.strip().startswith(name + ":")), "")
                pc_entry = "ENTREE a prendre" in line
                pc_ignored = "ENTREE ignoree" in line
                pc_exit = "SORTIE" in line
                tr = tday[tday.marche == name]
                t_entry = bool(len(tr) and tr.pris.iloc[0])
                t_ignored = bool(len(tr) and not tr.pris.iloc[0])
                t_exit = bool((texit.marche == name).any())
                if pc_entry or pc_ignored or pc_exit or t_entry or t_ignored or t_exit:
                    m = re.search(r"stop ([\d.]+) \(", line)
                    if m and len(tr):
                        stopdiff.append((float(m.group(1)) - tr.stop.iloc[0]) / (tr.prix_entree.iloc[0] - tr.stop.iloc[0]))
                    xr = texit[texit.marche == name]
                    stop_exit = bool(len(xr) and xr.prix_sortie.iloc[0] <= xr.stop.iloc[0] + 1e-9)
                    d_s = FULL[s]; dd_s = d_s.index.tz_convert(PAR).normalize()
                    rsi_close = float(d_s.rsi2[dd_s == day].iloc[0])
                    rows.append(dict(jour=day.date(), marche=name, zone=zone, flag=flags[s], sortie_au_stop=stop_exit,
                                     rsi2_cloture=round(rsi_close, 1), ligne=line.strip()[:90], pc_entree=pc_entry,
                                     pc_ignoree=pc_ignored, pc_sortie=pc_exit, bilan_entree=t_entry,
                                     bilan_ignoree=t_ignored, bilan_sortie=t_exit))
    r = pd.DataFrame(rows)
    r.to_csv(Path(__file__).with_name("replay_preclose_detail.csv"), index=False)
    sig_days = r[(r.bilan_entree | r.bilan_ignoree | r.pc_entree | r.pc_ignoree)].jour.nunique()
    print(f"Seances rejouees : {len(days) - 1} ; seances avec un signal d'entree (bilan ou controle) : {sig_days}")
    print(f"Erreur du proxy 15m (|proxy/cloture - 1|) : mediane {np.median(perr):.3%}, 90e centile {np.percentile(perr, 90):.3%}")
    e = r
    agree_in = (e.pc_entree & e.bilan_entree).sum()
    false_in = (e.pc_entree & ~e.bilan_entree).sum()
    miss_in = (~e.pc_entree & e.bilan_entree).sum()
    print(f"ENTREES a prendre : bilan {e.bilan_entree.sum()}, controle {e.pc_entree.sum()} | concordantes {agree_in}, "
          f"faux signaux du controle {false_in}, signaux manques {miss_in}")
    print(f"  dont faux 'a prendre' alors que le bilan dit IGNORE (5 positions) : {(e.pc_entree & e.bilan_ignoree).sum()}")
    print(f"SORTIES : bilan {e.bilan_sortie.sum()}, controle {e.pc_sortie.sum()} | concordantes {(e.pc_sortie & e.bilan_sortie).sum()}, "
          f"fausses {(e.pc_sortie & ~e.bilan_sortie).sum()}, manquees {(~e.pc_sortie & e.bilan_sortie).sum()}")
    ms = e[~e.pc_sortie & e.bilan_sortie]
    print(f"  dont sorties manquees qui sont des stops touches en seance (ordre stop, pas de decision a la cloture) : {ms.sortie_au_stop.sum()} ; "
          f"vraies sorties a la cloture manquees : {(~ms.sortie_au_stop).sum()}")
    cap_cases = e[(e.pc_ignoree & e.bilan_entree) | (e.pc_entree & e.bilan_ignoree)]
    print(f"  ecarts dus au compte des places (5 positions) : {len(cap_cases)}")
    print(f"  ecarts d'entree a RSI(2) de cloture entre 7 et 13 : {((e.pc_entree != e.bilan_entree) & e.rsi2_cloture.between(7, 13)).sum()} "
          f"sur {(e.pc_entree != e.bilan_entree).sum()}")
    print(f"Lignes concernees apres la cloture US (decalage d'heure) : {(e.flag == 'apres_cloture').sum()}")
    if stopdiff:
        sd = np.array(stopdiff)
        print(f"Stop du controle (ATR de la veille) - stop du bilan, en R : mediane {np.median(sd):+.3f}, extremes {sd.min():+.3f} / {sd.max():+.3f}")
    print(f"Detail : replay_preclose_detail.csv")
    print(r[(r.pc_entree != r.bilan_entree) | (r.pc_sortie != r.bilan_sortie)].to_string(index=False))


if __name__ == "__main__":
    main()
