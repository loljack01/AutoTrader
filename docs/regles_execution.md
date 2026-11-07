# Règles d'exécution (fixées le 05/11/2026 après l'audit)

1. **Une seule source de signaux pour la stratégie principale** : le moteur officiel
   (`scripts/incremental_engine.py`, utilisé par `scripts/day_plan.py`) et le suivi
   `scripts/frozen_15m_calls_trend.py`, sur les bougies 15m de TradingView.
   Les bougies 15m reconstruites à partir du 1m (dossier de travail) ne font **jamais**
   foi : le 05/11 elles ont donné un put à 15h45 au lieu de 16h45.
2. **« Exécute sur le fce1 »** : toujours lancer `day_plan.py` (ligne « Signal de la
   principale ») AVANT toute lecture 1m/5m, et annoncer d'abord ce signal.
3. **Indicateur Pine « Principale 15m »** : il sert d'alerte. En cas de différence avec
   le moteur officiel, c'est le moteur officiel qui compte, et la différence est corrigée.
4. **Données différées** (NQ1! ~10 min, NDX ~15 min) : jamais de décision en temps réel
   sur ces séries ; utiliser une série en temps réel (ex. CAPITALCOM:US100) en
   recalculant l'écart.
5. **Garde-fous** (`scripts/risk_guard.py`, mis à jour le 06/11/2026) : en ARGENT RÉEL,
   arrêt global si le résultat des 91 derniers jours atteint −500 €, arrêt du jour à −3R
   réalisés, pas d'ordre inverse après un stop sans signal du système (point 10). Pour la
   principale (sans argent) : arrêt du jour à −3R, pause si le suivi tombe 15R sous son
   plus haut.
6. **Ordre minimum de 500 €** (courtage gratuit) : levier du turbo = (risque en € × cours /
   distance du stop en points) / 500.
7. **Tailles (remplacé le 06/11/2026 : capital 10 000 €, tolérance 500 € sur 3 mois)** :
   - swing : phase 1 en réel à **25 €** par trade, **5 positions au maximum** (priorité au
     RSI(2) le plus bas), chaque exécution notée dans `data/journal_swing.csv` avec le
     **cours de l'indice** (pas le prix du turbo) ; contrôle d'exécution à 30 trades ;
     frein à −10R ; phase 2 plafonnée à **37,5 €** (jamais 50 €) ;
   - principale : **sans argent**. L'audit du 06/11 lui donne environ 1 % de chances de
     passer sa règle séquentielle avec la condition D. Si elle y passait un jour, ce
     serait à **8-10 € par trade au plus** (à 25 €, une fenêtre de 3 mois sur quatre
     atteindrait −500 € avec le swing) ;
   - produit du swing : turbo infini de 560 à 900 €, levier ≤ 1,6, barrière à au moins 35 %
     du cours (jamais moins de 15 %) ; ordre = max(500 €, exposition / 1,6).
8. **Réponses de l'utilisateur du 06/11/2026** (questions du groupe de travail) :
   - **perte maximale tolérée : 500 € sur 3 mois**, soit 20R à 25 €. Règle globale :
     si le résultat réel cumulé de TOUTES les stratégies en argent sur les 3 derniers
     mois atteint −500 €, tout s'arrête et on fait une révision avant de reprendre
     (les freins propres à chaque stratégie restent en place).
     Calcul descriptif (swing limité à 5 positions, 2012-2026, 1124 trades) : pire
     période de 3 mois −13R, 5e centile −6,4R, pire baisse −31,3R. À 25 € la pire
     période de 3 mois fait −325 € (compatible) ; à 1 % (50 €) elle ferait −650 €
     (incompatible). Taille maximale du swing compatible avec la tolérance :
     500 / 13 ≈ 38 € (0,75 %). La phase 2 du swing est donc plafonnée à 0,75 %.
   - **disponible à 17h25 et à 21h50** : contrôles avant clôture du swing à ces heures
     (indices européens, puis indices américains).
   - **spread payé sur les turbos : 0,01 €** (sur le prix du turbo), soit en points du
     sous-jacent 0,01 × parité (1 point CAC pour une parité de 100). Les coûts des
     modèles (0,05 % du sous-jacent pour le swing, environ 4 points CAC ; 1 et 3 points
     pour la principale) sont donc prudents, hors élargissement du spread à
     l'ouverture et autour des annonces.
