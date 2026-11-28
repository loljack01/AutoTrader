# Analyse intraday du FCE1, vendredi 27/11/2026 (8h00-22h00) : modèle pour les fois suivantes

Lecture APRÈS COUP, pas un signal. Méthode : règle 37 de `docs/regles_execution.md`. Données exactes 1 minute
(666 minutes, 8h00-19h05) puis 15m du bilan jusqu'à 22h00, double contrôle par deux calculs indépendants : concordants (outil
`scripts/lecture_fce1_jour.py`). Clôture anticipée de New York à 19h00 (lendemain de Thanksgiving).
Écart future - cash : FCE1 8158 à 17h35 pour un CAC cash clôturé à 8156,09, soit environ +2 à +3 points ;
équivalent cash ≈ FCE1 - 2,5.

## 1. La journée réelle

Règlement du 26/11 : 8114 (dernier cours 22h : 8110,5). Ouverture 8h00 : 8139. Plus bas **8117 à 12h47**,
plus haut **8189,5 à 18h59**, dernier cours 19h05 : 8183,5 (+69,5). Prix moyen pondéré (VWAP depuis 8h) :
8148,1.

| Heure | Mouvement | Ce qui s'est passé |
|---|---|---|
| 8h10 → 8h35 | 8128,5 → 8151,5 (+23) | 1er rejet de la borne haute 8150-8155 (SMA20 et double sommet du 26/11) |
| 8h59 → 9h00 | 8143 → 8122 (−21) | chute juste avant l'ouverture du cash |
| 9h00 → 9h05 | 8122 → 8155 (+33) | faux passage au-dessus de 8152 : 2e rejet |
| 9h05 → 11h30 | range 8131,5-8148,5 | autour de la zone pivot 8129-8138 |
| 11h51 → 12h47 | 8152,5 → 8117 (−35,5) | 3e rejet, cassure de la zone pivot, arrêt sur le pivot 8116,5 / 8120 |
| 12h47 → 14h10 | 8117 → 8142,5 (+25,5) | deux creux égaux à 8123 (13h05, 13h51), puis retour dans la zone pivot |
| 14h10 → 15h08 | 8142,5 → 8121,5 (−21) | creux plus haut que 12h47 |
| 15h30 → 15h41 | 8127 → 8140 → 8124,5 | aller-retour à l'ouverture américaine, creux encore plus haut |
| 15h41 → 17h03 | 8124,5 → 8178,5 (+54) | **cassure de 8152 vers 16h00** (et du plus haut de la semaine 8154,5, de la SMA20 8159) |
| 17h03 → 17h32 | 8178,5 → 8153,5 (−25) | ventes du fixing (1466 contrats à 17h34), arrêt sur 8152 devenu support |
| 17h32 → 18h59 | 8153,5 → 8189,5 (+36) | hausse jusqu'à la clôture anticipée de New York |
| 18h59 → 19h05 | 8189,5 → 8178,5 → 8183,5 | léger repli, très peu de volume |
| 19h05 → 22h00 | range 8177-8183, clôture 8180,5 | peu échangé (636 contrats en 3 heures), New York fermé |

## 2. Figures et structure

| Élément | Lecture |
|---|---|
| Résistance du jour | 8150-8155 testée 4 fois (8h35, 8h55, 9h05, 11h51) |
| Double sommet | 8151,5 (8h35, 8h55), ligne de cou 8141, cassée à 8h59, objectif 8130,5 atteint |
| Zone pivot | 8129-8138, équilibre du range 8117-8155 (≈8136) |
| Triangle ascendant | plafond 8152, creux montants 8117 (12h47), 8121,5 (15h08), 8124,5 (15h41) ; cassure 16h00 ; hauteur 38, objectif 8190, atteint à 8189,5 (18h59) |
| Liquidité au-dessus | 9h05 : passage à 8155 au-dessus des sommets égaux 8151,5, retour sous 8150 |
| Liquidité au-dessous | 12h47 : passage à 8117 sous le creux de 9h00 (8122), pas de clôture 15m dessous (marteau) |
| Cassures de structure | baissière 12h45 (clôture 8128,5 sous 8133,5) ; changement à la hausse 16h00 (clôture 8144 au-dessus de 8142,5) ; haussière 16h15 (clôture 8161 au-dessus de 8155) |
| Trou de cotation de la cassure | 8151,5-8156 en 15m (8152-8158,5 en 5m), retesté à 8153,5 à 17h32 et tenu |
| Dernière bougie baissière avant la hausse | 15h00, zone 8121,5-8130,5, jamais retestée |
| Volumes (rapport aux 20 bougies 15m précédentes) | 9h00 : 24 fois ; cassure 16h00 : 2,7 fois ; fixing 17h30 : 6,6 fois ; après 18h : 0,1 à 0,7 fois |

