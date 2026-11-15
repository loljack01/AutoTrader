# Audit critique de l'intraday (15/11/2026)

Demande de l'utilisateur du 15/11/2026 : « Refais audit et sois critique sur l'intraday ». **Aucune règle
nouvelle n'est testée** (règle 29 : un nouveau test par mois) : l'audit relit les trades des stratégies
intraday déjà figées, avec leurs propres fonctions, et les découpe. Il n'ajoute donc rien au registre.

Reproduire : `python3 -W ignore audit/2026-11-15/critique_intraday.py` (sortie brute :
`audit/2026-11-15/out_critique_intraday.txt`). Données 15 minutes jusqu'au 13/11/2026 à 22h15 ;
historique depuis le 22/05/2026 (CAC) à début août selon le marché.

## Verdict

**Aucune stratégie intraday du dépôt n'a d'avantage démontré, et la principale n'est pas une stratégie
intraday.** Son gain historique vient de quelques puts gardés plusieurs jours pendant deux mois ; limitée à
la séance et aux heures des turbos, il n'en reste presque rien.

## 1. Tableau de bord : tout ce qui est suivi

| Stratégie | Suivi depuis | Trades | Net à 1 pt | Net à 3 pts | t (1 pt) | Pire creux |
|---|---|---|---|---|---|---|
| Principale | 28/10 | 66 | +7,43R | +4,34R | 0,45 | −12,8R |
| D, forme exécutable en turbo | 06/11 | 34 | −9,75R | −14,44R | −1,72 | −10,4R |
| Simple balayage | 30/10 | 87 | +5,50R | −0,56R | 0,29 | −14,5R |
| L'écart continue | 28/10 | 64 | +5,06R | +2,85R | 1,15 | −3,0R |
| Pétrole | 30/10 | 11 | −0,65R | −0,90R | −0,09 | −5,1R |
| P2 | 09/11 | 2 | +0,75R | +0,56R | — | — |

Aucun score ne se distingue du hasard. « L'écart continue » est la seule à avoir un profil régulier (53 %
de gagnants, pire creux de −3R), sur un échantillon encore trop petit.

## 2. La principale : ce que disent les chiffres de base

| | Avant le 28/10 | Depuis le 28/10 |
|---|---|---|
| Trades clos (1 pt) | 299 | 66 |
| Net à 1 pt / à 3 pts | +97,90R / +76,27R | +7,43R / +4,34R |
| t par trade (1 pt / 3 pts) | 1,85 / 1,46 | 0,45 / 0,26 |
| Gagnants | 34 % | 29 % |
| Gain moyen / perte moyenne | +2,94R / −1,05R | +2,95R / −1,03R |
| Réussite nécessaire pour être à l'équilibre | 26 % | 26 % |
| Moyenne par trade, intervalle à 95 % (1 pt) | +0,02R à +0,72R | −0,35R à +0,64R |
| Probabilité que la vraie moyenne soit nulle ou négative (1 pt / 3 pts) | 2 % / 6 % | 33 % / 42 % |

Depuis le 28/10, il y a une chance sur trois que la principale ne gagne rien, et presque une sur deux avec
3 points de frais.

## 3. D'où vient le gain historique

| Découpage (avant le 28/10, 1 pt) | Trades | Net | t |
|---|---|---|---|
| Total | 299 | +97,9R | 1,85 |
| Les 5 meilleurs trades | 5 | +78,9R | |
| Tout le reste sans les 10 meilleurs | 289 | −8,3R | |
| Calls | 82 | +0,3R | 0,02 |
| Puts | 217 | +97,6R | 1,92 |
| Entrées 8h-21h30 (heures des turbos) | 250 | +38,0R | 1,31 |
| Entrées 21h30-8h (turbos fermés) | 49 | +59,9R | 1,36 |
| Sortis le jour même | 160 | −42,9R | −2,54 |
| Gardés au moins une nuit | 139 | +140,8R | 2,88 |

| Mois de sortie | 05 | 06 | 07 | 08 | 09 | 10 | 11 |
|---|---|---|---|---|---|---|---|
| Net à 1 pt | +3,8R | −1,6R | +4,1R | +0,1R | +37,8R | +52,5R | +8,6R |

