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

## Résultat (09/11/2026)

**REJETÉ** : quatre conditions sur six échouent. Sortie brute du script :

```
CAC 40         1pt-eq: n= 61 gagnants= 41% net=  +1.8R | 3pt-eq: n= 61 gagnants= 41% net=  -0.5R
DAX            1pt-eq: n= 46 gagnants= 65% net=  +4.8R | 3pt-eq: n= 46 gagnants= 57% net=  +2.9R
Euro Stoxx 50  1pt-eq: n= 47 gagnants= 47% net=  +1.6R | 3pt-eq: n= 47 gagnants= 45% net=  -0.4R
S&P 500        1pt-eq: n= 26 gagnants= 27% net=  -6.2R | 3pt-eq: n= 26 gagnants= 27% net=  -7.5R
Nasdaq 100     1pt-eq: n= 25 gagnants= 48% net=  -3.7R | 3pt-eq: n= 25 gagnants= 44% net=  -4.4R
FTSE 100       1pt-eq: n= 47 gagnants= 64% net=  +5.7R | 3pt-eq: n= 47 gagnants= 64% net=  +3.5R
SMI            1pt-eq: n= 65 gagnants= 55% net=  +2.3R | 3pt-eq: n= 65 gagnants= 54% net=  -0.5R
Dow Jones      1pt-eq: n= 34 gagnants= 47% net=  -2.3R | 3pt-eq: n= 34 gagnants= 47% net=  -3.9R
Russell 2000   1pt-eq: n= 28 gagnants= 36% net=  -3.9R | 3pt-eq: n= 28 gagnants= 32% net=  -4.9R
FTSE MIB       1pt-eq: n= 46 gagnants= 43% net=  +3.9R | 3pt-eq: n= 46 gagnants= 43% net=  +2.1R

10 marches ensemble: 1pt-eq n=425 gagnants=49% net=+4.0R moy=+0.009R t=+0.35 | 3pt-eq net=-13.5R
  moities -5.7/+9.7R | marches positifs 6/10 | hasard: mediane -9.6R, 95e centile +11.9R

Regle fixee avant: REJETEE
```

| Condition | Résultat | Verdict |
|---|---|---|
| 1. au moins 150 trades | 425 | OK |
| 2. net > 0 à 1 pt ET 3 pts | +4,0R à 1 pt, **−13,5R à 3 pts** | échoue |
| 3. deux moitiés > 0 | **−5,7R** / +9,7R | échoue |
| 4. au moins 6 marchés sur 10 positifs | 6 sur 10 | OK |
| 5. au-dessus du 95e centile du hasard | +4,0R pour **+11,9R** | échoue |
| 6. t ≥ 2,45 | **+0,35** | échoue |

- Le gain moyen est de +0,009R par trade, c'est-à-dire zéro : les gains à 1 point sont plus petits que les
  frais à 3 points (−13,5R). Le résultat (+4,0R) est au-dessus de la médiane du hasard (−9,6R) mais **sous son 95e centile (+11,9R)** : il ne se
  distingue pas d'un tirage aléatoire.
- Les marchés américains perdent (S&P 500 −6,2R, Nasdaq −3,7R, Russell −3,9R, Dow −2,3R), les européens gagnent un peu.
- Aucun autre test d'écart d'ouverture ne sera essayé, quel que soit le résultat (règle du document).
