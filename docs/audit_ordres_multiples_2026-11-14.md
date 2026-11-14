# Audit du 14/11/2026 : l'intraday avec plusieurs ordres sur un même indice

Demande de l'utilisateur du 14/11/2026 : « Refais un audit complet sur stratégie intraday avec plusieurs
ordres sur un même indice ». Document de mesure : **aucune règle n'est modifiée ni adoptée**. Les mesures
ont été fixées et poussées avant le calcul (commit `Freeze audit of 14/11`), puis calculées.

Reproduire : `python3 -W ignore audit/2026-11-14/ordres_multiples.py` (sortie brute :
`audit/2026-11-14/out_ordres_multiples.txt`, détail : `ordres_multiples_trades.csv`).

Périmètre : stratégie principale (15 minutes, SMA20), 10 marchés, données jusqu'au 13/11/2026 à 22h00.
Deux périodes : **avant le 28/10** (historique, déjà exploité pour construire les règles, donné pour
information) et **depuis le 28/10** (suivi sans argent). Contrôle : le simulateur de l'audit, limité à un
trade à la fois, redonne exactement les trades du moteur sur 80 configurations sur 80.

## Ce que fait la principale aujourd'hui

| | |
|---|---|
| Trades ouverts à la fois | 1 par indice et par sens (un call et un put peuvent coexister) |
| Ordres par signal | 1 |
| Jours × indice avec au moins un trade | 306 : **251 avec un seul trade**, 47 avec deux, 8 avec trois ou plus |
| Durée d'un trade clos | médiane 6,8 h ; un quart dure moins de 2,2 h, un quart plus de 22 h ; maximum 43 jours |
| Signaux ignorés parce qu'un trade du même sens était ouvert | environ 120 avant le 28/10, 18 depuis |

La principale n'est donc pas strictement intraday : un trade sur quatre passe au moins une nuit.

## 1. Plusieurs trades ouverts en même temps sur le même indice

Un signal qui arrive pendant qu'un trade du même sens est ouvert n'est plus ignoré.

**Depuis le 28/10 (suivi), frais de 1 point :**

| Version | Trades clos | Net | Net à 3 pts | Gains plafonnés à 5R | Pire creux | Jours à −3R ou pire |
|---|---|---|---|---|---|---|
| Base (1 à la fois) | 66 | +7,43R | +4,34R | +3,34R | −12,78R | 3 |
| 2 au maximum | 78 | +11,55R | +4,39R | +5,05R | −15,24R | 4 |
| 3 au maximum | 82 | +7,41R | −0,03R | +0,91R | −17,32R | 6 |
| Sans limite | 82 | +7,41R | −0,03R | +0,91R | −17,32R | 6 |

**Avant le 28/10 (historique, information), frais de 1 point :**

| Version | Trades clos | Net | t par trade | Gains plafonnés à 5R | Pire creux | Jours à −3R ou pire |
|---|---|---|---|---|---|---|
| Base (1 à la fois) | 299 | +97,90R | 1,85 | +41,69R | −15,82R | 13 |
| 2 au maximum | 359 | +123,77R | 2,21 | +58,16R | −22,71R | 14 |
| 3 au maximum | 396 | +129,54R | 2,27 | +63,92R | −32,06R | 18 |
| Sans limite | 418 | +122,85R | 2,14 | +57,23R | −37,15R | 19 |

**Les trades ajoutés, pris seuls** (ceux que la base ignore) :

| Période | Frais | Trades | Gagnants | Net | Moyenne par trade | t |
|---|---|---|---|---|---|---|
| Avant le 28/10 | 1 pt | 123 | 39 | +21,27R | +0,173R | 0,93 |
| Avant le 28/10 | 3 pts | 115 | 38 | +18,92R | +0,165R | 0,83 |
| Depuis le 28/10 | 1 pt | 16 | 4 | −0,02R | −0,001R | 0,00 |
| Depuis le 28/10 | 3 pts | 14 | 2 | −4,37R | −0,312R | −0,50 |

