# Audit du groupe : semaine du 16 au 20/11/2026

Demande de l'utilisateur (samedi 21/11) : « Réunis le groupe et faites un audit sur cette semaine ».
Ce document ne change aucune règle et ne calcule aucune règle ni variante nouvelle (règle 29) : il relit
les trades existants, les journaux et l'historique du dépôt, puis propose. Les décisions reviennent à
l'utilisateur, par écrit dans `docs/regles_execution.md`, un dimanche.

Participants : statisticien, gestionnaire du risque, responsable de l'exécution et des données,
développeur des outils, trader indices, coach de discipline, responsable de la méthode.

Sources : `data/backtests/frozen_*_trades.csv`, `data/journal_swing.csv`, sorties des scripts du bilan
du 20/11, `git log` du 16/11 au 21/11 (101 commits), conversation de la semaine.

## Verdict

| Bloc | État | Fait vérifié |
|---|---|---|
| Argent réel | **tient** (0 EUR) | aucun trade réel ; limite de −500 EUR intacte |
| Exécution du swing en réel | **défaillant** | 0 signal exécuté sur 5 (journal vide) ; signaux du 16 et du 17/11 manqués (règles 32 et 33) |
| Risque du swing (positions corrélées) | **défaillant** | les 5 positions du modèle ont touché leur stop le même jour (20/11) : −5,07R, soit environ −228 EUR, 46 % de la limite totale de −500 EUR en une séance, si elles avaient été prises |
| Quota TradingView | **défaillant** | quota épuisé 3 fois (17/11 vers 16h, 18/11 à 07h39, 20/11 à 22h20) ; routines du 17/11 (17h55, 21h42, 22h15) en échec ; bilan du 20/11 incomplet |
| Suivi des tests figés 9, 10 et 11 | **défaillant** | non lancés par le bilan du soir : test 9 dernier trade le 13/11, test 10 un seul trade (13/11), test 11 aucun trade depuis son départ le 15/11 |
| Données de volume | corrigé en cours de semaine | semaine d'échéance : lectures du 18 et du 19/11 faites sur le contrat sortant (volume faux) ; outil corrigé le 20/11 (`scripts/volume_normal.py`) |
| Principale et variantes (sans argent) | tient | semaine : 14 trades clos, +10,3R (puts +12,4R, calls −2,1R) ; D +14,6R sur 15 trades ; cumul principal +27,8R ; règle séquentielle en cours |
| Discipline de l'utilisateur | **tient, sous pression** | aucun ordre hors système ; mais 3 demandes de calls et puts « à faire », une dizaine de lectures en direct, un « on rate la hausse » |
| Stabilité des règles | fragile | 5 ajouts aux règles d'exécution en 5 jours (31 à 34 et un complément de 31) ; aucune règle de stratégie modifiée |

## 1. Le swing n'est pas exécuté (responsable de l'exécution, coach de discipline)

- Positions du modèle cette semaine : S&P 500 (16/11), Euro Stoxx 50, FTSE MIB, DAX et CAC 40 (17/11).
  Aucune n'a été prise en réel : le 16/11 l'utilisateur n'a rien acheté, le 17/11 les signaux sont
  arrivés trop tard (quota épuisé pendant les lectures en direct). Règles 32 et 33 décidées le 19/11.
- Depuis le passage en réel (05/11), le journal est vide : **la phase réelle n'a encore produit aucune
  mesure d'exécution** (contrôle des 30 trades : 0 sur 30).
- Effet de la semaine : les 5 trades du modèle ont fini au stop le 20/11. Ne pas les avoir pris a évité
  environ −228 EUR. C'est de la chance, pas une méthode : la semaine précédente, les mêmes manques
  auraient pu coûter des gains.

## 2. Positions corrélées : 5 positions = un seul pari (gestionnaire du risque, statisticien)

- Les 5 positions étaient des calls sur des indices qui baissent ensemble (Europe et États-Unis). Le
  marché a corrigé fortement : du 13 au 20/11, CAC 40 −5,3 %, DAX −7,3 %, Euro Stoxx 50 −7,0 %,
  S&P 500 −8,6 %, Nasdaq 100 −10,4 %, VIX à 31,5.
- Avec 1R ≈ 45 EUR par position et 5 positions au plus, une seule séance de baisse peut coûter
  5R ≈ 225 EUR, soit **près de la moitié de la limite totale de −500 EUR**.
- Le filtre de tendance fait maintenant son travail : 9 indices sur 10 sont sous leur SMA200, le swing
  ne prendra presque plus de position.
- À mesurer (relecture des trades existants du carnet de référence, pas un test) : pire séance et pire
  semaine du modèle avec ses positions simultanées. Toute limite de positions corrélées serait une
  variante, donc un test au sens de la règle 29.