## 3. Tableau des puts et calls (entrées dès 8h00, règle 37)

Niveaux connus la veille ; entrée à la clôture 15m après un retournement ou une cassure sur une borne ;
stop 2 points derrière ; sortie à la première zone touchée ; 3 points de frais.

| Heure | Ordre | CALL | PUT | Niveau FCE1 (≈ cash) | Bougie 15m | Indicateurs | Support / résistance, figure | Lecture smart money | Résultat |
|---|---|---|---|---|---|---|---|---|---|
| 8h15 | ACHAT | **CALL** | | 8132 (≈8129,5), stop 8126,5 | 8139 → 8132, mèches courtes | RSI 61, au-dessus EMA20 / SMA50, sous VWAP 8135, volume 1,9 fois | creux 8128,5 pile sur le niveau enregistré | touche du niveau, pas de balayage | |
| 8h24 | VENTE | **CALL** | | 8138 (≈8135,5) | grande bougie verte | | haut de la zone pivot | trou 5m 8134,5-8138,5 | **+6 brut, +3 net** |
| 8h45 | ACHAT | | **PUT** | 8144 (≈8141,5), stop 8153,5 | **étoile filante** (mèche haute 7,5) | RSI 68 | 1er rejet de 8150-8155 | sommet sous la liquidité 8152 ; annonce 8h45 (signalée) | |
| 8h59 | VENTE | | **PUT** | 8138 (≈8135,5) | avalement baissier, volume 2,2 fois | | double sommet 8151,5, 2 points sous le stop à 8h55 | | **+6 brut, +3 net** |
| 9h00 | ACHAT | | **PUT** | 8130 (≈8127,5), stop 8153,5 | avalement baissier clôturé au plus bas | RSI 55, sous VWAP | double sommet confirmé, entrée au bas de la zone pivot | risque 23,5 pour 5 ; entrée 9h00 (signalée) | |
| 9h00 | VENTE | | **PUT** | 8124,75 (≈8122) | minute de 9h00 : 8122, 1029 contrats | | pivot atteint | balayage des deux côtés ensuite | **+5,25 brut, +2,25 net** |
| 9h15 | ACHAT | | **PUT** | 8142,5 (≈8140), stop 8157 | 33 points d'amplitude, mèche haute 12,5 | RSI 62, au-dessus VWAP 8139,9 | faux passage à 8155, clôture sous 8150 | **liquidité prise au-dessus des sommets égaux** | |
| 9h15-9h30 | VENTE | | **PUT** | 8138 (≈8135,5) | plus bas 8133 | RSI 57 | zone pivot | | **+4,5 brut, +1,5 net** |
| 12h00 | ACHAT | | **PUT** | 8148 (≈8145,5), stop 8154,5 | **doji / étoile filante**, volume 0,6 fois | RSI 63, au-dessus VWAP | **3e rejet de 8152** | sommet plus bas que 8155 | |
| 12h15-12h30 | VENTE | | **PUT** | 8138 (≈8135,5) | deux grandes bougies rouges | | zone pivot cassée ensuite | trou baissier 8129-8138, cassure baissière | **+10 brut, +7 net** |
| 13h00 | — | ignoré | | 8127,5 (≈8125) | **marteau** (mèche basse 10,5) | RSI 45, sous EMA20 et VWAP | pivot 8116,5 | liquidité prise sous 8122 | cible à 1,5 point (+25 non pris) |
| 14h00 | ACHAT | **CALL** | | 8131 (≈8128,5), stop 8121 | **marteau** (mèche basse 5,5), clôture au plus haut | RSI 48, sous EMA20 8133 et VWAP 8138, volume 0,4 fois | **deux creux égaux 8123** (13h05, 13h51), plus hauts que 8117 | creux montants ; trous 5m 8127,5-8130,5 et 8132,5-8136,5 | |
| 14h04 | VENTE | **CALL** | | 8138 (≈8135,5) | grande bougie verte 14h00 | | haut de la zone pivot (plus haut 8142,5 à 14h10) | | **+7 brut, +4 net** |
| 16h15 | ACHAT | **CALL** | | 8161 (≈8158,5), stop 8148 | **grande bougie verte** (corps 16,5 / 19,5), volume 2,7 fois | RSI 69, au-dessus EMA20, SMA50, VWAP | cassure de 8152, SMA20, plus haut de semaine ; **triangle ascendant** | **cassure haussière** au-dessus de 8155, trou 8151,5-8156 | |
| 17h45 | renfort possible | **CALL** | | 8163 (≈8160,5), stop 8151,5 | **marteau** (mèche basse 8,5), volume 6,6 fois (fixing) | RSI 63, au-dessus VWAP | **retest de 8152** par le dessus | creux 8153,5 dans le trou 8151,5-8156 | même sens |
| 22h00 | VENTE | **CALL** | | 8180,5 (≈8178) | fin de séance (sortie au plus tard à 22h00) ; stop 8148 jamais touché (plus bas après l'entrée 8153,5 à 17h32) | RSI 73 à 18h45, volume faible le soir | objectif du triangle 8190 atteint (8189,5) ; 8199 (SMA200) pas atteint | | **+19,5 brut, +16,5 net (+1,3 R)** |
| 17h03 | — | | non détecté | 8178,5 | pas de figure de retournement | RSI 74 à 16h45 | aucun niveau connu | grande bougie rouge 17h15 (fixing) | −25 non pris |

Bilan 8h00-22h00 : 7 trades clos, **+58,25 brut, +37,25 net**. Séance : ouverture 8139, plus haut 8189,5 (18h59), plus bas 8117 (12h47), clôture 22h 8180,5 (+66,5 sur le règlement du 26/11 ; règlement du 27/11 : 8161,5).

Double contrôle de la soirée : les 44 bougies 15m de 8h00 à 18h45 du flux 15m du bilan sont identiques à celles recalculées depuis les barres 1 minute (écart 0).

## 4. Erreurs corrigées dans la conversation (à ne pas refaire)

- Put de 8h45 annoncé « entrée possible seulement à 9h00 » : faux, la bougie 8h30-8h45 clôturait déjà sous
  8150. Lire la clôture de CHAQUE bougie 15m.
- **Call de 13h50 oublié** (deux creux égaux 8123, marteau, entrée 14h00 à 8131) : il remplissait la même
  méthode que le call de 8h15. Passer en revue TOUS les creux et sommets touchant une borne, y compris les
  creux égaux et les creux montants, avant de donner le tableau.
- Rapports de volume : le premier calcul incluait la bougie elle-même dans la moyenne (9h00 « 11,7 fois »,
  8h45 « 4,2 fois ») ; la bonne mesure compare aux 20 bougies précédentes (24 fois et 2,2 fois).

## 5. Ce qui a fonctionné ce jour-là (constat, pas une règle)

Borne + bougie + volume : étoiles filantes sous 8152 le matin, cassure en grande bougie verte avec volume,
marteau du retest dans le trou de cotation. Les indicateurs de tendance (EMA20, VWAP) étaient contre les
deux bons calls de 13h00 et 14h00. Une journée ne prouve rien ; les lectures smart money ne sont pas un signal
testé (« CHoCH frais » arrêté le 05/11).
