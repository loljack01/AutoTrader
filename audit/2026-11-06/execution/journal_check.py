"""Controle du journal et des unites du glissement de frozen_swing_rsi2.py, en lancant le script lui-meme
(FREEZE avance au 01/07/2026 pour avoir des trades clos ; OUT et JOURNAL rediriges vers /tmp, depot intact).
Journaux testes :
  A  prix d'indice reels = prix du modele -2 points a l'entree et a la sortie (cas attendu)
  B  prix du TURBO notes a la place des points d'indice (turbo levier ~1,5, parite 100 ; parite 1000 FTSE MIB)
  C  journal A + colonnes ajoutees (heure, isin, parite, prix_turbo..., hors_systeme, motif)
  D  journal A + une ligne en double et une ligne hors systeme + un nom de marche mal ecrit
Usage : python3 journal_check.py"""
import contextlib, io, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import sw
import pandas as pd
import frozen_swing_rsi2 as fs

TMP = Path(tempfile.mkdtemp(prefix="journal_"))
fs.FREEZE, fs.OUT = pd.Timestamp("2026-07-01", tz="UTC"), TMP / "trades.csv"


def run(journal):
    fs.JOURNAL = TMP / "journal.csv"
    journal.to_csv(fs.JOURNAL, index=False)
    sys.argv = ["x"]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fs.main()
    return [l for l in buf.getvalue().splitlines() if "Execution" in l or "Controle d'execution" in l or "Depuis" in l]


fs.JOURNAL = TMP / "absent.csv"
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    fs.main()
t = pd.read_csv(fs.OUT)
c = t[t.pris & t.net_r_005.notna()].copy()
print(f"Trades clos pris depuis le 01/07/2026 (rejeu) : {len(c)}, net {c.net_r_005.sum():+.2f}R")
A = pd.DataFrame({"marche": c.marche, "entree": c.entree, "prix_entree": c.prix_entree + 2,
                  "sortie": c.sortie, "prix_sortie": c.prix_sortie - 2})
print("A (points d'indice, -2 pts par ordre) :", *run(A), sep="\n  ")
par = c.marche.map(lambda m: 1000 if m == "FTSE MIB" else 100)
lev = 1.5
k = c.prix_entree * (1 - 1 / lev)
B = pd.DataFrame({"marche": c.marche, "entree": c.entree, "prix_entree": ((c.prix_entree - k) / par).round(2),
                  "sortie": c.sortie, "prix_sortie": ((c.prix_sortie - k) / par).round(2)})
x = c.iloc[0]; b = B.iloc[0]
risk = x.prix_entree - x.stop
print(f"Exemple B : {x.marche} entree {x.entree} modele {x.prix_entree} -> {x.prix_sortie} (stop {x.stop}, R = {risk:.2f} pts, "
      f"resultat modele {(x.prix_sortie - x.prix_entree) / risk:+.3f}R) ; turbo note {b.prix_entree} -> {b.prix_sortie} : "
      f"glissement calcule = (({b.prix_sortie} - {b.prix_entree}) - ({x.prix_sortie} - {x.prix_entree})) / {risk:.2f} = "
      f"{((b.prix_sortie - b.prix_entree) - (x.prix_sortie - x.prix_entree)) / risk:+.3f}R")
print("B (prix du turbo) :", *run(B), sep="\n  ")
C = A.assign(heure_entree="17:25", heure_sortie="17:26", isin="DE000XXXXXXX", parite=100, prix_turbo_entree=10.0,
             prix_turbo_sortie=10.5, quantite=50, resultat_eur=25.0, signal="controle_17h12", hors_systeme=0, motif="")
print("C (colonnes ajoutees) :", *run(C), sep="\n  ")
D = pd.concat([A, A.iloc[[0]], pd.DataFrame([{"marche": "CAC 40", "entree": "2026-10-20", "prix_entree": 8000,
                                               "sortie": "2026-10-21", "prix_sortie": 7900}])], ignore_index=True)
D.loc[1, "marche"] = D.loc[1, "marche"].upper().replace(" ", "")
print("D (doublon, ligne hors systeme, nom mal ecrit) :", *run(D), sep="\n  ")