Constats :

- Les trades ajoutés valent **moins** que ceux de la base : +0,17R en moyenne dans l'historique contre
  +0,33R, et zéro ou négatif depuis le 28/10. Aucun de ces chiffres ne se distingue du hasard.
- Le risque monte plus vite que le gain : dans l'historique, le pire creux passe de −15,8R à −37,2R sans
  limite, pour un gain qui passe de +97,9R à +122,9R.
- Ce sont presque tous des puts (125 trades ajoutés sur 139) : plusieurs puts sur le même indice sont le
  même pari, pris plusieurs fois.
- Jusqu'à 6 trades du même sens ouverts ensemble dans l'historique, 3 depuis le 28/10.

**Sur la partie exécutable en turbo (variante D : entrées 8h-21h30, sortie à 21h45 au plus tard)**, la
question ne se pose presque pas : 14 trades ajoutés avant le 28/10 (+3,45R à 1 pt), **aucun depuis le
28/10**. Comme tout est vendu le soir, il est rare qu'un trade soit encore ouvert quand le signal suivant
arrive. Les résultats de D sont identiques avec 1, 2, 3 trades ou sans limite depuis le 28/10.

## 2. Plusieurs ordres pour un même signal

Mêmes entrées que la base, deux ordres de même taille.

- **Sortie partielle** : un ordre sort à +1R, l'autre garde la cible ; stop d'origine pour les deux.
- **Renfort** : à la première clôture à +1R ou mieux, un second ordre est ajouté, avec la même cible et un
  stop au prix d'entrée du premier.

| Période, frais | Version | Net | t par trade | Gains plafonnés à 5R | Pire creux | Jours à −3R ou pire |
|---|---|---|---|---|---|---|
| Avant le 28/10, 1 pt | Base | +97,90R | 1,85 | +41,69R | −15,82R | 13 |
| | Sortie partielle | +56,55R | 1,83 | +38,74R | −10,10R | 4 |
| | Renfort (137 posés) | +114,21R | 1,72 | +5,46R | −33,96R | 20 |
| Depuis le 28/10, 1 pt | Base | +7,43R | 0,45 | +3,34R | −12,78R | 3 |
| | Sortie partielle | +1,59R | 0,14 | +1,59R | −9,67R | 3 |
| | Renfort (24 posés) | +18,23R | 0,74 | −0,79R | −16,13R | 3 |
| Depuis le 28/10, 3 pts | Base | +4,34R | 0,26 | +0,43R | −12,32R | 3 |
| | Sortie partielle | −2,48R | −0,22 | −2,48R | −9,73R | 4 |
| | Renfort | +13,74R | 0,56 | −4,78R | −16,01R | 3 |

Constats :

- 54 % des trades clos (196 sur 365) ont atteint +1R avant leur sortie ; 74 d'entre eux ont fini au stop.
- **La sortie partielle** lisse les résultats (creux et mauvaises journées réduits) mais retire environ
  40 % du gain, parce que l'avantage de la principale vient de quelques gros gagnants. Le t reste le même
  (1,85 contre 1,83) : c'est l'équivalent d'une taille plus petite, pas une meilleure stratégie. Depuis le
  28/10 elle est à peine positive à 1 pt et négative à 3 pts.
- **Le renfort** augmente le total, mais tout vient de quelques très gros trades : avec les gains
  plafonnés à 5R (la mesure du passage en réel), il tombe à +5,5R dans l'historique et passe sous zéro
  depuis le 28/10. Le pire creux double.

## 3. Taille et risque en turbo

| | Quart | Médiane | Trois quarts |
|---|---|---|---|
| Distance du stop (en % du cours) | 0,25 % | 0,34 % | 0,43 % |
| Perte au stop, ordre de 500 EUR, levier 2,8 | 3,4 EUR | 4,7 EUR | 6,1 EUR |
| Perte au stop, ordre de 500 EUR, levier 5 | 6,1 EUR | 8,4 EUR | 10,8 EUR |
| Perte au stop, ordre de 500 EUR, levier 10 | 12,3 EUR | 16,8 EUR | 21,7 EUR |

