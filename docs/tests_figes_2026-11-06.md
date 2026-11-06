# Tests figés le 06/11/2026 (brainstorming à 6 experts), AVANT tout calcul de résultat

Accord de l'utilisateur le 06/11/2026. Ces règles et critères ne seront plus modifiés.
Chaque test aura son script, dont le docstring reprendra ce texte mot pour mot, commité
avant d'être lancé. Seul calcul fait avant ce document : le comptage descriptif des signaux
P1 et de leur recouvrement avec le RSI(2) sur 2012-2021 (205 signaux, 30 % le même jour,
55 % à 5 jours près), sans aucun résultat en R.

## Budget de tests multiples

- **4 tests au maximum** (tests 1 à 4). Seuil corrigé (Bonferroni 5 % / 4, unilatéral) :
  **t ≥ 2,24 en développement**, puis t ≥ 1,65 sur la période réservée.
- Aucun autre test de règle tant qu'un des 4 n'est pas jugé.
- Développement : 2012-01-01 → 2021-12-31. Période réservée : 2022-01-01 → dernier jour.
  La période réservée n'est lancée qu'une fois le développement jugé, et une seule fois.
- Statistiques regroupées par semaine (trades de tous les indices sortis la même semaine
  additionnés), comme `test_swing_rsi2_1990.py`.
- Swing de référence : `test_swing_rsi2.py` + limite de 5 positions
  (`test_swing_rsi2_cap5.py`), 10 indices cash, coût 0,05 % (base) et 0,10 % (stress).

## Test 0 (hors budget) : condition « exécutable turbo » de la principale

Figé dans `scripts/frozen_15m_variants.py` (variante D) et `scripts/frozen_15m_calls_trend.py`.
Entrées 8h00-21h30 Paris, sortie au plus tard à la clôture de la bougie 21h30-21h45,
coût 3 pts. La principale ne passe en réel que si D passe aussi la règle séquentielle
(+72R plafonnés à 5R aux contrôles de 100 en 100 ; abandon à ≤ 0 dès 200 trades, à −15R
à tout moment ou à 600 trades), à partir du 06/11.

## Test 1 : limite par zone sur le swing (R3)

- Règle : au plus 5 positions, dont au plus **2 en zone euro** (CAC 40, DAX, Euro Stoxx 50,
  FTSE MIB), **2 aux États-Unis** (S&P 500, Nasdaq 100, Dow Jones, Russell 2000) et
  **1 autre** (FTSE 100, SMI). Sorties d'abord, puis signaux d'une même clôture par RSI(2)
  croissant ; un signal qui trouve sa zone ou le carnet plein est ignoré. Règle de trade
  inchangée.
