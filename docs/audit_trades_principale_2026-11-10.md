# Audit des trades de la principale, trade par trade (28/10 → 09/11/2026)

Demande de l'utilisateur du 10/11/2026 : « Fais un audit complet des 47 trades et indique pourquoi ça
n'a pas fonctionné ». Document descriptif : aucune règle n'est testée ni modifiée (moratoire du 06/11).
Les chiffres se reproduisent avec `python3 audit/2026-11-10/audit_trades_principale.py` (sortie brute :
`audit/2026-11-10/out_audit_trades.txt`, détail : `audit_trades_principale.csv`).

Périmètre : stratégie principale, version SMA20, suivie **sans argent**. Le fichier compte aujourd'hui
**49 trades** : les 47 du tableau du 09/11, plus 2 puts pris le 09/11 (Russell 2000 et S&P 500).
Chaque trade a été relu sur les bougies de 15 minutes.

## Le résultat, d'abord

| | |
|---|---|
| Trades clos | 44 : **14 OK, 30 KO** |
| Trades ouverts | 5 (latent total +9,1R au 09/11 à 22h00) |
| Résultat net (1 pt de frais) | **+13,20R** (+9,14R avec gains plafonnés à 5R) |
| Les 4 meilleurs trades | +21,97R |
| Les 40 autres trades clos | **−8,77R** |
| Gain moyen d'un OK | +3,16R |
| Taux de réussite | 32 % (seuil d'équilibre : 24 %) |
| Intervalle de confiance à 95 % du taux de réussite | 20 % à 47 % |
| t de Student par trade | 0,90 |

Le suivi n'est pas négatif. Mais il ne « fonctionne » pas au sens où il ne prouve rien : hors 4 trades,
il perd 8,8R, et son taux de réussite ne se distingue pas du seuil d'équilibre.

## Pourquoi les 30 KO

| Ce qui s'est passé | Nombre | Part |
|---|---|---|
| Faux dès le départ (jamais +0,25R de gain latent) | 7 | 23 % |
| Petit gain latent (0,25R à 1R), puis retournement jusqu'au stop | 14 | 47 % |
| Parti dans le bon sens (au moins +1R), puis retour au stop | 9 | 30 % |

Autres mesures sur les KO :

| Mesure | Résultat |
|---|---|
| Le prix est allé au moins 1R plus loin que le stop dans les 24 h (le sens du signal était faux) | 22 sur 30 |
| L'objectif a été atteint dans les 48 h après le stop | 15 sur 30 |
| Les deux à la fois (aller-retour du marché) | 9 sur 30 |
| Stop touché sur une bougie d'ouverture (9h00, 9h15, 15h30, 15h45) | 7 sur 30 |
| Stop au minimum de la règle (2 ATR 15 minutes, environ 0,35 % du cours) | 12 KO sur 30, contre 6 OK sur 14 |
| Objectif visé | 2,6R en médiane, jusqu'à 7,7R |

## Les causes, par ordre d'importance

1. **Un objectif lointain, rarement atteint.** La cible est la prochaine « piscine de liquidité », à 2,6R en
   médiane. 23 KO sur 30 ont été en gain latent avant de revenir au stop. Deux ont atteint +3,2R et +4,0R
   (Russell put du 02/11, Dow call du 30/10) et finissent à −1R. La règle n'a ni stop suiveur ni sortie
   partielle. Ce n'est pas une piste neuve : la cible avancée à 80 % et le stop ramené à l'entrée à +1R
   ont été testés le 26/10 et **rejetés** (registre des tests, ligne 11).
2. **Le sens du signal était faux trois fois sur quatre.** Dans 22 KO sur 30, le prix a continué d'au moins
   1R au-delà du stop dans la journée : le stop a limité la perte, il n'était pas « trop serré ». La taille
   du stop n'explique pas les KO : la proportion de stops au minimum est la même chez les OK (43 %) et les
   KO (40 %).
3. **Un marché en allers-retours.** Dans 15 KO sur 30, l'objectif a quand même été atteint dans les 48 h.
   La période (28/10 → 09/11) a connu de fortes oscillations : pire séance du Nasdaq 100 depuis 2020 le
   05/11, puis rebond les 06 et 09/11. Un balayage suivi d'un changement de structure donne des signaux
   dans les deux sens sur ce type de marché.
4. **Le Russell 2000 pèse trop.** 16 trades clos sur 44 (36 %), 12 KO, −0,42R. Le Dow Jones : 4 KO sur 4,
   −4,17R. Le gain vient du CAC 40 (+7,10R) et du S&P 500 (+5,93R, un seul trade à +8R).
5. **Les entrées de nuit (0h-7h).** 7 trades, 1 OK, −3,73R. Elles ne sont de toute façon pas exécutables
   avec un turbo.
6. **Les puts pris contre la tendance journalière** (clôture de la veille au-dessus de la SMA20) : 22 trades
   clos, 6 OK, −1,66R. **Mais ce constat est fragile** : les 3 puts encore ouverts (SMI, FTSE 100, DAX) sont
   de ce type et ont atteint +10,9R, +9,3R et +3,5R de gain latent avant de retomber à +1,3R, +2,3R et +0,1R.

## Ce que l'audit ne permet pas de conclure

- 44 trades clos sur 9 séances : chaque sous-groupe compte 4 à 22 trades. Aucun de ces écarts n'est
  significatif. Les lire comme des règles (« supprimer le Russell », « plus de puts contre la tendance »)
  serait un tri après coup, ce que le moratoire interdit.
- Le suivi continue jusqu'au contrôle des 100 trades (règle séquentielle du 05/11 : +72R plafonnés). À
  +9,1R plafonnés sur 44 trades, il est loin de la barre. La condition D (exécutable turbo) est à −2,6R
  sur 5 trades depuis le 06/11.
- Correction : le 10/11, j'avais indiqué 10 KO ayant atteint +1R avant le stop. Le compte exact est 9
  (la bougie du stop elle-même n'est plus comptée dans le gain latent).

## Les 49 trades

Heure de Paris, début de la bougie d'entrée (l'entrée se fait à sa clôture, 15 minutes plus tard).
« Max latent » : meilleur gain latent atteint avant la sortie.

| # | Entrée | Marché | Sens | Résultat | Objectif | Max latent | Ce qui s'est passé | Remarques |
|---|---|---|---|---|---|---|---|---|
| 1 | 28/10 09:15 | CAC 40 | call | OK +1,65R | 1,7R | +1,82R | objectif atteint |  |
| 2 | 28/10 11:00 | Russell 2000 | put | KO -1,05R | 4,0R | +0,05R | faux dès le départ | put contre la tendance |
| 3 | 28/10 11:00 | Euro Stoxx 50 | put | KO -1,03R | 3,5R | +0,04R | faux dès le départ |  |
| 4 | 28/10 18:30 | Russell 2000 | put | KO -1,05R | 1,4R | +1,42R | parti dans le bon sens (≥ 1R) puis retour au stop | put contre la tendance ; objectif atteint après le stop |
| 5 | 28/10 19:30 | Dow Jones | put | KO -1,04R | 1,5R | +1,01R | parti dans le bon sens (≥ 1R) puis retour au stop | put contre la tendance ; objectif atteint après le stop |
| 6 | 28/10 21:00 | Russell 2000 | call | KO -1,01R | 2,5R | +1,29R | parti dans le bon sens (≥ 1R) puis retour au stop |  |
| 7 | 29/10 01:15 | S&P 500 | call | KO -1,03R | 4,5R | +0,47R | petit gain latent puis retournement | hors 8h-21h30 |
| 8 | 29/10 04:15 | Russell 2000 | put | KO -1,04R | 3,1R | +0,07R | faux dès le départ | put contre la tendance ; hors 8h-21h30 ; objectif atteint après le stop |
| 9 | 29/10 05:30 | DAX | call | KO -1,06R | 6,1R | +1,12R | parti dans le bon sens (≥ 1R) puis retour au stop | hors 8h-21h30 ; objectif atteint après le stop |
| 10 | 29/10 09:15 | Dow Jones | put | KO -1,05R | 2,6R | +0,96R | petit gain latent puis retournement | put contre la tendance ; objectif atteint après le stop |
| 11 | 29/10 10:30 | FTSE MIB | call | KO -1,02R | 1,7R | +1,38R | parti dans le bon sens (≥ 1R) puis retour au stop | stop à une ouverture ; objectif atteint après le stop |
| 12 | 29/10 18:30 | Russell 2000 | put | OK +3,95R | 4,0R | +4,03R | objectif atteint | put contre la tendance |
| 13 | 29/10 18:45 | FTSE MIB | put | OK +1,97R | 2,0R | +2,82R | objectif atteint | put contre la tendance |
| 14 | 29/10 21:00 | Euro Stoxx 50 | put | OK +3,96R | 4,0R | +4,01R | objectif atteint |  |
| 15 | 29/10 21:30 | DAX | put | OK +2,06R | 2,1R | +2,11R | objectif atteint | put contre la tendance ; hors 8h-21h30 |
| 16 | 30/10 02:00 | Dow Jones | put | KO -1,04R | 2,1R | +0,49R | petit gain latent puis retournement | put contre la tendance ; hors 8h-21h30 ; objectif atteint après le stop |
| 17 | 30/10 11:45 | FTSE 100 | put | OK +1,67R | 1,7R | +1,88R | objectif atteint | put contre la tendance |
| 18 | 30/10 14:45 | FTSE 100 | call | KO -1,04R | 4,1R | +0,00R | faux dès le départ |  |
| 19 | 30/10 20:45 | Dow Jones | call | KO -1,04R | 7,7R | +4,01R | parti dans le bon sens (≥ 1R) puis retour au stop | objectif atteint après le stop |
| 20 | 02/11 07:00 | Russell 2000 | put | KO -1,06R | 7,6R | +0,88R | petit gain latent puis retournement | put contre la tendance ; hors 8h-21h30 |
| 21 | 02/11 10:15 | Russell 2000 | call | KO -1,04R | 2,4R | +0,78R | petit gain latent puis retournement | stop à une ouverture ; objectif atteint après le stop |
| 22 | 02/11 10:15 | FTSE 100 | call | KO -1,04R | 4,7R | +0,43R | petit gain latent puis retournement | objectif atteint après le stop |
| 23 | 02/11 13:00 | SMI | call | OK +2,01R | 2,1R | +2,11R | objectif atteint |  |
| 24 | 02/11 18:15 | Russell 2000 | put | KO -1,02R | 3,6R | +3,17R | parti dans le bon sens (≥ 1R) puis retour au stop | put contre la tendance ; objectif atteint après le stop |
| 25 | 02/11 18:30 | Russell 2000 | call | KO -1,02R | 1,7R | +0,47R | petit gain latent puis retournement | objectif atteint après le stop |
| 26 | 03/11 09:15 | Russell 2000 | call | OK +2,79R | 2,8R | +2,86R | objectif atteint |  |
| 27 | 03/11 10:00 | DAX | call | OK +2,35R | 2,4R | +2,51R | objectif atteint |  |
| 28 | 03/11 12:45 | CAC 40 | put | KO -1,05R | 6,8R | +0,35R | petit gain latent puis retournement | put contre la tendance |
| 29 | 03/11 17:00 | CAC 40 | put | KO -1,01R | 1,8R | +0,26R | petit gain latent puis retournement | put contre la tendance |
| 30 | 03/11 17:30 | DAX | put | KO -1,01R | 2,4R | +1,47R | parti dans le bon sens (≥ 1R) puis retour au stop | put contre la tendance |
| 31 | 03/11 18:00 | FTSE MIB | put | KO -1,01R | 1,3R | +0,23R | faux dès le départ | put contre la tendance ; stop à une ouverture |
| 32 | 04/11 07:15 | Russell 2000 | call | OK +2,54R | 2,6R | +2,72R | objectif atteint | hors 8h-21h30 |
| 33 | 04/11 08:00 | CAC 40 | call | OK +6,06R | 6,1R | +6,79R | objectif atteint |  |
| 34 | 04/11 13:00 | Russell 2000 | put | KO -1,03R | 6,8R | +0,15R | faux dès le départ | put contre la tendance ; objectif atteint après le stop |
| 35 | 04/11 16:15 | Russell 2000 | put | KO -1,01R | 1,7R | +0,23R | faux dès le départ | put contre la tendance ; objectif atteint après le stop |
| 36 | 04/11 21:45 | S&P 500 | put | OK +8,00R | 8,0R | +10,43R | objectif atteint | hors 8h-21h30 |
| 37 | 05/11 07:45 | Russell 2000 | call | KO -1,04R | 5,1R | +1,97R | parti dans le bon sens (≥ 1R) puis retour au stop | hors 8h-21h30 ; stop à une ouverture |
| 38 | 05/11 09:15 | SMI | put | ouvert +1,31R | 13,3R | +10,88R | en cours (a atteint +10,88R au mieux) | put contre la tendance |
| 39 | 05/11 09:45 | FTSE 100 | put | ouvert +2,32R | 9,5R | +9,30R | en cours (a atteint +9,30R au mieux) | put contre la tendance |
| 40 | 05/11 12:00 | CAC 40 | put | KO -1,03R | 1,7R | +0,41R | petit gain latent puis retournement | put contre la tendance ; objectif atteint après le stop |
| 41 | 05/11 12:00 | FTSE MIB | call | KO -1,03R | 2,7R | +0,54R | petit gain latent puis retournement | stop à une ouverture |
| 42 | 05/11 14:00 | Russell 2000 | put | OK +2,73R | 2,8R | +2,99R | objectif atteint | put contre la tendance |
| 43 | 05/11 15:45 | DAX | put | ouvert +0,08R | 4,6R | +3,48R | en cours (a atteint +3,48R au mieux) | put contre la tendance |
| 44 | 05/11 16:45 | CAC 40 | put | OK +2,48R | 2,5R | +2,68R | objectif atteint | put contre la tendance |
| 45 | 06/11 14:15 | Euro Stoxx 50 | put | KO -1,02R | 1,7R | +0,59R | petit gain latent puis retournement | put contre la tendance ; stop à une ouverture |
| 46 | 06/11 15:45 | CAC 40 | call | ouvert +1,48R | 2,4R | +1,70R | en cours (a atteint +1,70R au mieux) |  |
| 47 | 06/11 16:00 | Euro Stoxx 50 | call | ouvert +3,94R | 5,0R | +4,34R | en cours (a atteint +4,34R au mieux) |  |
| 48 | 09/11 08:15 | Russell 2000 | put | KO -1,04R | 5,1R | +0,57R | petit gain latent puis retournement | stop à une ouverture |
| 49 | 09/11 09:30 | S&P 500 | put | KO -1,04R | 1,7R | +0,61R | petit gain latent puis retournement |  |
