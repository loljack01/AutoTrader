# Test 8 figé le 10/11/2026 : stop suiveur structurel sur la principale, AVANT tout calcul

Demande de l'utilisateur du 10/11/2026 (« Exécute tes recommandations »), après l'audit trade par trade
(`docs/audit_trades_principale_2026-11-10.md`). La recommandation était : ne modifier aucune règle, et
figer la seule piste jamais testée, pour la lancer un dimanche.

**Non lancé.** Seul le contrôle de reproduction a été exécuté (`--controle`) : il re-parcourt les trades
de la base sans stop suiveur et vérifie qu'on retrouve les mêmes résultats (348 trades à 1 pt, 310 à
3 pts : identique). Il n'affiche aucun résultat de la variante. Lancement : un dimanche, sur l'ordre
explicite de l'utilisateur (moratoire du 06/11, point 12 de `docs/regles_execution.md`).

## D'où vient l'idée, et ce que cela impose

L'audit du 10/11 a montré que 9 des 30 trades stoppés du suivi (28/10 → 09/11) étaient allés à +1R ou plus
avant de revenir au stop, et que les trades ouverts ont rendu de gros gains latents. L'idée est donc née
des trades entrés **à partir du 28/10**. Pour ne pas la juger sur les données qui l'ont inspirée, le test
est jugé **seulement sur les trades entrés avant le 28/10/2026**, que l'audit n'a pas regardés.

Sa cousine (stop ramené à l'entrée à +1R) a été rejetée le 26/10 (`scripts/exit_variants_test.py`,
registre ligne 11). La sortie partielle n'est pas testée : avec des ordres de 500 €, vendre la moitié
ferait un ordre de 250 €, sous le minimum de gratuité.

## Règle testée (un seul changement, paramètres repris du moteur, jamais réajustés)

Base : la principale telle que figée (SMA20 : calls avec la tendance, puts toujours), 10 marchés, bougies
de 15 minutes. Les entrées sont celles de la base ; seule la sortie change.

| Élément | Règle |
|---|---|
| Armement | dès qu'une bougie après l'entrée atteint **+1R** dans le sens du trade |
| Stop suiveur | à chaque clôture, le stop passe au **dernier creux confirmé formé après l'entrée, moins la marge du moteur** (8 points équivalent CAC × le facteur du marché), si ce niveau est au-dessus du stop en cours et sous la clôture. Pour un put : dernier sommet confirmé plus la marge |
| Creux confirmé | celui du moteur : plus bas strictement inférieur aux 2 précédents et pas supérieur aux 2 suivants, confirmé 2 bougies plus tard |
| Sens unique | le stop ne recule jamais ; il s'applique à partir de la bougie suivante |
| Sorties | stop (d'origine ou suiveur) ou **objectif d'origine** ; stop d'abord si une bougie touche les deux |
| Résultat | sens × (sortie − entrée) / risque initial − frais / risque initial |

Frais de 1 point et de 3 points équivalent CAC.

## Critère, fixé avant le calcul

Sur les trades clos entrés **avant le 28/10/2026**, 10 marchés réunis, il faut **toutes** ces conditions :

1. résultat net de la variante **supérieur à celui de la base à 1 pt ET à 3 pts** ;
2. la même chose à 1 pt sur **les deux moitiés** de l'historique (moitiés par marché, additionnées) ;
3. avec chaque résultat **plafonné à +5R** (la mesure du passage en réel) : variante supérieure à la base à 1 pt ;
4. variante au moins égale à la base sur **au moins 6 marchés sur 10** à 1 pt ;
5. t-statistique des écarts (variante − base), additionnés par jour d'entrée, **≥ 2,50** à 1 pt
   (Bonferroni 5 % / 8 tests, unilatéral).

Si tout passe : **nouvelle candidate suivie sans argent** en avant (verdict à 100 trades clos face à la
principale, comme les variantes A à D). La principale n'est pas modifiée et rien ne passe en argent réel.
Sinon : rejetée, sans réglage supplémentaire (aucun autre seuil d'armement, marge ou longueur de creux).

## Limites annoncées

- Les entrées sont celles de la base : une place libérée plus tôt par le stop suiveur n'est pas réutilisée.
- Les sorties sont remplies au niveau du stop, comme dans le moteur de base (pas d'écart d'ouverture).
- L'historique 15 minutes ne remonte qu'à mai-août 2026 selon le marché.
- Budget de tests multiples porté à **8 tests** en 2026. Les trades entrés depuis le 28/10 sont affichés
  pour information seulement.

Script : `scripts/test_trailing_stop.py` (docstring identique à cette règle). Résultat dans un commit
séparé, avec la sortie brute.
