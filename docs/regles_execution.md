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
