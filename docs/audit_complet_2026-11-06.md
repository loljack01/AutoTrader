# Audit complet du 06/11/2026 (9 experts, 3 pôles)

Experts : quant académique, mathématicien, quant data (pôle recherche) ; trader pro,
analyse graphique, fondamental (pôle marché) ; spécialiste turbos/exécution, fiscaliste,
coach de discipline (pôle exécution et client).

Chaque chiffre est reproductible par les scripts de `audit/2026-11-06/<pôle>/` (sorties
`*.out` / `out_*.txt` à côté). Aucune règle nouvelle n'a été testée ; le dépôt n'a pas été
modifié pendant l'audit. Lancer depuis le dossier du pôle, par exemple :
`cd audit/2026-11-06/execution && python3 -W ignore costs.py`.

## Synthèse transverse

| Sujet | Verdict | Constat principal | Reproduire |
|---|---|---|---|
| Intégrité de la recherche | fragile | 65/65 contrôles de référence OK ; mais 18 tests avec règle et résultat dans le même commit, 9 rejets sans chiffre écrit, règle de passage de la principale modifiée 3 fois avec le suivi connu (toujours plus stricte) | `recherche/git_integrity.py`, `ref_checks.sh`, `tests_inventaire.py` |
| Tests multiples | fragile | 57 décisions, ~3 197 hypothèses ; aucune validation ne survit seule à Bonferroni/Holm (t ≥ 3,13) ; seul le swing combiné 2012-2026 + 1991-2011 passe (z = 3,71) | `recherche/tests_inventaire.py` |
| Principale : backtest vs suivi | tient | suivi cohérent avec l'historique (R moyen +0,345 vs +0,327, p = 0,97) | `recherche/section2_principale.py` |
| Principale : avantage | fragile | 11 trades > 5R font +115R (plus que le total) ; sans eux −3,6R ; aucun découpage connu à l'entrée n'est significatif | `marche/analyse_principale.py` |
| Principale : passage en réel | ne tient pas | version exécutable D : +0,019R/trade à 1 pt, −0,068R à 3 pts ; ~1 % de chances de passer la règle séquentielle | `recherche/section2_principale.py` |
| Swing : avantage | fragile | +71R sur 1 124 trades (+0,063R) ; 2012-2017 t = 3,82 mais 2018-2026 t = 0,27 ; US = 67 % du gain ; 5 % des trades = 74 % du total | `recherche/section3_swing.py`, `section3_periodes.py`, `marche/swing_regimes.py` |
| Swing : risque et taille | tient | pire 3 mois −13R (−326 € à 25 €) ; jamais −500 € à 25 € ni à 37,5 € ; 3 fois à 50 € | `execution/guards.py` |
| Swing : coûts et impôt | tient | coûts réels ≈ 0,017R/trade (modèle 0,018R) ; ≈ +122 €/an avant impôt, ≈ +79 €/an après PFU 31,4 % | `execution/costs.py` |
| Swing : week-end et barrière | tient | aucun lundi au-delà du stop en 14 ans ; levier ≤ 1,5 : aucune barrière touchée | `marche/gaps.py` |
| Chaîne d'exécution du swing | fragile | contrôle avant clôture vs bilan : 11 faux signaux, 5 manqués sur 41 ; journal en prix de turbo fausse le glissement ; clôture US à 21h00 certaines semaines (contrôle à 21h42 trop tard) | `execution/replay_preclose.py`, `journal_check.py`, `dst_check.py` |
| Risque global | fragile | −500 € / 3 mois non codé ; avec la principale à 25 € en plus, une fenêtre de 3 mois sur quatre atteint −500 € | `execution/guards.py`, `recherche/section4_correlations.py` |
| Corrélations | tient | principale / swing 0,03 ; principale / simple balayage 0,84 (même stratégie) | `recherche/section4_correlations.py` |
| Données | tient | pièges : date de séance des futures US (veille 18h NY), ouvertures FTSE 100 fausses (89 %), minutes 1m manquantes 8-35 % | `recherche/section5_*.py` |
| Comportement / rythme | ne tient pas | ~22 idées par semaine depuis le 22/10, 46 % nées en séance ; 89 % des rejets le jour du gel ; swing gelé et passé en réel le même soir | `execution/behaviour.py` |
| Cohérence docs / routines / code | ne tient pas | routine « Checklist pré-séance CAC 8h50 » encore au plan v3 (100 €/trade) ; risk_guard à 5 000 € et année 2026 en dur ; plan du matin avec scénarios rejetés et sans positions swing | `execution/` (voir rapport) |

## Ce qui en découle (à décider par l'utilisateur)

1. Le swing reste la seule stratégie en argent, à 25 € par trade ; phase 2 plafonnée à
   37,5 € ; espérance honnête : quelques dizaines d'euros par an après impôt, avec des
   années négatives (2018 : −441 €).
2. La principale n'a quasiment aucune chance de passer en réel dans sa version exécutable ;
   si elle y passait, ce serait à 8-10 € par trade au plus, pas 25 €.
3. Corrections d'outillage (sans changer aucune règle de trading) : contrôle avant
   clôture (places, indices occupés, « À CONFIRMER » près des seuils), contrôle de
   glissement (alerte « prix de turbo ? »), compteur −500 € / 91 jours et −3R par jour,
   capital 10 000 € et année dans risk_guard, plan du matin sans scénarios rejetés et avec
   les positions swing, routine de 8h50 supprimée ou réécrite, contrôle US à 20h42 les
   semaines de décalage horaire.
4. Process : moratoire sur les nouvelles idées jusqu'au verdict du test 4 ; une
   modification par semaine, décidée le dimanche ; gel et résultat dans deux commits
   séparés ; registre unique des tests.
