# Test 11 figé le 14/11/2026 : la règle d'alternance, avec et sans filtre, AVANT tout trade en avant

Accord de l'utilisateur du 14/11/2026 (« Ok »), après l'audit du même jour
(`docs/audit_ordres_multiples_2026-11-14.md`, sections 5 et 6). Moratoire du 06/11 levé pour ce seul test.
Figé un samedi, marchés fermés : aucun trade ne peut exister avant le départ du suivi.

## La règle (utilisateur, 14/11)

« Il ne peut y avoir 2 calls en même temps et 2 puts en même temps. Si on est en call, derrière on fait un
put. Si on a un put, derrière on fait un call. »

Version retenue de l'audit (« A+R »), appliquée aux signaux de la principale sans rien changer d'autre :

| Élément | Règle |
|---|---|
| Alternance | sur un indice, un signal n'est pris que s'il est de sens opposé au dernier trade pris sur cet indice |
| Retournement | si le trade précédent est encore ouvert, il est fermé à la clôture de la bougie du signal (une seule position à la fois sur l'indice) |
| Même bougie | si un call et un put sont possibles ensemble, seul celui dont le balayage est le plus récent est pris |
| État au départ | la règle est appliquée depuis le début de l'historique de chaque marché : le dernier sens et le trade ouvert au départ sont ceux qu'elle donne |

Tout le reste est la principale : même moteur, mêmes 10 marchés, mêmes facteurs, mêmes frais, fenêtre de
4 h.

## Versions suivies

- **E1** : alternance **avec** le filtre (calls seulement au-dessus de la moyenne 20 jours, puts toujours).
- **E2** : alternance **sans** le filtre (calls et puts toujours autorisés).
- Chacune aussi dans sa forme exécutable en turbo (entrées 8h-21h30, sortie à 21h45 au plus tard).
- Référence : la principale sur la même période.

**Suivi en avant uniquement** : seuls comptent les trades entrés à partir du **dimanche 15/11/2026 à 23h00
(Paris)**. Les chiffres de l'audit ne servent jamais à juger.

## Critère, fixé avant tout trade

Verdict pour E1 et pour E2, chacune quand elle a **100 trades clos** en avant (coupure = sortie de son 100e
trade ; la principale et la forme turbo sont comptées jusqu'à la même coupure). La version devient la
candidate qui remplace la principale (après discussion avec l'utilisateur) seulement si **toutes** ces
conditions sont vraies sur cette période :

1. son résultat net avec chaque gain **plafonné à +5R** (1 pt) est supérieur à celui de la principale ;
2. son résultat net à 3 pts est **> 0** ;
3. sa forme exécutable en turbo a un résultat net à 3 pts **> 0**.

**Le filtre** est jugé par E1 contre E2 : si les deux passent, E2 n'est préférée que si elle est au-dessus
de E1 **à la fois** sur le résultat plafonné (1 pt) et sur le résultat à 3 pts, comparés à la coupure de
E2 ; sinon E1.

**Frein** : une version dont le cumul plafonné (1 pt) atteint −15R à un moment quelconque est abandonnée.

Une version retenue **ne passe pas en argent réel** : elle commencerait son propre test séquentiel (règle
du 05/11) à zéro. La principale n'est pas modifiée.

## Limites annoncées

- L'alternance prend environ 40 à 65 trades en deux semaines et demie : le verdict demandera cinq à six
  semaines.
- Dans l'audit, A+R était la meilleure de cinq variantes essayées, donc en partie choisie après coup ; ses
  scores n'étaient pas significatifs (t ≤ 2,27, seuil du registre 3,22). Ce suivi est là pour le vérifier
  sur des trades que personne n'a vus.
- Avec le filtre, l'alternance met un indice en sommeil après un put tant qu'aucun call n'est revenu.
- Le critère ne demande pas de seuil statistique : c'est le test séquentiel qui suivrait qui protège du
  hasard, pas ce verdict.

Script : `scripts/frozen_15m_alternance.py` (docstring identique à cette règle ; il utilise le simulateur
de `audit/2026-11-14/`, contrôlé identique au moteur à chaque passage). Première sortie brute dans un
commit séparé.
