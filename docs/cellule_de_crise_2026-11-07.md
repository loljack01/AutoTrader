# Cellule de crise du 07/11/2026 : ce qui est défaillant

Demande de l'utilisateur : « Cellule de crise pour tout le groupe pour analyser ce qui est
défaillant ». Ce document ne change aucune règle (moratoire, une modification par semaine
le dimanche). Il constate, chiffre et propose. Les décisions reviennent à l'utilisateur.

Vérifications refaites le 07/11 :
- taille réelle du swing : script du scratchpad, carnet de référence de 1 124 trades, 2012 → 06/11/2026 ;
- rejeu du contrôle avant clôture : `audit/2026-11-06/execution/replay_preclose.py` relancé avec le
  `swing_preclose.py` corrigé (91 séances, du 01/07 au 05/11/2026) ;
- historique git.

Participants : statisticien, gestionnaire du risque, spécialiste des turbos, responsable de
l'exécution et des données, développeur des outils, trader indices, fiscaliste, coach de discipline,
responsable de la méthode.

## Verdict

| Bloc | État | Fait vérifié |
|---|---|---|
| Taille en argent réel (décision du 07/11) | **défaillant** | perte au stop variable de 25 à 90 € (médiane 39 €) ; pire trimestre historique −489 € pour une limite de −500 € ; frein et arrêt du jour comptés en R fixe de 45 € alors que le R réel varie |
| Produits pour exécuter le swing | **défaillant** | turbo identifié pour le CAC 40 seulement ; les indices américains font 67 % du gain historique et n'ont aucun produit choisi |
| Contrôle avant clôture | fragile, en progrès | entrées : 8 faux signaux et 5 manqués (contre 11 et 5 avant correction) ; « A CONFIRMER » sur 43 lignes sur 86, sans règle sur ce qu'il faut faire dans ce cas |
| Stabilité des règles | **défaillant** | 46 commits depuis le 04/11 ; 25 modifications des 4 fichiers de l'argent réel en 4 jours ; règle de taille changée 3 fois ; décision de taille prise un samedi alors que la règle du point 12 dit « le dimanche » |
| Documents | défaillant | `regles_execution.md` : points 7, 9 et 14 (25 €, phase 2 à 37,5 €) en contradiction avec le point 15 (45 €) ; docstrings de `risk_guard.py` et `frozen_swing_rsi2.py` encore à 25 € ; chiffres du point 15 calculés à R fixe |
| Compréhension du produit | fragile | question du 07/11 « pourquoi l'exposition est de 1 400 € ? » posée alors que l'argent réel est déjà engagé |
| Avantage du swing | faible mais réel | t = 0,27 depuis 2018 ; environ +220 € par an avant impôt avec la taille actuelle |
| Discipline de l'utilisateur | **tient** | zéro ordre hors système depuis le 22/10 ; journaux et contrôles en place |
| Données et références | tient | contrôles de référence OK ; erreur du cours de substitution (proxy) : médiane 0,10 %, 90e centile 0,26 % |

## 1. Taille : la décision du 07/11 a été chiffrée trop vite (gestionnaire du risque, statisticien)

Avec 500 € engagés à un levier fixe de 2,8, l'exposition est **constante (1 400 €)**. Le risque ne
l'est plus : la perte au stop vaut 1 400 € × la distance du stop, et cette distance va de 1,2 % à 6,4 %
selon la volatilité. Le 07/11, j'ai converti les R en euros à 44 € par R fixe. Le calcul trade par trade
donne ceci :

