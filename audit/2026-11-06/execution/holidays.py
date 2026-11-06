"""swing_preclose.py compte les jours de detention avec np.busday_count (lundi-vendredi, sans jours feries) alors que
la regle compte des seances (10e seance apres l'entree). Compte, sur le livre a 5 positions 2012-2026, les trades ou le
controle aurait annonce la sortie "10e jour" une seance trop tot (un jour ferie de l'indice dans la detention).
Usage : python3 holidays.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_all, cap5_trades
import numpy as np

data = load_all()
t = cap5_trades(data)
early = 0
for x in t.itertuples():
    idx = data[x.sym].index.normalize()
    i = idx.get_loc(x.entry)
    for j in range(i + 1, i + 1 + x.days):  # seances encore detenues avant la sortie reelle
        if j == i + x.days:
            break
        if np.busday_count(x.entry.date(), idx[j].date()) >= 10:
            early += 1
            break
print(f"{len(t)} trades ; trades avec une fausse sortie '10e jour' au controle avant cloture : {early} ({early / len(t):.1%})")
