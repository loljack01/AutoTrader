# Candidats pour le test de décembre (décision le dimanche 6/12/2026)

Préparé le 28/11/2026 à la demande de l'utilisateur (« Oui prépare la liste des candidats pour le 6/12 »).
**Aucun calcul n'a été fait** (règle 29) : ce document décrit des idées, pas des résultats. Le 6/12,
l'utilisateur choisit UN test ; la règle complète est alors écrite et figée AVANT tout calcul, avec son
critère. Seuil de Bonferroni du registre après 85 décisions : t ≥ 3,24 (il montera un peu avec la 86e).

Exclus d'office (déjà testés au registre) : cassure du range d'ouverture (23), repli VWAP (24),
comblement d'écart (17), squeeze Bollinger (18), supertrend (25), TSMOM (26-27), NR7 (40), tournant du
mois (42), momentum de fin de séance (39), divergence SMT (33), enchère ratée (32), CHoCH frais (20),
réaction aux niveaux (05/11) et retournement aux bornes (test 12, rejeté le 26/11).
Exclu aussi : toute stratégie où Claude « décide » à partir d'actualités passées (le modèle connaît
déjà la suite : biais d'anticipation impossible à corriger).

## A. Décisions sur des suivis existants (ce ne sont PAS des tests)

| Sujet | État au 27/11 | Décision à prendre |
|---|---|---|
| L'écart continue | 105 trades, +10,46 R (+7,01 R à 3 points), t 1,90 : **CONFIRMÉE** | continuer sans argent, ou fixer une règle de passage en réel (taille, plafond, produit) |
| Simple balayage | verdict officiel ABANDONNÉE au seuil de 100 trades (16/11) ; le script affiche CANDIDATE (170 trades, +56,6 R) | garder le verdict (recommandé : changer un verdict après coup parce que la suite est bonne serait de l'ajustement) ou écrire une nouvelle règle de passage, jugée seulement sur les trades APRÈS la décision |

## B. Candidats au test de décembre (un seul sera retenu)

### B1. Swing « force de la bougie » (IBS) — recommandé
- **Idée** : effet de retour à la moyenne bien documenté sur les indices : quand un indice clôture près
  du bas de sa journée (IBS = (clôture - plus bas) / (plus haut - plus bas) < 0,2) en tendance
  haussière, il a tendance à remonter les jours suivants.
- **Pourquoi lui** : même produit et même logique que le swing en réel (calls, turbos, au-dessus de
  la SMA200), mais un déclencheur différent du RSI(2) ; longue histoire journalière disponible sur les
  10 indices cash (des décennies), 0 appel TradingView en plus.
- **À figer avec toi** : seuil IBS (0,2 ?), filtre SMA200, sortie (clôture au-dessus du plus haut de
  la veille ? 5 jours au plus ?), stop, interaction avec le swing existant (même indice OCCUPÉ ?).
- **Risque** : signaux en partie communs avec le RSI(2) ; à mesurer seulement comme stratégie séparée.

### B2. Tenue de nuit (clôture → ouverture) sur indices
- **Idée** : une part importante de la hausse des indices se fait la nuit (de la clôture à
  l'ouverture suivante), effet décrit dans la littérature académique.
- **Pour toi** : les turbos cotent de 8h à 22h, donc un achat le soir et une revente le matin sont
  exécutables. Données : ouvertures et clôtures journalières des indices cash (longue histoire).
- **À figer** : heure d'achat et de revente (clôture du cash ou 21h45 sur le future ?), filtre de
  tendance, frais réalistes du turbo (écart achat-vente) : c'est le point critique, l'effet par nuit
  est petit.
- **Risque** : gain moyen par nuit faible face aux frais ; risque d'écart d'ouverture.

### B3. Retournement aux bornes, version fidèle à ta lecture
- **Idée** : ta lecture du 26/11, avec TES bornes (SMA20 journalière, plus haut et plus bas de la
  veille, zones touchées au moins 2 fois), au plus 1 trade par jour et par sens.
- **À figer** : la définition exacte d'une borne, la confirmation, le stop, la cible ; tout doit venir
  de toi, avant calcul (le test 12 a été jugé peu fidèle).
- **Risque** : probabilité a priori faible (deux échecs dans la même famille : 05/11 et test 12).

### B4. Cassure puis retest d'une borne (FCE1!, 15m)
- **Idée** : la séquence du 27/11 (cassure de 8152 en grande bougie verte avec volume, retest tenu,
  continuation +36).
- **À figer** : borne connue la veille, critère de cassure (clôture 15m au-delà + volume ?), retest
  (retour à moins de X points sans clôture de l'autre côté), stop, cible.
- **Risque** : idée née d'une seule journée (biais d'après coup) ; historique 15m du FCE1! limité à
  environ 7 mois.

## Recommandation (avis, pas décision)

1. **B1 (IBS)** : le meilleur rapport chances / coût, compatible avec ce qui est déjà en réel, sur
   des décennies de données.
2. B2 si tu préfères une idée sans indicateur, à condition de connaître les frais réels du turbo.
3. B3 et B4 seulement si tu tiens à la lecture des bornes ; probabilité de succès faible.

Quel que soit le choix : aucun argent réel avant un verdict et une décision écrite ; seul le swing
reste en réel.

## Autres points de l'ordre du jour du 6/12

- Propositions 1 à 7 de l'audit de la règle des tableaux après coup.
- Connecteur Interactive Brokers : à autoriser dans les réglages des connecteurs de claude.ai (seulement
  utile avec un compte IBKR, en lecture seule).
- Échéance des contrats à terme le 18/12 : passage au contrat suivant pour la semaine du 14 au 18/12.
- Symbole du FTSE MIB futur : « FIB1! » fonctionne (EUREX:FIB1! et IDEM:FIB1! refusés le 27/11) ; à
  corriger dans la routine du bilan du soir.
