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
5. **Garde-fous** (`scripts/risk_guard.py`) : 0,5 à 1 % de risque par trade ; plus de
   nouveau trade dans la journée après −3R réalisés ; pause et révision si le suivi réel
   tombe 15R sous son plus haut.
6. **Ordre minimum de 500 €** (courtage gratuit) : levier du turbo = (risque en € × cours /
   distance du stop en points) / 500.
7. **Capital 5 000 € (05/11/2026), tailles décidées après le groupe de travail :**
   - principale : **0,5 % = 25 €** par trade, et seulement après son verdict séquentiel
     (+72R plafonnés, voir `frozen_15m_calls_trend.py`) ;
   - swing : phase 1 en réel à **0,5 % = 25 €** par trade, **5 positions au maximum**
     (priorité au RSI(2) le plus bas), chaque exécution notée dans
     `data/journal_swing.csv` ; contrôle d'exécution à 30 trades ; frein à −10R ;
     phase 2 jusqu'à 1 % seulement si le contrôle passe et avec l'accord de l'utilisateur
     (recommandé 0,5-0,75 % : pire baisse historique −40R).
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
