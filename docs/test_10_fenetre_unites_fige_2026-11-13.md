# Test 10 figé le 13/11/2026 : durées de fenêtre sur bougies de 5 et 30 minutes, AVANT tout calcul

Demande de l'utilisateur du 13/11/2026, après le test 9 : « Je voudrais aussi sur 5mn 15mn et 30mn »,
précisée par sa réponse à la question posée : il s'agit des **unités de temps du graphique**. Moratoire du
06/11 levé pour ce seul test, sur cet ordre. Les 15 minutes sont déjà le test 9
(`docs/test_9_fenetre_fige_2026-11-13.md`), inchangé.

## Ce qui est testé

**10 combinaisons**, fixées maintenant : bougies de **5 minutes** et de **30 minutes** × durées de
**1 h, 2 h, 4 h, 6 h, 8 h** entre le balayage et l'entrée (temps d'horloge).

Référence : la principale (**15 minutes, 4 h**) sur la même période.

Tout le reste est le moteur de la principale avec les mêmes paramètres, calculés sur les bougies de
l'unité : pivots à 2 bougies, stop = le plus grand de (extrême du balayage ± 8 points × facteur du marché)
et de 2 × ATR(14) de l'unité, objectif = poche opposée non balayée la plus proche, rapport net ≥ 1,3,
filtre horaire de Paris, un trade par balayage, calls seulement au-dessus de la moyenne 20 jours, puts
toujours, mêmes 10 marchés, frais de 1 point et de 3 points équivalent CAC.

**Suivi en avant uniquement** : seuls comptent les trades entrés à partir du **13/11/2026 14h00 (Paris)**.
Aucun résultat passé d'aucune unité ni durée n'est calculé ni affiché. La principale n'est pas modifiée.

## Données

- **30 minutes** : construites à partir des bougies de 15 minutes du cache (10 marchés).
- **5 minutes** : construites à partir des bougies d'une minute accumulées (depuis le 22-27/10 selon le
  marché, 16/09 pour le CAC). Contrôle du 13/11 : ces bougies d'une minute, regroupées en 15 minutes,
  redonnent les 15 minutes du cache (aucun quart d'heure manquant sur les 10 marchés).
- Une bougie construite n'est utilisée que lorsque les données sources couvrent toute sa durée.
- Le script compte et affiche les trous dans les bougies d'une minute pendant le suivi.

## Critère, fixé avant le calcul

Verdict quand la référence (15 minutes, 4 h) a **100 trades clos** en avant (coupure = sortie de son 100e
trade ; les combinaisons sont comptées jusqu'à la même coupure). Une combinaison est retenue comme
**nouvelle candidate** seulement si **toutes** ces conditions sont vraies :

1. résultat net supérieur à celui de la référence **à 1 pt ET à 3 pts** ;
2. résultat net avec chaque gain **plafonné à +5R** (1 pt) supérieur à celui de la référence ;
3. son propre résultat net à 3 pts **> 0** ;
4. t-statistique des écarts (combinaison − référence, additionnés par jour d'entrée, 1 pt) **≥ 2,84**
   (Bonferroni 5 % / 22 tests, unilatéral).

Si plusieurs passent : celle au résultat plafonné le plus élevé. Si aucune ne passe : **rien n'est retenu,
et aucune autre unité ni durée ne sera essayée**. Une combinaison retenue ne change pas la principale et ne
passe pas en argent réel : elle commencerait son propre test séquentiel à zéro.

## Limites annoncées

- En 5 minutes les stops sont plus courts : les frais pèsent plus lourd en R, et le nombre de trades est
  plus élevé. En 30 minutes c'est l'inverse. La comparaison se fait en R net, à frais identiques.
- L'historique 5 minutes est court (environ trois semaines avant le départ) : les poches de liquidité plus
  anciennes ne sont pas connues du moteur en 5 minutes.
- Le suivi 5 minutes dépend de l'accumulation des bougies d'une minute : un trou fausserait les bougies
  concernées (compté et affiché à chaque passage).
- 10 combinaisons de plus : budget de tests multiples porté à **22 tests** en 2026, seuil relevé à 2,84.
  À 100 trades de la référence, ce seuil sera difficile à atteindre. C'est voulu.

Script : `scripts/frozen_window_units.py` (docstring identique à cette règle). Première sortie brute dans
un commit séparé.
