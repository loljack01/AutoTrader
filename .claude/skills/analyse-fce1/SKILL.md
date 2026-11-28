---
name: analyse-fce1
description: Analyse intraday du FCE1 (contrat à terme CAC 40) et tableau des puts et calls après coup, selon la règle 37 de docs/regles_execution.md. À utiliser quand l'utilisateur envoie une capture du FCE1, demande « analyse le FCE1 », « fais le tableau des puts et calls », « mets à jour le fce1 jusqu'à 22h », « refais le tableau avec indicateurs, bougies, support résistance, SMC », ou « enregistre les supports et résistances ». Lecture après coup : jamais un signal, jamais un ordre.
---

# Analyse intraday du FCE1 (règle 37)

Référence : règle 37 de `docs/regles_execution.md` et le modèle `docs/analyse_fce1_2026-11-27.md`.
Tout se fait en français, avec des niveaux FCE1 ET leur équivalent CAC 40 cash.

## 0. Garde-fous (avant tout)

- C'est une **lecture après coup** : pas un signal, pas un ordre, pas un test (règle 29). Ne jamais
  calculer une règle nouvelle sur l'historique : ce serait un test (un par mois, décidé un dimanche).
- Seul le **swing** est joué en argent réel. Aucun ordre sur capture ni hors alerte.
- **Budget TradingView** (règle 34, environ 50 appels par jour) : l'analyse coûte 1 appel, 2 au plus.
  Après 21h, réutiliser les barres 15m du bilan de 22h15 (0 appel). Ne jamais créer, modifier ou
  supprimer d'alerte TradingView.