- Mesures, comparées au swing de référence limité à 5 positions : pire baisse en R (cumul
  dans l'ordre des sorties), pire période de 3 mois en R, R par an, à 0,05 %.
- **Adopté** seulement si, sur le développement PUIS sur la période réservée : pire baisse
  réduite d'au moins 20 % ET R par an ≥ 90 % de la référence. Sinon, non adopté.

## Test 2 : faux cassage du plus bas 20 jours (P1, expert graphique)

- Signal le jour J (indice cash, journalier) : L20 = plus bas des 20 séances J-20 à J-1,
  posé au moins 4 séances avant J (son jour ≤ J-4) ; Bas(J) < L20 ; Clôture(J) > L20 ;
  Clôture(J-1) > SMA200(J-1).
- Entrée à la clôture de J. Stop = Bas(J) − 0,25 × ATR14(J) (ATR EWM, comme le swing).
  Sortie à la première clôture > SMA5 après J, ou à la clôture de la 10e séance ; une
  ouverture au-delà du stop sort à l'ouverture. Une position par indice.
- Portefeuille : P1 partage les 5 places du swing RSI(2) ; signaux d'une même clôture par
  RSI(2) croissant ; si un indice a les deux signaux le même jour, un seul trade (règle
  RSI(2)).
- **Rejet immédiat** si plus de 50 % des signaux P1 tombent le même jour qu'un signal
  RSI(2) sur le même indice.
- **Développement** : au moins 100 trades P1 seuls ; net > 0 à 0,10 % ; t hebdomadaire
  ≥ 2,24 à 0,05 % ; au moins 7 indices sur 10 positifs à 0,05 % ; portefeuille combiné
  (RSI(2) + P1, 5 places) ≥ RSI(2) seul + 1R par an.
- **Période réservée** : net > 0 à 0,05 %, t hebdomadaire ≥ 1,65, combiné ≥ RSI(2) seul
  + 1R par an. Puis contrôle sur 1991-2011 (mêmes fichiers que `test_swing_rsi2_1990.py`) :
  t ≥ 1,65. Adopté seulement si les trois passent.

## Test 3 : demi-taille quand le VIX est haut (R2)

- Données : TVC:VIX journalier.
- Règle évaluée : demi-taille sur un trade swing si la clôture du VIX de la veille de
  l'entrée (J-1) est > 30.
- **Adopté** seulement si les trades du swing de référence (limite 5) entrés avec
  VIX(J-1) > 30 sont au moins 50 et ont un **net R ≤ 0 à 0,05 %**, sur le développement
  ET sur la période réservée. Sinon, taille normale quel que soit le VIX.

## Test 4 : rejet du plus haut / plus bas de la veille (P2), suivi en avant seulement

- Marchés : FCE1!, FDAX1!, FESX1! en 15m (facteurs k : 1 ; 3,2397 ; 0,8004).
- PDH / PDL : plus haut / plus bas des bougies 15m de 9h00 à 17h30 Paris de la séance
  précédente. ATRj = ATR14 journalier du future.
- **Put** : bougie 15m débutant entre 9h15 et 15h15 Paris avec Haut > PDH,
  Clôture < PDH et Haut − PDH ≤ 0,3 × ATRj. Entrée à la clôture de la bougie. Stop = Haut
  de la bougie + 0,1 × ATRj. Cible = (PDH + PDL) / 2. Trade seulement si le R:R net
  (coût 3 pts × k) est ≥ 1,3. Sortie à la cible, au stop (le stop d'abord si les deux dans
  la même bougie) ou à la clôture de la bougie 17h15-17h30.
- **Call** : miroir sur le PDL, seulement si la clôture journalière de la veille est
  au-dessus de la SMA20.
- Au plus 1 trade par côté et par jour et par marché (le premier signal).
- Suivi en avant à partir du **lundi 09/11/2026**, sans argent. Aucun calcul sur les
  données 15m antérieures.
- **Verdict à 150 trades clos** : net R > 0 à 3 pts ET t (par jour) ≥ 2,24 → candidat ;
  sinon la famille des réactions aux niveaux est fermée. **Abandon** dès −15R cumulés.

## Résultats (06/11/2026, développement 2012-2021, période réservée non utilisée)

- **Test 1 : NON ADOPTÉ.** Référence 757 trades, +5,62R/an, pire baisse −31,3R, pire
  3 mois −13,0R ; limite par zone 637 trades, +4,41R/an, −24,9R, −9,3R. Baisse réduite de
  20 % mais 78 % du R par an (seuil 90 %).
- **Test 2 (P1) : REJETÉ.** 30 % de signaux communs avec le RSI(2) ; P1 seul 205 trades,
  +0,169R/trade, +34,6R à 0,05 %, +23,5R à 0,10 %, mais t hebdomadaire 1,66 (seuil 2,24)
  et 6 indices positifs sur 10 (seuil 7). Combiné +1,47R/an (seuil +1). Pas de réglage.
- **Test 3 (VIX) : NON ADOPTÉ.** 10 trades seulement avec VIX > 30 (seuil 50), et
  positifs (+4,8R).
- Budget : 3 tests sur 4 utilisés. Reste le test 4 (P2, suivi en avant dès le 09/11).
  La période réservée 2022-2026 reste intacte.