| Taille (historique 2012-2026, 1 124 trades) | Gain/an | Pire 3 mois | Pire baisse | Perte au stop (médiane / maximum) | Pire trade |
|---|---|---|---|---|---|
| A. risque fixe 25 € (règle du 06/11) | +120 € | −326 € | −781 € | 25 / 25 € | — |
| **B. 500 € × levier 2,8 (choix du 07/11)** | **+220 €** | **−489 €** | **−1 063 €** | **39 / 90 €** | **−129 €** (écart d'ouverture sous le stop) |
| C. 500 € au levier = exposition / 500 (≥ 1) | +120 € | −326 € | −781 € | 25 / 32 € | — |

Ce que ces chiffres montrent :
- Les chiffres annoncés le 07/11 étaient faux : +211 €/an, pire trimestre −573 €, une atteinte de
  −500 € en 14 ans. Le calcul réaliste donne +220 €/an, un pire trimestre de −489 €, aucune atteinte,
  et une pire baisse de −1 063 €. Le pire trimestre est à 11 € de la limite : sur un historique de
  14 ans, la marge est nulle.
- La solution C retrouve exactement les risques du 06/11 tout en gardant **500 € par ordre**. Elle
  suppose un turbo de levier 1,2 à 2,5, médiane 1,8. Le problème n'est donc pas le montant de 500 €,
  c'est **le levier minimum de 2,79 du turbo Boursomarkets**.
- Les garde-fous comptent en R fixe de 45 € (`risk_guard.py` : arrêt du jour à −3R, calcul de
  secours = R × 45 €). Avec un R réel de 25 à 90 €, « −3R » peut valoir de −75 € à −270 €. Le frein
  du swing (−10R) n'a plus de valeur en euros fixe : quand la baisse historique atteint −31,3R, elle
  vaut −1 007 €.

## 2. Produits : le swing n'est exécutable que sur le CAC 40 (spécialiste des turbos, trader indices)

Un seul produit est identifié : le turbo call CAC 40 Boursomarkets, prix d'exercice 5 250, levier 2,79.
Les indices américains font 67 % du gain historique et n'ont aucun turbo retenu. Si un signal arrive
lundi sur le S&P 500, il sera « non exécutable ». Il faut aussi vérifier deux choses avant tout
achat : la gratuité des ordres (0 € dès 500 €) vaut-elle pour les turbos des autres émetteurs (SG,
BNP, Vontobel…), qui proposent souvent des leviers de 1,5 à 2 ? Ou seulement pour Boursomarkets ?

## 3. Contrôle avant clôture : mieux, mais « A CONFIRMER » ne dit pas quoi faire (exécution, développeur)

Rejeu refait le 07/11 avec le script corrigé du 06/11 :

| | Avant correction (audit du 06/11) | Après correction (07/11) |
|---|---|---|
| Entrées : concordantes / fausses / manquées | — / 11 / 5 sur 41 | 30 / 8 / 5 (bilan : 35) |
| Erreurs d'entrée signalées « A CONFIRMER » | — | 9 sur 13 |
| Sorties à la clôture manquées ou fausses | — | 8, toutes signalées « A CONFIRMER » |
| Lignes « A CONFIRMER » | — | 43 sur 86 |

Le signal « A CONFIRMER » attrape bien les erreurs. Mais il s'allume une fois sur deux, et aucune
règle ne dit s'il faut passer l'ordre ou non. À 17h25, l'utilisateur doit décider seul, donc au
feeling. C'est le trou opérationnel principal. Restent 4 erreurs d'entrée non signalées en 4 mois.

## 4. Stabilité et documents (responsable de la méthode, coach)

- Depuis le 04/11 : 46 commits, dont 19 depuis le 06/11 ; 25 modifications de `regles_execution.md`,
  `swing_preclose.py`, `risk_guard.py` et `frozen_swing_rsi2.py`.
- La règle de taille a changé trois fois en deux jours : 25 €, puis 25 € avec un ordre de 500 €,
  puis environ 45 €. Le point 12 (une modification par semaine, le dimanche) a été contourné le
  samedi 07/11, à la demande de l'utilisateur, mais sans le chiffrage complet ci-dessus.
- Les documents se contredisent : selon le paragraphe lu, on trouve 25 €, 37,5 € ou 45 €. Pour
  quelqu'un qui passe ses ordres depuis un téléphone à 17h25, c'est une source d'erreur directe.
- Charge : 6 routines par jour et 8 stratégies suivies, dont 7 sans argent. La principale a environ
  1 % de chances de passer : son suivi prend de l'attention sans aider à la seule stratégie jouée en
  argent.

## 5. Ce qui tient

Zéro ordre hors système depuis le 22/10. Règle anti-revanche écrite. Journaux avec contrôles. Limite
globale de −500 € sur 3 mois. Références des scripts identiques. Moratoire respecté sur les idées de
stratégie. La défaillance vient de l'outillage et du rythme des changements, pas de l'utilisateur.

## Propositions (à décider par l'utilisateur ; rien n'est appliqué)

1. **Taille** : chercher un turbo call de levier 1,5 à 2 (autres émetteurs, en vérifiant les frais)
   pour revenir au risque de 25 € avec 500 € engagés (solution C). En attendant, garder 500 € × 2,8
   mais ne pas dépasser 3 positions ouvertes en même temps, ou accepter la marge nulle face à
   −500 € en connaissance de cause.
2. **Garde-fous en euros** : `risk_guard.py` et le frein du swing en euros (arrêt du jour à −135 €,
   frein à −450 €) ; résultat de secours = 1 400 € × variation de l'indice. C'est une correction
   d'outillage, sans changement de règle de trading.
3. **Règle « A CONFIRMER »** : la fixer dimanche, après mesure sur le rejeu (par exemple : on passe
   l'ordre quand même, et le bilan du soir corrige à l'ouverture suivante ; ou on s'abstient).
4. **Produits** : avant le premier ordre, un ISIN par indice ; à défaut, l'indice est marqué
   « non exécutable ».
5. **Gel des documents** : un seul paragraphe « taille en vigueur » en tête de `regles_execution.md`,
   les anciens points barrés ; plus aucun changement avant dimanche.
6. **Allègement** : réduire le bilan du soir aux stratégies en argent plus une ligne pour les autres.
