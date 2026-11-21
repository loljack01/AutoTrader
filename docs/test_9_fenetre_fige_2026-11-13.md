# Test 9 figé le 13/11/2026 : durée de la fenêtre balayage → retournement, AVANT tout calcul

Demande de l'utilisateur du 13/11/2026, en séance, après l'analyse de la matinée CAC (aucun balayage,
dernier balayage vieux de plus de 4 h) : « Peut-on optimiser le 4h figé » puis « optimise sur les séances
en cours ». Moratoire du 06/11 levé pour ce seul test, sur cet ordre.

## D'où vient la question

La principale n'entre que si le retournement de structure (CHoCH) suit le balayage de moins de **4 h**.
Cette durée n'a jamais été optimisée : c'est une convention du 07/10 (16 bougies de 15 minutes), passée
en heures d'horloge le même jour pour qu'un balayage du soir ne déclenche pas le lendemain matin. Seule
une fenêtre de 1 h a été essayée (27/10, `scripts/improved_15m_test.py`) ; elle n'a pas tenu.

## Ce qui est testé

Cinq durées, fixées maintenant : **1 h, 2 h, 4 h (référence = la principale), 6 h, 8 h**. 8 h est la plus
longue qui ne fait jamais passer un balayage par-dessus la nuit européenne (22 h → 8 h = 10 h). Tout le
reste est la principale : même moteur, mêmes 10 marchés, mêmes facteurs, mêmes frais, calls seulement
au-dessus de la moyenne 20 jours, puts toujours.

**Suivi en avant uniquement** : seuls comptent les trades entrés à partir du **13/11/2026 11h00 (Paris)**.
Aucun résultat passé d'aucune durée n'est calculé ni affiché : le choix ne peut donc pas se faire sur des
données déjà vues. La principale n'est pas modifiée.

## Critère, fixé avant le calcul

Verdict quand la référence 4 h a **100 trades clos** en avant (coupure = sortie de son 100e trade ; les
autres durées sont comptées jusqu'à la même coupure). Une durée est retenue comme **nouvelle candidate**
seulement si **toutes** ces conditions sont vraies :

1. résultat net supérieur à celui de la référence 4 h **à 1 pt ET à 3 pts** ;
2. résultat net avec chaque gain **plafonné à +5R** (1 pt) supérieur à celui de la référence ;
3. son propre résultat net à 3 pts **> 0** ;
4. t-statistique des écarts (durée − référence, additionnés par jour d'entrée, 1 pt) **≥ 2,64**
   (Bonferroni 5 % / 12 tests, unilatéral).

Si plusieurs passent : celle au résultat plafonné le plus élevé. Si aucune ne passe : **4 h reste, et
aucune autre durée ne sera essayée**. Une durée retenue ne change pas la principale et ne passe pas en
argent réel : elle commencerait son propre test séquentiel à zéro.

## Limites annoncées

- Les durées ne diffèrent que sur une partie des trades (ceux dont le retournement arrive entre 1 h et
  8 h après le balayage) : à 100 trades, la condition 4 sera difficile à atteindre. C'est voulu.
- Un trade ouvert bloque les entrées suivantes du même sens sur son marché : les durées ne prennent donc
  pas exactement les mêmes trades, même hors de la fenêtre.
- Budget de tests multiples porté à **12 tests** en 2026 (4 durées nouvelles).

Script : `scripts/frozen_15m_window.py` (docstring identique à cette règle). Première sortie brute dans un
commit séparé.
