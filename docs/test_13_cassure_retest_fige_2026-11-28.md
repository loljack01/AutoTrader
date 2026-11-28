# Test 13 (B4) figé le 28/11/2026 : cassure puis retest d'une borne, AVANT tout calcul

Choix de l'utilisateur le samedi 28/11/2026 : « B4 », puis « OK » sur les 11 points proposés. Règle 29 :
c'est le test de décembre ; la décision formelle et le calcul ont lieu le **dimanche 6/12/2026** (le script
refuse de calculer avant). Aucun autre test en décembre sauf levée explicite et écrite de la limite.

## Origine

Séance du 27/11 (FCE1!) : la borne 8150-8155, rejetée 4 fois le matin, est cassée à 16h00 en grande bougie
verte avec du volume (2,7 fois la moyenne), retestée à 17h32 (creux 8153,5 dans le trou de cotation), puis
le cours monte jusqu'à 8189,5. Idée venue d'une seule journée : fort risque de biais d'après coup.

## La règle (script `scripts/test_13_cassure_retest.py`, figé avant le premier lancement)

| N° | Élément | Règle |
|---|---|---|
| 1 | Bornes connues à 8h00 | plus haut et plus bas de la veille ; SMA20 journalière ; zones touchées au moins 3 fois dans les 3 séances précédentes (groupes d'au moins 3 sommets ou creux isolés 15m à 3 points ou moins, niveau = moyenne) ; bornes à 2 points ou moins fusionnées |
| 2 | Cassure | clôture 15m au-delà de la borne d'au moins 3 points, la clôture précédente étant de l'autre côté (ou dessus) |
| 3 | Volume | volume de la bougie de cassure > 1,5 fois la moyenne des 20 bougies 15m précédentes |
| 4 | Retest | dans les 16 bougies suivantes, retour à moins de 3 points de la borne ; une clôture de l'autre côté de la borne annule le montage |
| 5 | Entrée | à la clôture de la première bougie de retest qui clôture dans le sens de la cassure (verte pour un call, rouge pour un put) |
| 6 | Sens | calls (cassure par le haut) et puts (cassure par le bas) |
| 7 | Stop | 2 points de l'autre côté de la borne |
| 8 | Cible | 1,5 R ; la borne suivante si elle est plus proche et à au moins 1 R |
| 9 | Heures | entrées sur les clôtures de 8h15 à 21h30 ; sortie au plus tard à 22h00 ; 3 points de frais ; une position à la fois ; stop et cible dans la même bougie : stop d'abord |
| 10 | Données | tout le cache 15m du FCE1! jusqu'au vendredi 4/12/2026 inclus |
| 11 | Critère | moins de 30 trades : non concluant ; total > 0 et t ≥ 3,25 (Bonferroni, 86 décisions) : retenue pour un suivi en avant sans argent ; total > 0 et 2 ≤ t < 3,25 : prometteuse, décision de l'utilisateur un dimanche ; sinon rejetée |

Informations sans effet sur le verdict : calls et puts séparés, résultat avant frais, sans les 3 meilleurs
trades, pire écart, motifs de sortie.

Quel que soit le verdict : **aucun argent réel** (seul le swing est joué en réel) et aucune règle de
stratégie figée n'est modifiée. Vérification du code sur des barres fictives seulement (pas de données de
marché) avant le figement.

## Résultat

(à remplir le 6/12/2026 après le calcul)