9. **Capital porté à 10 000 € (06/11/2026, option D du groupe de travail).**
   Le risque par trade n'est PAS doublé : il reste borné par la tolérance de 500 € sur
   3 mois (pire période de 3 mois du swing : −13R).
   - swing phase 1 : **25 €** par trade (0,25 %), inchangé ; phase 2 : jusqu'à
     **37,5 €** (0,375 %) si le contrôle d'exécution passe ; 50 € (0,5 %) seulement si
     la tolérance est relevée à environ 650-700 € sur 3 mois ;
   - le capital supplémentaire sert à tenir les 5 positions avec peu ou pas de levier
     (environ 700 à 900 € d'exposition chacune, soit 3 500 à 4 500 € au total : ETF ou
     tracker, ou turbo de levier ≤ 1,5), ce qui réduit le risque de désactivation sur un
     écart d'ouverture ;
   - principale (sans argent jusqu'à son verdict) : même borne de 25 € par trade, et la
     règle globale −500 € sur 3 mois s'applique à l'ensemble.
10. **Réponses de l'utilisateur au coach de discipline (06/11/2026)** :
   - ordres réels hors système depuis le 22/10 : **zéro** (le compteur global de −500 € sur
     3 mois part donc de 0 €) ;
   - après une perte : « j'arrête, ou je reprends dans l'autre sens en espérant ». Règle
     ajoutée sur recommandation du coach : **après un stop, aucun ordre dans le sens inverse
     sans signal du système** (moteur officiel ou contrôle swing) ; un ordre inverse « en
     espérant » est un trade de revanche, il est interdit et noté au journal hors système
     s'il est passé quand même ;
   - temps disponible : variable selon les jours, souvent important. La routine reste de
     25 minutes environ (9h05, 17h25, 21h50, 22h15) ; le temps en plus sert au journal et
     à la revue du dimanche, pas à regarder le 1 minute.
11. **Frais de vente des turbos : 0 €** (confirmé par l'utilisateur le 06/11/2026 sur son avis
    d'opéré Boursorama). Achat et vente à 0 € pour les ordres >= 500 € : seul le spread
    (0,01 € sur le prix du turbo) coûte, ce qui reste sous les coûts des modèles. Le swing
    reste donc en turbos sur le compte-titres (avis du fiscaliste : le PEA n'exécute pas les
    signaux US de 22h et sa vente d'ETF serait payante).
12. **Discipline de recherche (audit complet du 06/11/2026, accord de l'utilisateur)** :
    - **moratoire** : aucune nouvelle idée de stratégie testée avant le verdict du test 4
      (P2, 150 trades) ;
    - au plus **une modification de règle par semaine**, décidée le dimanche, jamais en
      séance ni dans les 24 h qui suivent une perte ;
    - la règle et son critère sont commités et poussés dans un commit, le résultat (avec la
      sortie brute) dans un commit séparé ;
    - chaque test et chaque changement de règle de passage est inscrit dans
      `docs/registre_tests.csv` (seuil corrigé selon le nombre cumulé de tests).
13. **Routines** : la « checklist pré-séance CAC 8h50 » (ancien plan v3, 100 € par trade) est
    supprimée le 06/11/2026. Les semaines où la Bourse de New York ferme à 21h00 (heure de
    Paris : Europe et États-Unis pas encore ou plus à la même heure d'été), le contrôle swing
    US se fait à 20h42 (routine dédiée) ; `swing_preclose.py` affiche l'heure de clôture US.
    Audit complet : `docs/audit_complet_2026-11-06.md`.
14. **Ordre minimum de 500 € pour CHAQUE trade (rappel de l'utilisateur, 07/11/2026)** :
    - swing : ordre = max(500 €, exposition / 1,6), au levier exposition / ordre ; dans
      97,5 % des signaux depuis 2012 cela respecte 25 € de risque et un levier ≤ 1,6 ;
    - quand l'exposition pour 25 € de risque est inférieure à 500 € (2,5 % des signaux,
      stops larges, surtout Nasdaq et FTSE MIB), l'ordre reste à 500 € au levier le plus bas
      disponible (~1) : le risque réel monte alors jusqu'à ~34 € (médiane ~27 €), accepté
      pour garder 100 % des signaux ; `swing_preclose.py` l'affiche ;
    - principale (si un jour en réel à 8-10 €) : ordre de 500 € minimum, levier =
      exposition / 500 (≈ 6 pour un stop CAC de 26 points à 10 €).
