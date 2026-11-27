# AutoTrader : règles permanentes pour Claude

La référence est `docs/regles_execution.md` (règles numérotées) et `docs/registre_tests.csv`. Trois règles
demandent une action de ma part à chaque session :

- **Limite de recherche (règle 29)** : au plus un nouveau test par mois calendaire, décidé un dimanche.
  Tout calcul d'une règle ou variante nouvelle compte, même présenté comme un audit. Avant d'exécuter une
  demande qui dépasse la limite, je le rappelle à l'utilisateur et je n'exécute que s'il confirme
  explicitement qu'il lève la limite pour ce test. Relire des trades existants ou corriger l'outillage ne
  compte pas.
- **Arrêt de la famille de la principale (règle 30)** : si la variante D est abandonnée, je ne lance plus et
  ne commente plus la principale, ses variantes A à D, les tests 8 à 11, le filtre delta ni le pétrole.
- **Demande ambiguë** : je pose la question avant de calculer, au lieu de deviner.

Analyse de séance du FCE1 avec tableau de puts et calls : suivre la règle 37 et le modèle
`docs/analyse_fce1_2026-11-27.md` (données 1 minute, double contrôle avec `scripts/lecture_fce1_jour.py`,
entrées dès 8h15, revue de tous les creux et sommets sur une borne, lecture technique par trade, niveaux
enregistrés ensuite).

Seul le swing est joué en argent réel. Aucune règle de stratégie figée n'est modifiée sans décision écrite
de l'utilisateur dans `docs/regles_execution.md`.
