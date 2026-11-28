"""Section 1 : inventaire des règles testées (d'après git log / docstrings, commits cités),
nombre attendu de faux positifs, et correction de Holm / Bonferroni sur les
« validations ». Les t des validations calculables sont recalculés ici.
Usage : PYTHONDONTWRITEBYTECODE=1 python3 tests_inventaire.py"""
import sys; sys.dont_write_bytecode = True
REPO = "/home/user/AutoTrader"; sys.path.insert(0, REPO + "/scripts"); sys.path.insert(0, REPO)
import numpy as np, pandas as pd
from scipy.stats import norm
import test_swing_rsi2 as sw
# (commit, idée, nb de décisions pré-enregistrées, nb d'hypothèses comparées, verdict)
INV = [("d715b30", "recherche exhaustive de combinaisons d'indicateurs", 1, 3066, "exploratoire"),
       ("7e4e603", "filtre tendance journalière (achats)", 1, 1, "info"),
       ("7b8171e", "miroir vente + filtre", 1, 1, "info"),
       ("977de41", "puts 5m figés (plancher 2xATR)", 1, 2, "figé, suivi -9.8R/30"),
       ("c1b2a69", "filtres 1D/4h/1h 5m", 1, 3, "info"),
       ("c78be96", "filtres rapides SMA20/EMA20/SMA10", 1, 3, "non remplacé"),
       ("a880a29", "15m sma20/ema20 figés", 1, 2, "figé"),
       ("a8c1284", "options d'audit (5)", 1, 5, "info"),
       ("321adb5", "balayage de l'extrême de séance", 1, 1, "rejeté"),
       ("6f42ca5", "continuation P1/P2", 2, 2, "rejeté"),
       ("f66b1ad", "2 sorties", 2, 2, "rejeté"),
       ("05d6792", "3 filtres de direction", 3, 3, "rejeté"),
       ("7985e51", "règles 15m sur 4 marchés", 2, 2, "non confirmé"),
       ("0933b45", "version améliorée (5 corrections)", 1, 6, "non retenu (1 point tient)"),
       ("1f0828e", "grille SMA/EMA x 6 longueurs", 1, 24, "sma20 gardée"),
       ("97239b2", "escalier intraday", 1, 1, "rejeté (non suivi)"),
       ("752b631", "comblement d'écart", 1, 1, "rejeté t=-3.54"),
       ("752b631", "squeeze Bollinger", 1, 1, "rejeté (non suivi)"),
       ("c6efe40", "écart continue (a posteriori)", 1, 1, "suivi"),
       ("8762eab", "CHoCH frais A/B/A+B", 1, 3, "suivi (t=1.06)"),
       ("39259dd", "entrée limite", 1, 1, "rejeté (non suivi)"),
       ("306b5d5", "robustesse aux gros gains (familles)", 1, 9, "calls avec tendance robuste"),
       ("daf3e25", "cassure du range d'ouverture", 1, 2, "rejeté (non suivi)"),
       ("3fe82f1", "repli VWAP d'ouverture", 1, 1, "rejeté (non suivi)"),
       ("175bd05", "supertrend A/B/C", 3, 3, "rejeté (non suivi)"),
       ("ce89557", "TSMOM 12m actions", 1, 1, "rejeté (non suivi)"),
       ("060853a", "TSMOM diversifié", 1, 1, "rejeté (non suivi)"),
       ("ee9e6ee", "principale sur pétrole", 1, 1, "ne tient pas"),
       ("0746bc4", "1m contexte", 1, 1, "rejeté"), ("ff107fa", "1m un seul sens", 1, 1, "rejeté"),
       ("bccba12", "1m marge 16", 1, 1, "rejeté"), ("8191138", "enchère ratée IB", 1, 1, "rejeté"),
       ("226c296", "divergence SMT", 1, 1, "rejeté"), ("70077ae", "delta corrigé", 1, 1, "en attente"),
       ("5d4a0eb", "papamallis", 1, 1, "rejeté"), ("265b14b", "réaction structure 5m", 1, 1, "rejeté"),
       ("ed6b223", "rotation sectorielle", 1, 1, "rejeté"),
       ("f170711", "swing RSI(2) calls / puts", 2, 2, "calls PASSE, puts rejeté"),
       ("f170711", "momentum fin de séance", 1, 1, "rejeté"), ("d1abab6", "NR7", 1, 1, "rejeté"),
       ("77181f2", "validation swing (8 indices + 27 voisins)", 2, 28, "confirmé"),
       ("117745c", "tournant du mois", 1, 1, "rejeté"), ("fad8c5b", "swing 2 positions", 1, 1, "rejeté"),
       ("8328601", "swing 1991-2011", 1, 1, "confirmé t=2.72"), ("2c2d347", "limite 5 positions", 1, 1, "adopté"),
       ("b808b85", "tests 1-3 du 06/11", 3, 3, "non adoptés")]