- Demande ambiguë (période, entrées autorisées, ce qu'il faut enregistrer) : poser la question avant
  de calculer.
- Séance du FCE1 : **8h00-22h00** (règle 35) ; 8h00-9h00 et 17h35-22h00 sont « peu échangé ».

## 1. Données exactes (jamais la capture seule)

1. `git pull origin claude/trading-environment-4w4s95`.
2. Un appel `mcp__Trading_view_premium__mcp-tv-get-ohlcv` : symbol `EURONEXT:FCE1!`, interval `1m`,
   count `2000`, format `columns` (le résultat dépasse la limite et est enregistré dans un fichier
   tool-results ; le lire avec Python, ne jamais charger les barres dans la conversation).
   Si le résultat revient dans la conversation, le réécrire tel quel dans un fichier JSON du scratchpad.
3. La capture sert seulement à vérifier : ses valeurs (dernier cours, lignes, « Bas ») doivent
   correspondre aux données. Signaler tout écart.

## 2. Double contrôle (obligatoire avant de donner un chiffre)

```
python3 -W ignore scripts/lecture_fce1_jour.py <fichier 1m> --date AAAA-MM-JJ
```

Le script sort : ouverture, plus haut et plus bas avec l'heure, bougies 15m avec RSI(14), moyenne
exponentielle 20, moyenne 50, prix moyen pondéré depuis 8h, volume rapporté aux 20 bougies
précédentes, motif de bougie, sommets et creux (zigzag 12 points et 15m), trous de cotation 15m et 5m,
gros volumes, et la ligne **DOUBLE CONTRÔLE : CONCORDE**. Si elle affiche DIFFÉRENT, chercher la cause
avant de répondre. Pour la soirée, comparer aussi les bougies 15m du bilan aux bougies recalculées
depuis le 1m (écart attendu : 0).

## 3. Ordre de la réponse

1. **La journée réelle** : règlement de la veille, ouverture, plus haut et plus bas (heures), dernier
   cours ; tableau des grands mouvements (heure, de → à, points, ce qui s'est passé). Ne donner une
   cause (annonce, actualité) que si elle est vérifiée ; sinon écrire « cause non vérifiée ».
2. **Figures et structure** : bornes testées (combien de fois, quand), double sommet ou creux, triangle
   et son objectif (constat après coup), balayages de liquidité, cassures et changements de
   structure, trous de cotation, dernière bougie opposée avant l'impulsion, volumes.
3. **Le tableau** (format ci-dessous).
4. **Bilan** : trades clos brut et net, trades ouverts, ce qui a marché, ce qui a échoué, limites.
5. **Stratégies réelles** en une ligne : swing (seul argent réel), principale sans argent (le bilan de
   22h15 fait foi).

## 4. Méthode du tableau

- Niveaux : ceux connus la veille dans `data/niveaux_cles.csv` (date_seance du jour) ; ne jamais
  utiliser un niveau découvert pendant la séance pour une entrée.
- Entrée : à la **clôture d'une bougie 15m** après un retournement ou une cassure sur une borne.
  Entrées dès la clôture de 8h15, y compris 8h45, 9h00 et autour des annonces du matin, mais
  **signalées** (« 9h00 », « annonce ») ; signaler aussi 15h30-15h45, 17h30-17h35 et les annonces
  après 9h15 (règles 31 et 35).
- Stop : 2 points derrière l'extrême du retournement (ou sous la borne cassée).
- Sortie : à la **première zone touchée** ; depuis l'intérieur d'une zone, à son bord opposé ; au plus
  tard à 22h00. Pas de trade si la cible est à 3 points ou moins. 3 points de frais. Une position à
  la fois (un « renfort » est signalé, pas compté).
- **Passer en revue TOUS les creux et sommets qui touchent une borne** (creux ou sommets égaux, creux
  montants, faux passages) avant de rendre le tableau. Lire la clôture de CHAQUE bougie 15m.
- Format : lignes **ACHAT** et **VENTE** séparées, colonnes **CALL** et **PUT** côte à côte :

| Heure | Ordre | CALL | PUT | Niveau FCE1 (≈ cash) | Bougie 15m | Indicateurs | Support / résistance, figure | Lecture smart money | Résultat |
|---|---|---|---|---|---|---|---|---|---|

  Ajouter les occasions ignorées ou non détectées avec la raison (cible trop proche, aucun niveau,
  heure exclue) et ce que le marché a fait ensuite.
- Équivalent cash : écart FCE1 - cash mesuré le jour même (FCE1 à 17h35 contre la clôture du CAC
  cash) ; sinon l'écart du dernier jour connu, en le disant.

## 5. Enregistrement

- **Seulement les 3 à 5 supports, résistances et pivots les plus importants** pour la séance suivante,
  dans `data/niveaux_cles.csv` (colonnes : date_seance, symbole, horizon, niveau, role, importance,
  raison, fixe_le ; fins de ligne `\n` ; écrire avec `csv.writer(..., lineterminator="\n")`).
- Chaque niveau porte sa **zone de stops probable** (déduite, pas observée) : juste au-delà des plus
  hauts et plus bas, sommets ou creux égaux, chiffres ronds et bornes cassées ; « pas de zone de stops »
  pour un pivot en milieu de range. Ces zones servent à ne pas y placer son propre stop, pas à entrer.
- Compléter ou créer `docs/analyse_fce1_AAAA-MM-JJ.md` sur le modèle du 27/11 (journée, figures,
  tableau, erreurs corrigées, constat).
- Commit et push sur `claude/trading-environment-4w4s95` avec le pied de commit habituel.

## 6. Erreurs déjà commises (ne pas refaire)

- Annoncer une entrée « possible seulement à 9h00 » alors que la bougie précédente clôturait déjà
  au-delà de la borne.
- Oublier un call sur deux creux égaux (13h50 le 27/11).
- Calculer un rapport de volume en incluant la bougie elle-même dans la moyenne.
- Conclure avant que les données soient complètes ; donner des chiffres tirés d'une capture.
- Présenter d'abord la règle au lieu de la journée réelle (« ton analyse ne reflète pas la journée »).