- **Dix trades font plus que tout le gain.** Sans eux, 289 trades perdent 8,3R. Depuis le 28/10 c'est pire :
  sans les 5 meilleurs trades, les 61 autres perdent 19,6R.
- **Les calls n'ont rien rapporté** (+0,3R en 82 trades) ; tout vient des puts.
- **Deux mois font 90 % du gain** : septembre et octobre 2026. De mai à août, quatre mois donnent +6,4R.
- **Les trades clos dans la journée perdent** (−42,9R sur 160 trades). Ce découpage est fait après coup (un
  trade gardé la nuit est un trade qui n'a pas été stoppé le jour même), il ne prouve donc pas à lui seul
  qu'il faut garder la nuit. Mais les deux versions honnêtes de la question, figées à l'avance, disent la
  même chose : la variante A (sortie forcée le jour même) ne garde que +39,9R sur les +112,1R de
  l'historique d'avant le 06/11, et la variante D (heures des turbos et sortie le soir) n'en garde que
  +6,5R à 1 point et passe à −13,8R à 3 points.
- **Deux marchés sur dix perdent nettement** : SMI −17,3R, Dow Jones −8,1R.

## 4. Elle ne fait pas ce qu'on attend d'un intraday

| Indice | Jours avec au moins un trade | Un trade tous les |
|---|---|---|
| CAC 40 | 29 % | 3,2 jours |
| DAX | 28 % | 2,8 jours |
| Nasdaq 100 | 25 % | 3,5 jours |
| S&P 500 | 51 % | 1,5 jour |
| FTSE MIB | 23 % | 3,9 jours |

- Sur le CAC, sept séances sur dix n'ont aucun signal. Elle ne peut pas « attraper les hausses et les
  baisses de la journée ».
- Un trade sur quatre dure plus de 24 heures dans l'historique.

## 5. En euros, et la règle de passage

| Ordres de 500 EUR, levier 2,8 (1R ≈ 4,7 EUR) | Ordres passés | Résultat à 1 pt | Résultat à 3 pts |
|---|---|---|---|
| Principale, avant le 28/10 | 299 (150 000 EUR d'ordres) | +460 EUR | +358 EUR |
| Forme turbo D, avant le 28/10 | 346 (173 000 EUR d'ordres) | +31 EUR | −65 EUR |
| Principale, depuis le 28/10 | 66 (33 000 EUR d'ordres) | +35 EUR | +20 EUR |

**Correction (même jour)** : le tableau ci-dessus multiplie le total en R par la valeur médiane d'un R. Avec des
ordres de montant fixe, un R ne vaut pas la même chose d'un trade à l'autre (il dépend de la distance du
stop). Calculé trade par trade (500 EUR × 2,8 × mouvement), la principale fait **+375 EUR** avant le 28/10
(et non +460 EUR) et **+51 EUR** depuis (et non +35 EUR), à 1 pt.

- Même en prenant l'historique pour argent comptant, la principale aurait rapporté 460 EUR en cinq mois
  pour 299 ordres, et sa forme exécutable 31 EUR.
- **La règle de passage est hors d'atteinte** : elle demande +72R plafonnés à un contrôle, soit au moins
  0,12R plafonné par trade sur 600 trades. La principale a fait 0,139R dans l'historique (qui a servi à la
  construire) et 0,051R depuis le 28/10. La forme turbo, qui est la condition du passage, a fait −0,048R à
  3 points dans l'historique.

## 6. Critique de la méthode

- **L'historique est court et déjà usé** : cinq mois, dont deux font tout le gain, et 84 décisions au
  registre prises sur ces mêmes données.
- **Les réglages n'ont jamais été justifiés** : fenêtre de 4 h, marge de 8 points, stop à 2 ATR, rapport
  minimum de 1,3, niveau d'une poche fixé sur son premier pivot.
- **Trois tests (9, 10, 11) viennent d'être ajoutés sur une base** dont la forme exécutable est à 0,6R de
  son abandon.
- **L'essentiel du temps de suivi va à l'intraday**, alors que la seule stratégie en argent réel est le
  swing.

## 7. Les défauts relevés, du plus grave au moins grave

Vérifiés dans le code, les sorties d'audit et l'historique Git (15/11/2026). Aucune règle n'a été testée.

| # | Défaut | Constat vérifié |
|---|---|---|
| 1 | Pas d'avantage mesurable | t = 0,45 depuis le 28/10 ; une chance sur trois que la vraie moyenne soit nulle ou négative (deux sur cinq à 3 pts) |
| 2 | Le résultat en R trompe pour des ordres à montant fixe | +97,9R avant le 28/10 ne valent que +375 EUR ; les 10 meilleurs trades font +320 EUR, les 289 autres environ +55 EUR. Le plus gros (+39R, put FTSE 100, stop à 0,1 % du cours, gardé 43 jours) vaut 64 EUR |
| 3 | Le moteur trade la nuit | le filtre horaire ne bloque que 9h00-9h15 et le quart d'heure suivant l'ouverture américaine ; il laisse passer 22h-8h, 8h-9h (« peu fiable ») et après 17h30 (« dégradé »). 49 trades de nuit avant le 28/10, quand les turbos ne cotent pas ; stops de nuit plus serrés (0,24 % contre 0,34 %), qui gonflent les R |
| 4 | Les annonces économiques ne sont pas filtrées | la règle « rien dans les 15 minutes autour d'une annonce » n'existe que pour l'exécution humaine : le moteur ne reçoit jamais le calendrier (`major_events` n'est passé nulle part). Le suivi compte des trades que la règle d'exécution interdit |
| 5 | Pas de sortie dans le temps | un trade attend sa cible, parfois une poche lointaine : jusqu'à 43 jours, un sur quatre plus de 24 h. Ce n'est pas de l'intraday |
| 6 | La plupart des « balayages » portent sur des niveaux déjà cassés | 62 % des balayages (210 sur 339) visent une poche que le prix avait déjà franchie en clôture avant (audit du 06/11) : ce n'est pas la liquidité intacte que décrit la théorie |
| 7 | Une moitié de la stratégie n'a jamais rien rapporté | calls : +0,3R en 82 trades avant le 28/10 ; le filtre des calls a été choisi sur cette même période |
| 8 | Positions contradictoires | un call et un put ouverts en même temps sur le même indice 60 fois : on paie des frais pour être couvert |
| 9 | Réglages jamais justifiés | fenêtre de 4 h, marge de 8 points, stop à 2 ATR, rapport minimum de 1,3, pivots à 2 bougies ; des signaux se jouent au demi-point (13/11) |
| 10 | Les frais décident de tout | la forme exécutable est à +6,5R à 1 pt et −13,8R à 3 pts sur l'historique ; le coût réel d'un aller-retour en turbo n'a pas été mesuré pour l'intraday |
| 11 | Données courtes et partiellement fausses | 15 minutes disponibles depuis mai-août 2026 seulement (limite du fournisseur, impossible à allonger) ; ouvertures du FTSE 100 fausses dans 89 % des séances (concerne « l'écart continue ») ; 8 à 35 % de minutes manquantes en 1 minute (concerne le filtre delta) |
| 12 | Processus | 84 décisions au registre sur les mêmes cinq mois ; tests 9 à 11 ajoutés sur une base dont la forme exécutable est à 0,6R de l'abandon |

**Ce qui tient** : le suivi n'est pas réécrit après coup (21 versions du fichier de suivi comparées depuis le
28/10 : aucun trade clos disparu ni modifié), et les contrôles de reproduction sont tous identiques.

Les défauts 3 et 4 se corrigeraient dans le moteur, mais ce serait une règle nouvelle, donc le test d'un
mois (règle 29), et sur une famille qui s'arrête si D est abandonnée (règle 30).

## Ce que j'en conclus

1. Ne plus rien construire sur la principale. Laisser la règle 30 s'appliquer quand D touche −15R.
2. Garder jusqu'à leur verdict les trois suivis qui ne dépendent pas d'elle : « l'écart continue », P2 et
   le simple balayage. Ils ne demandent aucun travail.
3. Si un intraday doit être cherché, que ce soit le test de décembre, sur une idée d'une autre nature et
   jugée sur des données jamais utilisées (les indices cash en bougies d'une heure depuis janvier 2024).
4. Ne pas confondre : ce que cet audit montre de mieux dans ces signaux se passe sur plusieurs jours, pas
   dans la séance. C'est une observation après coup, à ne pas transformer en règle sans test.