inv = pd.DataFrame(INV, columns=["commit", "idee", "decisions", "hypotheses", "verdict"])
m_dec, m_hyp = inv.decisions.sum(), inv.hypotheses.sum()
print(inv.to_string(index=False))
print(f"\nIdees/scripts : {len(inv)} ; decisions pre-enregistrees : {m_dec} ; hypotheses comparees (combos, grilles, voisins inclus) : {m_hyp}")
for m in (m_dec, m_hyp):
    print(f"  m={m}: faux positifs attendus a 5 % si tout est nul = {0.05*m:.1f} ; seuil Bonferroni unilateral 5 % : p <= {0.05/m:.2e} (t >= {norm.isf(0.05/m):.2f})")
# t des validations
def tweek(t):
    w = t.groupby(t.exit.dt.tz_localize(None).dt.to_period("W")).r.sum(); return w.mean() / (w.std(ddof=1) / np.sqrt(len(w)))
parts = []
for s in sw.INDICES:
    d = sw.load(s); x = sw.run(d, 1); parts.append(x.assign(r=sw.net(x, sw.COSTS[0])))
x = pd.concat(parts); t_sw = tweek(x)
VAL = {"swing 10 indices" : sw.INDICES}
new = {"EURONEXT:AEX": 0, "BME:IBC": 0, "OMXSTO:OMXS30": 0, "TVC:NI225": 0, "HSI:HSI": 0, "ASX:XJO": 0, "TSX:TSX": 0, "EURONEXT:BEL20": 0}
p2 = []
for s in new:
    d = sw.load(s); y = sw.run(d, 1); p2.append(y.assign(r=sw.net(y, sw.COSTS[0])))
y = pd.concat(p2); t_new = tweek(y)
tr = pd.read_csv("/home/user/AutoTrader/audit/2026-11-06/recherche/trades_15m.csv", parse_dates=["entry_time"])
tr = tr[tr.result != "open"]
def tt(r): return r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
h = tr[(tr.strat == "principale") & (tr.entry_time < pd.Timestamp("2026-10-28", tz="UTC"))].net_r
g = tr[(tr.strat == "ecart") & (tr.entry_time < pd.Timestamp("2026-10-28", tz="UTC"))].net_r
live = tr[(tr.strat == "principale") & (tr.entry_time >= pd.Timestamp("2026-10-28", tz="UTC"))].net_r
vals = {"swing RSI(2) 2012-2026 (t hebdo)": t_sw, "swing 8 indices nouveaux (t hebdo)": t_new,
        "swing 1991-2011 (docstring, donnees hors depot)": 2.72, "limite 5 positions 2012-2026 (docstring)": 2.25,
        "principale historique 1pt (t par trade)": tt(h), "principale historique plafond 5R": tt(np.minimum(h, 5)),
        "principale suivi 40 trades": tt(live), "CHoCH frais (docstring)": 1.06, "ecart continue a posteriori": tt(g)}
v = pd.DataFrame({"t": vals}).assign(p=lambda z: norm.sf(z.t)).sort_values("p")
for m in (m_dec, m_hyp):
    k = len(v); rank = np.arange(1, k + 1)
    v[f"Bonf m={m}"] = v.p <= 0.05 / m
    holm = []; ok = True
    for i, p in enumerate(v.p):
        ok = ok and p <= 0.05 / (m - i); holm.append(ok)
    v[f"Holm m={m}"] = holm
print("\n", v.round(4).to_string())
z = (t_sw + 2.72) / np.sqrt(2)
print(f"\nStouffer swing 1991-2011 + 2012-2026 : z={z:.2f}, p={norm.sf(z):.1e}")
