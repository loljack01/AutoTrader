# Test 12 figé le 26/11/2026 : retournement confirmé sur une borne, AVANT tout calcul

Décision de l'utilisateur du jeudi 26/11/2026 (« Les 2 ») : rédiger la fiche ET lever la limite de recherche
de novembre (règle 29) pour ce seul test. Novembre était consommé (tests 9, 10, 11 et audits du 14/11) ; ce
test compte comme un test supplémentaire de novembre, la limite de décembre reste entière (un test, décidé
le dimanche 6/12).

## Origine

Séance du 26/11 (FCE1!) : quatre grands mouvements de 30 à 55 points ont tous tourné sur une borne connue
(faux passage sous 8100 à 8h55 puis hausse jusqu'à 8151 ; double sommet sous la SMA20 puis baisse jusqu'à
8106 ; etc.). La lecture « entrée sur retournement confirmé aux bornes, stop derrière le retournement, vente
à la zone suivante » donnait +87,5 points bruts ce jour-là, la règle des tableaux après coup −6,5. Une seule
journée ne prouve rien : on mesure sur tout l'historique en cache.

Proche de deux familles déjà vues : les scénarios de réaction aux niveaux (rejetés le 05/11) et le « simple
balayage » (suivi sans argent, verdict ABANDONNÉE au seuil de 100 trades). Ce test doit faire mieux qu'elles.

## La règle (script `scripts/test_12_retournement_bornes.py`, figé avant le premier lancement)

| Élément | Règle |
|---|---|
| Marché, données | CAC 40, FCE1! en 15 minutes, séance 8h00-22h00 (règle 35) |
| Niveaux connus à 8h00 | règlement, plus haut, plus bas de la veille ; plus haut et plus bas de la semaine (jours clos) ; SMA20 journalière ; sommets et creux isolés 15m (2 bougies de chaque côté) des 3 séances précédentes ; chiffres ronds de 50 ; fusion à 2 points ; gardés à ±1,5 ATR14 journalier du règlement |
| Borne (balayage) | une bougie 15m fait le plus bas (call) ou le plus haut (put) des 16 dernières bougies (4 h) et passe au-delà d'un niveau connu |
| Retournement confirmé | une clôture 15m revient de l'autre côté de ce niveau, sur la même bougie ou l'une des 2 suivantes ; entrée à cette clôture |
| Stop | 2 points au-delà de l'extrême du balayage |
| Vente | au premier niveau connu qui donne au moins 1,5 R net de 3 points de frais ; sans un tel niveau, pas de trade |
| Heures | entrées sur les clôtures de 8h15 à 21h30, jamais à 9h00, 15h30, 15h45, 17h15, 17h30 ; sortie au plus tard à 22h00 |
| Divers | une position à la fois ; stop et objectif dans la même bougie : stop d'abord ; call prioritaire si les deux à la fois ; annonces non filtrées (pas de calendrier historique) |
| Frais | 3 points par trade |

## Critère, fixé avant calcul

Période jugée : tout le cache 15m du FCE1! jusqu'au 25/11/2026 inclus (le 26/11 est exclu, l'idée en vient).

- Moins de 30 trades : **non concluant**.
- Total en R > 0 **et** t ≥ 3,24 (seuil de Bonferroni du registre, 85 décisions) : **retenue pour un suivi
  en avant sans argent**, à partir de la décision écrite de l'utilisateur.
- Total > 0 et 2 ≤ t < 3,24 : **prometteuse, non prouvée** ; décision de l'utilisateur (un dimanche).
- Sinon : **rejetée**.

Informations sans effet sur le verdict : calls et puts séparés, sans les 3 meilleurs trades, avant et
depuis le 28/10, pire écart, motifs de sortie.

Quel que soit le verdict : **aucun argent réel** (seul le swing est joué en réel) et aucune règle de
stratégie figée n'est modifiée.

## Résultat (calculé le 26/11/2026 après le commit e7b999b qui fige la règle)

| Mesure | Valeur |
|---|---|
| Période | 22/05/2026 au 25/11/2026, 134 jours avec trade |
| Trades | 630 (210 gagnants, 33 %) |
| Total à 3 points | **−193,5 R**, moyenne −0,31 R, **t −5,48** |
| Calls / puts | −108,7 R (327) / −84,8 R (303) |
| Sans les 3 meilleurs | −204,7 R |
| Avant le 28/10 / depuis | −154,2 R (547 trades) / −39,3 R (83 trades) |
| Sorties | stop 399, objectif 159, fin de séance 72 |

**Verdict (critère fixé avant) : REJETÉE.** Le retournement mécanique « balayage d'un niveau au plus haut
ou plus bas de 4 heures, puis clôture revenue » perd nettement et de façon significative sur le CAC en 15m :
il se déclenche environ 4,7 fois par jour et finit au stop 6 fois sur 10. La lecture du 26/11 (+87,5 points)
reposait sur des bornes choisies après coup ; elle ne se reproduit pas avec une définition objective connue
à 8h00. Aucune variante n'est calculée (ce serait un nouveau test, règle 29).

## Audit critique (26/11, relecture des 630 trades, sans nouveau calcul de règle)

- Avant frais, le signal est nul : −17,5 R bruts, −0,03 R par trade. Les frais (3 points pour un risque
  médian de 13 points, soit 0,28 R par trade) font presque toute la perte. Taux de réussite 33 % pour un
  équilibre vers 44 %.
- Fidélité à l'idée de l'utilisateur : FAIBLE. Les « bornes » codées (tout niveau d'une liste dense, balayé
  au plus haut ou plus bas de 4 heures) ne sont pas les bornes majeures lues le 26/11 (SMA20, plus haut et
  plus bas de la veille, zones touchées plusieurs fois). D'où 4,7 trades par jour (11 au plus) et des
  reprises après stop sur la même zone. Les paramètres (16 bougies, 3 bougies de confirmation, marge de
  2 points, 1,5 R) ont été choisis sans justification ni question à l'utilisateur ; la question du sens
  (point 7 de la proposition) a été tranchée seule. Le test rejette donc cette version, pas toute l'idée.
- Ce qui reste solide : sur 630 occasions, « balayage puis reprise » n'a aucun avantage avant frais sur le
  CAC 15m ; c'est le deuxième échec de la famille « réaction aux niveaux » (après le 05/11). Le +87,5 du
  26/11 venait de bornes choisies après coup.
- Tranches (information, pas des règles) : 15h-18h +9,1 R sur 131 trades (+0,07 R) ; 8h-9h −40,1 R ;
  18h-22h −37,5 R ; le premier trade du jour est le plus mauvais (−0,48 R). Choisir une tranche après coup
  serait de l'ajustement.
- Toute version plus stricte serait un nouveau test (règle 29, décembre, décision le 6/12), à définir
  entièrement AVANT calcul avec l'utilisateur ; probabilité de succès a priori faible.
