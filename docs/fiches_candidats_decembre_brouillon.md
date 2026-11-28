# Fiches B1 à B4 : BROUILLON à valider (aucun calcul, règle 29)

Rédigé le 28/11/2026 après « On continue b1 b2 b3 et b4 ». Ce sont des PROPOSITIONS : chaque valeur
marquée (?) est à trancher par l'utilisateur. Rien n'est calculé. Règle 29 : un seul test par mois,
décidé un dimanche ; le 6/12, une fiche est choisie, complétée, figée par un commit, puis calculée. Les
autres attendent les mois suivants, sauf levée explicite et écrite de la limite pour un test donné.

Critère commun proposé (même modèle que le test 12) : moins de 30 trades = non concluant ; total > 0
et t ≥ seuil de Bonferroni du registre (≈ 3,25 à la 86e décision) = retenue pour un suivi en avant sans
argent ; total > 0 et 2 ≤ t < seuil = prometteuse, décision de l'utilisateur un dimanche ; sinon
rejetée. Aucun argent réel quel que soit le verdict.

## B1. Swing « force de la bougie » (IBS), calls

| Élément | Proposition |
|---|---|
| Marchés, données | les 10 indices cash du swing, barres journalières en cache (toute l'histoire disponible) |
| Signal | clôture > SMA200 ET IBS = (clôture - plus bas) / (plus haut - plus bas) < 0,2 (?) |
| Entrée | à la clôture du jour du signal (comme le swing, règle 28) |
| Sortie | 1re clôture au-dessus du plus haut de la veille (?) ou 5e jour (?) |
| Stop | le même stop que le swing RSI(2) (?) |
| Frais | 0,05 % et 0,10 % par aller-retour (comme le swing) |
| Positions | 1 par indice, 5 au plus ; comptée à part du swing existant (le chevauchement est montré pour information) |
| Questions | seuil 0,2 ou 0,25 ? sortie ? stop ? exclure les jours où le RSI(2) donne déjà un signal ? |

## B2. Tenue de nuit (clôture → ouverture)

| Élément | Proposition |
|---|---|
| Marchés, données | les 10 indices cash, barres journalières (ouverture et clôture) |
| Signal | chaque soir où la clôture est au-dessus de la SMA200 (?) |
| Entrée / sortie | achat à la clôture, vente à l'ouverture suivante |
| Frais | **écart achat-vente réel des turbos utilisés** (à donner par l'utilisateur) ; par défaut 0,05 % et 0,10 % |
| Questions | filtre SMA200 ou aucun ? tous les soirs ou seulement certains jours ? frais réels du turbo ? |
| Point critique | le gain moyen par nuit est petit ; le verdict dépend surtout des frais |

## B3. Retournement aux bornes, version de l'utilisateur (FCE1!, 15m)

| Élément | Proposition (à remplacer par la définition de l'utilisateur) |
|---|---|
| Bornes connues à 8h | SMA20 journalière, plus haut et plus bas de la veille, zones touchées au moins 2 fois dans les 3 séances précédentes (à 3 points près) (?) |
| Signal | passage au-delà d'une borne puis clôture 15m revenue de l'autre côté (?) |
| Limite | 1 trade par jour et par sens (?) |
| Stop, cible | 2 points derrière l'extrême ; cible à la borne suivante (?) |
| Heures | clôtures de 8h15 à 21h30, sortie au plus tard à 22h00 ; 3 points de frais |
| Questions | quelles bornes exactement ? quelle confirmation ? quelle cible ? |
| Note | famille déjà en échec deux fois (05/11, test 12) |

## B4. Cassure puis retest d'une borne (FCE1!, 15m)

| Élément | Proposition |
|---|---|
| Bornes connues à 8h | plus haut et plus bas de la veille, SMA20 journalière, zones touchées au moins 3 fois (?) |
| Cassure | clôture 15m au-delà de la borne d'au moins 3 points (?) avec un volume > 1,5 fois la moyenne des 20 bougies précédentes (?) |
| Retest | dans les 16 bougies suivantes, retour à moins de 3 points de la borne sans clôture de l'autre côté (?) |
| Entrée | à la clôture de la bougie du retest si elle clôture dans le sens de la cassure |
| Stop, cible | 2 points de l'autre côté de la borne (?) ; cible 1,5 R ou borne suivante (?) ; sortie au plus tard à 22h00 |
| Heures, frais | clôtures de 8h15 à 21h30 ; 3 points de frais |
| Note | idée venue d'une seule journée (27/11) ; historique 15m d'environ 7 mois |
