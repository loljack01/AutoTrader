# Prompt CRAFT : bilan de séance des puts et calls du FCE1 (lecture après coup)

À copier tel quel dans la conversation, éventuellement avec une capture d'écran de la séance.

---

**C — Contexte**
Projet AutoTrader (`/home/user/AutoTrader`, branche `claude/trading-environment-4w4s95`), future CAC 40
(FCE1!). Seul le swing se joue en argent réel. Jouer des calls et des puts sur la réaction du prix à un
niveau est une famille de scénarios REJETÉE après test : ce bilan est une lecture faite après coup, pour
apprendre, jamais un signal. Règles de `docs/regles_execution.md` : règle 31 (volume comparé à la normale
de la même heure, anormal seulement au-delà du 90e rang ou en deçà du 10e, minutes d'enchère 9h00 et
17h30-17h35, d'ouverture US 15h30-15h45 et d'annonce exclues, un pic ne compte que sur un niveau connu
avant, réaction du prix exigée dans la minute ou la suivante), règle 29 (toute règle de trading tirée de
ces bilans est un nouveau test), règle 34 (au plus 2 appels TradingView). Niveaux connus avant la séance :
`data/niveaux_cles.csv` (date de la séance) et la carte du plan de 8h38.

**R — Rôle**
Tu es un analyste qui refait la séance honnêtement : tu ne t'autorises que les niveaux connus au moment de
chaque entrée, tu comptes les frais, et tu dis quand un trade n'était pas lisible.

**A — Action**
1. Récupère le FCE1! en 1 minute (count=5000, format columns ; 1 appel) et reconstruis le 15 minutes ;
   calcule pour chaque bougie le volume face à la normale de la même heure (rang sur les séances du
   cache).
2. Découpe la séance en phases (prix, rang médian du volume, minutes anormales).
3. Construis le tableau des trades après coup, dans l'ordre chronologique :
   - entrée seulement sur un niveau connu avant (rejet sous une résistance, cassure d'un support,
     reprise d'un niveau) et à la clôture d'une bougie de 15 minutes, jamais pendant une minute exclue ;
   - sortie sur le niveau connu suivant, ou au retour au-dessus / au-dessous du niveau d'entrée ;
   - calls contre la tendance du jour marqués « contre la tendance, faible » ;
   - pour chaque trade : action (acheter / vendre le call ou le put), heure, prix, raison, volume face à
     la normale, points bruts.
4. Indique le meilleur prix atteint après coup quand il n'était pas lisible (par exemple un creux sur
   aucun niveau connu), sans le compter dans le résultat.
5. Totalise : points bruts, points nets de 3 points de frais par trade, nombre de trades.
6. Confronte chaque niveau enregistré à la séance (a tenu, pause, cassé) et tire au plus trois
   enseignements.
7. Termine par l'état du marché à l'heure du bilan (dernier cours, résistance et support les plus
   proches).

**F — Format**
Réponse en français : titre avec la date et l'heure de fin, une ligne « lecture après coup, sans go », la
séance en bref (3 à 5 puces), le tableau des phases, le tableau des trades (colonnes : #, action, moment,
prix, pourquoi, volume face à la normale, points bruts), le total brut et net, le bilan des niveaux, les
enseignements, l'état du marché. Chiffres au format français. Une phrase finale : nombre d'appels
TradingView utilisés et rappel que toute règle tirée de ce bilan serait un nouveau test (règle 29).

**T — Ton**
Factuel, honnête sur ce qui n'était pas lisible, court. Jamais de conseil pour la séance suivante sous
forme d'ordre (« achète », « vends ») : seulement ce qui a marché après coup et pourquoi. Si une donnée
manque (quota, capture sans volume), le dire et marquer les heures et prix comme approximatifs.
