# Test 7 figé le 09/11/2026 : petit écart d'ouverture dans le sens de la tendance, AVANT tout calcul

Demande de l'utilisateur le 09/11/2026 (« Oui, fige le test »), après la matinée du CAC 40 : ouverture
sous la clôture de la veille, puis +80 points, sans signal de la principale ni des règles d'écart.
**Aucun calcul n'a été fait pour ce test**, seulement une vérification de syntaxe du script. **Non lancé** :
le moratoire du 06/11 (point 12 de `docs/regles_execution.md`) n'est levé que sur l'ordre explicite de le
lancer, comme pour les tests 5 et 6.

## Ce que j'ai vérifié ce matin, et une correction

- Ce matin, le CAC n'a pas ouvert en hausse : la bougie de 9h00 a ouvert à 8 124,5 et clôturé à 8 134, sous
  la clôture de la veille R = 8 147,5. L'écart |C0 − R| = 13,5 points, soit **0,11 ATR** (ATR journalier 123).
- Ni l'écart continue ni le test d'écart rejeté du 27/10 (`gap_fill_test.py`, −44,1R sur 378 trades à 1 pt,
  t = −3,54) ne jouent cette zone : les deux exigent un écart d'au moins 0,25 ATR.
- La principale n'a pas pris de trade : elle exige un balayage d'un **double creux** puis un CHoCH.
  Le plus bas de 9h00 (8 113,5) s'est arrêté à 1 point au-dessus d'un creux isolé (8 112,5).

## Règle testée (une seule règle, paramètres fixés ici, jamais réajustés)

Mêmes séances que `gap_fill_test.py` (Europe 9h00 Paris, États-Unis 9h30 New York), bougies de 15 minutes.

| Élément | Règle |
|---|---|
| Référence R | clôture officielle de la veille (barre 1D) |
| Zone | **\|C0 − R\| < 0,25 × ATR(14) journalier**, C0 = clôture de la 1re bougie de 15 minutes de la séance (le complément de la zone 0,25-1,0 ATR des règles d'écart) |
| Sens | **avec la tendance de la principale** : achat si la clôture de la veille est au-dessus de sa SMA20, vente sinon (`ma_grid_test.trend_up`) |
| Entrée | à C0 |
| Stop | **0,5 × ATR(14)** contre la position |
| Cible | **0,5 × ATR(14)** dans le sens du trade (1:1) |
| Sortie temporelle | clôture de la bougie qui termine 3 heures après l'ouverture |

Une bougie qui touche stop et cible compte comme un stop. Un trade par marché et par jour. Coûts 1 pt et 3 pts
équivalent CAC (facteurs par marché de `frozen_15m_calls_trend.py`). Les paramètres 0,25 / 0,5 / 3 h ont été
choisis avant de voir un seul résultat et ne seront jamais modifiés.

## Critère, fixé avant le calcul

Même base que `gap_fill_test.py`, avec deux conditions de plus (le test est post-hoc). Il faut **toutes** ces
conditions, sur les 10 marchés réunis :

1. au moins **150 trades** ;
2. résultat net en R **> 0 à 1 pt ET à 3 pts** ;
3. les deux moitiés de l'historique (par marché, additionnées) **> 0** à 1 pt ;
4. au moins **6 marchés sur 10** positifs à 1 pt ;
5. résultat à 1 pt **au-dessus du 95e centile** du hasard (jour et sens tirés au hasard, mêmes stop et cible,
   200 tirages) ;
6. t-statistique à 1 pt **≥ 2,45** (Bonferroni 5 % / 7 tests, unilatéral).

Si tout passe : à suivre **sans argent** en avant (100 trades), jamais directement en argent réel. Sinon :
rejeté, sans réglage supplémentaire.

## Limites annoncées

- L'historique 15 minutes disponible ne remonte qu'à mai-août 2026 selon le marché (CAC : 22/05/2026), soit
  environ 5 à 6 mois : l'échantillon sera court, c'est pourquoi la condition 1 exige 150 trades.
- Le test est né d'une seule matinée : il peut très bien être rejeté, et c'est un résultat normal.
- Budget de tests multiples porté à **7 tests** en 2026 ; aucun autre test d'écart d'ouverture ensuite.

Script : `scripts/test_small_gap_trend.py` (docstring identique à cette règle). Résultat dans un commit
séparé de celui-ci, avec la sortie brute.