## 3. Quota TradingView (développeur des outils, responsable des données)

- Environ 50 appels par jour. Les routines en demandent environ 40 (plan 4, contrôles 2 à 4, bilan 34).
- Ce qui a fait déborder : les lectures en direct minute par minute (17, 18 et 20/11), les analyses à
  la demande (FCE1, Anthropic) et les tableaux de calls et puts.
- Conséquences : le 17/11 les contrôles du swing ont échoué, d'où les signaux manqués ; le 20/11 le
  bilan n'a pas pu mettre à jour FTSE 100, Dow, Russell, FTSE MIB ni le pétrole.
- La règle 34 (19/11) n'a pas suffi le 20/11 : les lectures en direct et les analyses de la journée
  ont dépassé la marge.

## 4. Tests figés qui ne sont plus suivis (responsable de la méthode)

- Tests 9 (fenêtre), 10 (unités de fenêtre) et 11 (alternance) : inscrits « en cours » au registre,
  mais leurs scripts ne figurent pas dans le bilan du soir. Leurs fichiers de trades ne bougent plus.
  Ces scripts lisent le cache : les ajouter au bilan ne coûte aucun appel TradingView.
- « Simple balayage » : verdict ABANDONNÉE fixé au seuil des 100 trades (16/11). Le script affiche
  maintenant « CANDIDATE AU RÉEL » (129 trades, +48,2R ; plafonné 5R +24,2R contre +24,6R pour la
  principale sur la même période ; +14,6R cette semaine). Le verdict tient selon la règle, mais l'écart
  entre le verdict et les chiffres doit être tranché explicitement par l'utilisateur.

## 5. Données et lecture (trader indices, responsable des données)

- Échéance du future CAC le 20/11 : FCE1! est resté sur le contrat de novembre jusqu'au jour
  d'échéance. Le volume lu le 18 et le 19/11 était celui d'un contrat abandonné (« baisse sans
  vendeurs » : faux). Corrigé le 20/11 : normale hors semaines d'échéance, contrats cumulés pendant
  l'échéance (règle 31, complément). Prochaine semaine d'échéance : du 14 au 18/12.
- Lectures sur capture : écarts mesurés après coup jusqu'à 16 points sur un trade (call de 12h30 le
  20/11 : environ −21 estimé sur capture, −5 sur données exactes). Confirme la règle « aucun ordre sur
  capture ».

## 6. Tableaux de calls et puts après coup (statisticien, coach de discipline)

- 20/11, données exactes : 14 trades, +114 points bruts, +72 nets ; +96 nets jusqu'à 17h35, −24 nets
  après (marché peu échangé). Les puts (dans le sens de la tendance) font l'essentiel.
- Ce sont des lectures faites en connaissant la fin, sur une séance de tendance nette. Elles ne disent
  rien d'une séance sans tendance. La famille « réaction aux niveaux » a été rejetée après test.
- Effet secondaire observé : les tableaux en direct entretiennent l'envie de trader en intraday
  (demandes de calls et puts « à mettre en place », « on rate la hausse »).

## Propositions pour décision (dimanche 22/11 au plus tôt)

1. **Exécution du swing** : soit rendre l'exécution fiable (notification sur le téléphone à 17h55 et à
   21h42, un ordre passé dans le quart d'heure, budget TradingView réservé à ces contrôles), soit
   suspendre la phase réelle jusqu'à ce que l'exécution soit possible. Sans exécution, le contrôle des
   30 trades n'avancera jamais.
2. **Risque corrélé** : faire mesurer (relecture des trades existants) la pire séance et la pire
   semaine du modèle avec 5 positions. Si une limite de positions corrélées est voulue, la préparer
   comme test de décembre (fiche écrite, décision le dimanche 6/12).
3. **Quota** : réserver 40 appels par jour aux routines ; direct limité à 15 minutes ou un point toutes
   les 5 minutes (règle 34), tableaux de calls et puts faits une fois par jour, le soir, sur les
   données du bilan (aucun appel en plus). Option payante : extension TradingView (500 appels par
   jour) ou données IBKR une fois le connecteur autorisé.
4. **Tests 9, 10 et 11** : les ajouter au bilan du soir (aucun appel en plus) ou les clore au registre.
5. **Simple balayage** : confirmer l'abandon, ou en faire le test de décembre (règle 29 : un seul test
   par mois).
6. **Semaine d'échéance du 14 au 18/12** : ajouter aux routines l'appel du contrat suivant (un appel de
   plus par lecture de volume).
7. **Calendrier de la recherche** : un seul test en décembre. Candidats notés cette semaine : limite de
   positions corrélées du swing, simple balayage, tableau de niveaux « puts seulement, rien après
   17h35 ». Choix le dimanche 6/12.