- Frais d'un aller-retour : 1 point = 0,037R, 3 points = 0,112R (médianes).
- Plusieurs ordres de 500 EUR sur le même indice sont possibles en taille : trois ordres au levier 2,8
  engagent 1 500 EUR pour environ 14 EUR de risque. Mais ce risque est **entièrement lié** : les trois
  ordres gagnent ou perdent ensemble.
- À 4,7 EUR par R, les +7,43R du suivi depuis le 28/10 représentent environ +35 EUR pour 66 ordres.

## 4. Valeur statistique

- 8 mesures de plus au registre (78 décisions cumulées, seuil t ≥ 3,22). Le meilleur t de cet audit est
  2,27, sur un historique déjà exploité ; depuis le 28/10, tous les t sont entre −0,5 et +0,74.
- L'historique d'avant le 28/10 a servi à construire les règles : ses chiffres ne valident rien.
- Depuis le 28/10 il n'y a que 16 trades ajoutés : trop peu pour conclure, dans un sens comme dans l'autre.

## 5. Suite : la règle d'alternance de l'utilisateur

Précision de l'utilisateur après lecture des sections 1 à 4 : « Il ne peut y avoir 2 calls en même temps et
2 puts en même temps. Si on est en call, derrière on fait un put. Si on a un put, derrière on fait un
call. » Les sections 1 et 2 mesuraient donc autre chose (des ordres du même sens empilés). Mesures de
cette section fixées et poussées avant le calcul (commit `Freeze audit of 14/11 (continued)`).

Reproduire : `python3 -W ignore audit/2026-11-14/alternance.py` (sortie brute : `out_alternance.txt`,
détail : `alternance_trades.csv`). Contrôle : sans alternance ni retournement, le simulateur redonne les
trades du moteur sur 40 configurations sur 40.

Variantes, appliquées aux signaux de la principale sans rien changer d'autre :

- **A, alternance stricte** : sur un indice, un signal n'est pris que s'il est de sens opposé au dernier
  trade pris sur cet indice.
