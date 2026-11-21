#!/bin/bash
# Délai (secondes) entre le commit qui fige une règle et celui qui ajoute son résultat.
# Usage : bash delais_gel_resultat.sh
cd /home/user/AutoTrader
while read a b lab; do
  ta=$(git log -1 --format=%at $a); tb=$(git log -1 --format=%at $b)
  echo "$lab : $a -> $b  $((tb-ta)) s"
done <<'L'
0746bc4 a221317 1m_contexte
ff107fa a26a568 1m_exclusif
bccba12 52eb209 1m_marge16
8191138 6f996b2 IB_rotation
226c296 d9ea730 SMT
5d4a0eb a0ee070 papamallis
265b14b c7d773e structure_5m
ed6b223 3f7eee8 rotation_sectorielle
f170711 2cceb3b swing_RSI2+momentum
d1abab6 21aa266 NR7
77181f2 7799afb validation_swing(8_indices_a_telecharger)
117745c 77f0489 tournant_du_mois
fad8c5b 259b281 swing_2_positions
8328601 adc9c3c swing_1991-2011(donnees_a_telecharger)
2c2d347 332f1a0 limite_5_positions
b808b85 ff2fe9a tests_1-3
L
echo "Scripts dont la regle et le resultat (message du commit) sont dans le MEME commit :"
for c in 321adb5 6f42ca5 f66b1ad 05d6792 7985e51 0933b45 1f0828e 97239b2 752b631 8762eab 39259dd 306b5d5 daf3e25 3fe82f1 175bd05 ce89557 060853a ee9e6ee; do git log -1 --format='  %h %ad %s' --date=format:'%d/%m %H:%M' $c | cut -c1-110; done
