#!/bin/bash
# Lance chaque script figé dans une COPIE du dépôt (aucune écriture dans le dépôt) et
# extrait les lignes de contrôle de référence. Usage : bash ref_checks.sh
C=/tmp/audit_copie; rm -rf $C; cp -r /home/user/AutoTrader $C; cd $C
export PYTHONDONTWRITEBYTECODE=1
for s in frozen_puts_5m frozen_15m_daily frozen_15m_markets frozen_15m_calls_trend frozen_15m_fresh_choch frozen_15m_single_sweep frozen_gap_continuation frozen_15m_oil frozen_swing_rsi2 frozen_15m_variants; do
  echo "######## $s"
  timeout 900 python3 scripts/$s.py 2>&1 | grep -iE "reference|controle|DIFFERENT|OK|Passage|PASSE|ABANDON|historique|verdict|ensemble|clos" | head -40
done
