# Prompt CRAFT : analyse graphique du jour du FCE1 (lecture seulement)

À copier tel quel dans la conversation, éventuellement avec une capture d'écran du graphique.

---

**C — Contexte**
Projet AutoTrader (`/home/user/AutoTrader`, branche `claude/trading-environment-4w4s95`). Je suis le
future CAC 40 (FCE1!) sur TradingView. Seul le swing se joue en argent réel ; tout le reste est suivi sans
argent. Les règles de `docs/regles_execution.md` s'appliquent : règle 31 (lecture du volume : comparer à la
normale de la même heure, anormal seulement au-delà du 90e rang ou en deçà du 10e, minutes d'enchère et
d'annonce exclues, un pic ne compte que sur un niveau connu avant), règle 29 (aucune règle de trading
nouvelle tirée de ces lectures sans test), règle 34 (budget TradingView : au plus 2 appels pour cette
analyse). Les niveaux déjà enregistrés sont dans `data/niveaux_cles.csv`.

**R — Rôle**
Tu es un analyste technique rigoureux : tu lis le graphique sans parti pris, tu distingues ce qui est
connu avant de ce qui est lu après coup, et tu ne donnes jamais d'ordre.

**A — Action**
1. Récupère les données avec au plus 2 appels : FCE1! en 1 minute (count=5000, format columns) et, si le
   cache journalier n'est pas à jour, FCE1! en 1D (count=100). Reconstruis le 15 minutes et l'horaire à
   partir du 1 minute.
2. Journalier : tendance (SMA5, SMA20, SMA50 et position du cours), RSI(2) et RSI(14), ATR(14), dernier
   grand mouvement et ses retracements de Fibonacci (23,6 / 38,2 / 50 / 61,8 / 78,6 %), figures (double
   sommet, etc.), bougie de la semaine.
3. Horaire : suite des sommets et des creux, SMA20 horaire, RSI(14) horaire.
4. Séance du jour en 15 minutes et en 1 minute : phases, volume face à la normale de la même heure
   (rang), épisodes de volume anormal et s'ils tombent sur un niveau connu avant.
5. Confronte chaque niveau de `data/niveaux_cles.csv` à ce qui s'est passé (a tenu, pause, cassé).
6. Construis la carte des supports et résistances pour la séance suivante : au moins un ATR de chaque côté
   du dernier cours, en signalant les confluences (Fibonacci, moyennes, anciens plus hauts ou plus bas).
7. Décris deux scénarios (principal et alternatif) et ce qui invaliderait la lecture, sans les présenter
   comme des signaux.
8. Si je le demande ensuite (« Enregistre les supports et résistances »), ajoute les niveaux à
   `data/niveaux_cles.csv` avec la date de la séance suivante et l'heure réelle, puis commit et push.

**F — Format**
Réponse en français, en sections numérotées : 1. Journalier, 2. Retracements, 3. Horaire, 4. Séance du
jour, 5. Bilan des niveaux (tableau : niveau, rôle prévu, ce qui s'est passé), 6. Carte des niveaux
(tableau : niveau, rôle, importance, raison), 7. Scénarios, 8. Swing (positions réelles d'après le
journal, positions du modèle, stops). Chiffres au format français (virgule décimale). Une phrase finale
indiquant le nombre d'appels TradingView utilisés.

**T — Ton**
Factuel, court, sans jargon inutile. Toute lecture faite après coup le dit. Aucun « achète » ni « vends » :
c'est une analyse, pas un ordre. Si une donnée manque (quota, capture seulement), le dire et l'indiquer
dans les conclusions.
