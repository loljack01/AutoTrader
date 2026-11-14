"""Fuseaux et changements d'heure : semaines ou la cloture US (16h00 New York) tombe a 21h00 Paris,
donc AVANT le controle de 21h42 (routine "Swing avant cloture US", cron CRON_TZ=Europe/Paris 42 21 * * 1-5).
1) horodatage des bougies US du cache (heure d'ouverture UTC) et heure de cloture Paris, 26/10-30/10/2026 et 08/03-27/03/2026 ;
2) sur 2012-2026 (livre a 5 positions), entrees et sorties a la cloture d'indices US tombant ces jours-la ;
3) prochaines fenetres.
Usage : python3 dst_check.py"""
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_all, cap5_trades, ZONE
import pandas as pd

PAR, NY = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York")


def us_close_paris(day):
    return pd.Timestamp(day.year, day.month, day.day, 16, 0, tzinfo=NY).tz_convert(PAR)


data = load_all()
spx = data["SP:SPX"]
for a, b in (("2026-03-06", "2026-03-31"), ("2026-10-23", "2026-11-03")):
    x = spx[(spx.index >= pd.Timestamp(a, tz="UTC")) & (spx.index <= pd.Timestamp(b, tz="UTC"))]
    print(f"S&P 500 {a} -> {b} : " + ", ".join(f"{i:%d/%m} ouv {i:%H:%M}Z clot {us_close_paris(i):%H:%M} Paris" for i in x.index))

t = cap5_trades(data)
us = t[t.sym.map(ZONE) == "us"]
def early(ts):
    return us_close_paris(ts).hour == 21
ent = us[us.entry.map(early)]
ex = us[us.exit.map(early) & (us.exit_px > us.entry_px - us.risk + 1e-9)]  # sorties a la cloture (pas au stop)
print(f"\n2012-2026, livre a 5 : {len(us)} trades US ; entrees a une cloture de 21h00 Paris : {len(ent)} ; "
      f"sorties a la cloture de 21h00 Paris : {len(ex)} ; total {len(ent) + len(ex)} decisions sur {2 * len(us)}"
      f" ({(len(ent) + len(ex)) / (2 * len(us)):.1%}), soit {(len(ent) + len(ex)) / 14.8:.1f} par an")
days = pd.bdate_range("2012-01-01", "2026-11-05", tz="UTC")
nb = sum(us_close_paris(d).hour == 21 for d in days)
print(f"Seances ouvrees concernees 2012-2026 : {nb} ({nb / 14.8:.1f} par an)")
fut = pd.bdate_range("2026-11-06", "2027-12-31", tz="UTC")
w = [d for d in fut if us_close_paris(d).hour == 21]
print("Prochaines seances ou la cloture US est a 21h00 Paris : " + f"{w[0]:%d/%m/%Y} -> {w[-1]:%d/%m/%Y}" if w else "aucune",
      f"({len(w)} seances : " + ", ".join(sorted({f'{d:%m/%Y}' for d in w})) + ")")
