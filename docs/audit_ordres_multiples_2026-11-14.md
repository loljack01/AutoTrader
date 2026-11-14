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

## Conclusion

Prendre plusieurs ordres sur le même indice ne règle pas le problème de l'intraday. Ce qui manque à la
principale est un avantage par trade, pas un nombre d'ordres : multiplier les ordres multiplie le même
pari, avec des trades ajoutés moins bons que les autres et un risque qui grossit plus vite que le gain.

| Piste | Verdict de l'audit |
|---|---|
| Plusieurs trades ouverts à la fois (principale) | ne ressort pas : gain non distinguable du hasard, creux nettement plus profond |
| Plusieurs trades ouverts à la fois (version turbo D) | sans objet : aucun cas depuis le 28/10 |
| Sortie partielle à +1R | lisse mais retire 40 % du gain ; équivaut à réduire la taille |
| Renfort à +1R | gain porté par quelques très gros trades ; ne tient pas avec les gains plafonnés |

Aucune de ces pistes ne mérite d'être figée pour un suivi en avant sur la foi de ces chiffres. La décision
reste à l'utilisateur.