- **Aj, alternance du jour** : même règle, remise à zéro chaque matin.
- **R, retournement** : un signal de sens opposé pris pendant qu'un trade est ouvert ferme ce trade.
- **A+R** et **Aj+R** : les deux ensemble (une seule position à la fois sur l'indice).

État des lieux de la base : 60 % des trades (216 sur 360) sont de même sens que le trade précédent sur le
même indice ; 261 puts pour 109 calls ; 60 fois un call et un put ont été ouverts en même temps.

**Principale, depuis le 28/10 (suivi) :**

| Version | Trades clos | Net à 1 pt | Net à 3 pts | Gains plafonnés à 5R | Pire creux | Jours à −3R ou pire |
|---|---|---|---|---|---|---|
| Base | 66 | +7,43R | +4,34R | +3,34R | −12,78R | 3 |
| A alternance stricte | 40 | +8,55R | +8,03R | +4,46R | −7,98R | 1 |
| Aj alternance du jour | 62 | +3,05R | +0,08R | −1,05R | −13,81R | 3 |
| R retournement | 77 | +5,85R | +6,94R | +1,79R | −18,64R | 3 |
| **A+R** | 49 | +16,36R | +17,17R | +12,29R | −7,53R | 1 |
| Aj+R | 70 | +5,28R | +3,18R | +1,21R | −18,07R | 3 |

**Principale, avant le 28/10 (historique, information), frais de 1 point :**

| Version | Trades clos | Net | t par trade | Gains plafonnés à 5R | Pire creux |
|---|---|---|---|---|---|
| Base | 299 | +97,90R | 1,85 | +41,69R | −15,82R |
| A alternance stricte | 132 | +51,47R | 2,03 | +37,97R | −9,12R |
| Aj alternance du jour | 284 | +88,64R | 1,70 | +32,43R | −15,20R |
| R retournement | 340 | +75,90R | 2,11 | +53,50R | −15,75R |
| **A+R** | 138 | +53,52R | 2,27 | +42,34R | −8,71R |
| Aj+R | 316 | +68,37R | 1,95 | +45,96R | −15,12R |

**Version exécutable en turbo (D), frais de 3 points (la mesure de sa règle de passage) :**

| Version | Avant le 28/10 | Pire creux | Depuis le 28/10 | Pire creux |
|---|---|---|---|---|
| Base | 314 trades, −13,83R | −36,68R | 74 trades, +10,90R | −14,44R |
| A alternance stricte | 92 trades, +10,32R | −7,49R | 40 trades, +11,06R | −7,11R |
| Aj alternance du jour | 290 trades, −8,46R | −30,42R | 67 trades, +11,08R | −14,23R |
| R retournement | 316 trades, −10,20R | −35,32R | 74 trades, +10,00R | −13,97R |
| **A+R** | 94 trades, +12,46R | −7,45R | 40 trades, +13,21R | −3,60R |
| Aj+R | 293 trades, −4,86R | −29,59R | 67 trades, +10,18R | −13,61R |

Constats :

- **L'alternance stricte, surtout avec le retournement (A+R), est la seule variante de cet audit qui fait
  au moins aussi bien que la base sur les huit découpages** (principale et D, 1 et 3 points, avant et
  depuis le 28/10), avec deux à trois fois moins de trades et un pire creux à peu près divisé par deux.
- **Elle prend moins de trades, pas plus** : 40 à 49 depuis le 28/10 contre 66. Elle n'attrape donc pas
  davantage de hausses et de baisses ; elle évite de reprendre plusieurs fois le même sens.
- **L'alternance remise à zéro chaque jour (Aj) n'apporte rien** : l'effet vient de la mémoire d'un jour
  sur l'autre. Comme les calls sont interdits sous la moyenne 20 jours, l'alternance stricte revient en
  pratique à ne prendre qu'un put par indice tant qu'aucun call n'est revenu : en tendance baissière,
  l'indice est mis en sommeil.
- **Le retournement seul (R) n'aide pas** : avant le 28/10, les trades retournés ont rendu +27,3R contre
  +49,4R s'ils avaient été laissés courir (37 trades comparables) ; depuis le 28/10 c'est l'inverse
  (+5,1R contre +2,8R sur 14 trades).
- Dans la base, les trades de même sens que le précédent ne sont pas plus mauvais dans l'historique
  (+0,330R en moyenne contre +0,324R) ; ils le sont depuis le 28/10 (−0,115R contre +0,280R, sur 28 et 38
  trades), sans que l'écart soit significatif.

Valeur statistique : le meilleur t est 2,27, sur l'historique déjà exploité ; depuis le 28/10, A+R est à
t = 1,2 sur 45 à 49 trades. Le seuil du registre est 3,22 (79 décisions), et A+R est la meilleure de cinq
variantes essayées ici : rien n'est prouvé.

## 6. Suite : sans la règle « calls interdits sous la moyenne 20 jours »

Question de l'utilisateur : « Et si on enlève la règle des calls interdits sous la moyenne 20 jours ».
Les six versions de la section 5 ont été recalculées avec les calls toujours autorisés (mesure fixée et
poussée avant le calcul, commit `Freeze audit of 14/11 (continued): alternation without the calls trend
filter`). Reproduire : `python3 -W ignore audit/2026-11-14/alternance.py --sans-filtre` (sortie brute :
`out_alternance_sans_filtre.txt`). Contrôle : 40 configurations sur 40 identiques au moteur sans filtre.

Sans le filtre, la base compte 278 calls pour 261 puts (109 calls avec le filtre).

**Alternance stricte avec retournement (A+R), avec et sans le filtre :**

| Version, frais | Avant le 28/10, avec filtre | Avant le 28/10, sans filtre | Depuis le 28/10, avec filtre | Depuis le 28/10, sans filtre |
|---|---|---|---|---|
| Principale, 1 pt | 138 trades, +53,52R | 321 trades, +25,25R | 49 trades, +16,36R | 64 trades, +31,82R |
| Principale, 3 pts | 119 trades, +41,19R | 286 trades, +2,10R | 45 trades, +17,17R | 58 trades, +28,12R |
| Turbo (D), 1 pt | 107 trades, +21,66R | 256 trades, +6,57R | 42 trades, +13,70R | 58 trades, +28,11R |
| Turbo (D), 3 pts | 94 trades, +12,46R | 229 trades, −13,13R | 40 trades, +13,21R | 56 trades, +24,12R |

**Version actuelle (sans alternance), avec et sans le filtre, frais de 1 point :**

| | Avant le 28/10 | Depuis le 28/10 |
|---|---|---|
| Avec filtre | 299 trades, +97,90R (plafonné 5R +41,69R, creux −15,82R) | 66 trades, +7,43R |
| Sans filtre | 455 trades, +61,78R (plafonné 5R −5,51R, creux −26,76R) | 76 trades, +19,83R |

Constats :

- **Depuis le 28/10, tout est meilleur sans le filtre** : les marchés ont monté, et les calls pris sous la
  moyenne 20 jours ont gagné. A+R sans filtre atteint +31,8R sur 64 trades (t = 2,0), avec un pire creux
  de −6,5R.
- **Avant le 28/10, c'est l'inverse, et sur beaucoup plus de trades** : sans le filtre, A+R perd plus de
  la moitié de son résultat à 1 point (+25,3R contre +53,5R), presque tout à 3 points (+2,1R contre
  +41,2R), et la version turbo passe en perte (−13,1R contre +12,5R). Le pire creux fait plus que doubler
  (−19,4R contre −8,7R sur la principale à 1 point).
- **Sur les deux périodes réunies**, la version avec filtre reste devant avec deux fois moins de trades :
  principale à 3 points +58,4R (164 trades) contre +30,2R (344 trades) ; turbo à 3 points +25,7R
  (134 trades) contre +11,0R (285 trades).
- Sans le filtre, A+R n'est plus positive sur les huit découpages : elle ne l'est nettement que depuis le
  28/10.

Lecture : l'avantage récent du « sans filtre » repose sur deux semaines et demie de hausse et une dizaine
de calls de plus dans la version actuelle. Le filtre a été retenu le 27/10 parce que les calls sans
filtre ne gagnaient rien sur cinq mois. Les deux semaines depuis vont dans l'autre sens, mais elles ne
suffisent pas à l'annuler (t entre 1,0 et 2,0, seuil du registre 3,22).

## Conclusion

| Piste | Verdict de l'audit |
|---|---|
| Plusieurs trades du même sens ouverts à la fois | ne ressort pas : gain non distinguable du hasard, creux nettement plus profond |
| Sortie partielle à +1R | lisse mais retire 40 % du gain ; équivaut à réduire la taille |
| Renfort à +1R | gain porté par quelques très gros trades ; ne tient pas avec les gains plafonnés |
| Alternance du jour, retournement seul | ne ressortent pas |
| **Alternance stricte avec retournement (A+R)** | **ressort sur les huit découpages, avec moins de trades et un creux réduit de moitié ; non prouvée (t ≤ 2,27)** |
| A+R sans le filtre des calls | meilleure depuis le 28/10 seulement ; nettement moins bonne sur les cinq mois d'avant ; ne ressort pas |

Empiler des ordres du même sens ne règle rien : cela multiplie le même pari. La règle d'alternance de
l'utilisateur, dans sa version stricte, est en revanche la première variante de la principale qui ne se
dégrade sur aucun découpage. Elle n'est pas validée pour autant : elle mérite seulement d'être figée et
suivie en avant, à côté de la principale, avec un critère écrit d'avance. Cette décision revient à
l'utilisateur (règle 12 : un dimanche). Aucune règle n'est modifiée par cet audit.
