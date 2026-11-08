# Fiches pratiques par indice (swing, 07/11/2026)

Document opérationnel, compatible avec le moratoire : aucune règle n'est testée ni modifiée.
Les chiffres se reproduisent avec `python3 scripts/fiches_indices.py` (cache du 06/11 au soir) :
l'ATR et donc le stop, l'exposition et l'ordre changent chaque jour ; le contrôle avant
clôture (`swing_preclose.py`) donne les valeurs du jour au moment du signal.

## Tableau au 06/11/2026 (choix du 07/11 : 500 € par ordre, turbo au levier le plus bas ≈ 2,8)

| Indice | Tendance | Stop de la règle (2,5 ATR) | Perte au stop avec 500 € au levier 2,8 (= 1R) | Trades/an (historique) | R/trade (historique, descriptif) |
|---|---|---|---|---|---|
| CAC 40 | **sous SMA200** | 257 pts (3,2 %) | ≈ 44 € | 7,5 | +0,017 |
| DAX | au-dessus | 932 pts (3,6 %) | ≈ 51 € | 7,0 | +0,042 |
| Euro Stoxx 50 | au-dessus | 214 pts (3,5 %) | ≈ 49 € | 7,0 | +0,013 |
| S&P 500 | au-dessus | 252 pts (3,4 %) | ≈ 48 € | 8,2 | +0,091 |
| Nasdaq 100 | **sous SMA200** | 1 577 pts (5,8 %) | **≈ 82 €** | 8,4 | +0,102 |
| FTSE 100 | au-dessus | 314 pts (2,9 %) | ≈ 41 € | 6,9 | +0,048 |
| SMI | au-dessus | 432 pts (2,9 %) | ≈ 41 € | 7,1 | +0,041 |
| Dow Jones | au-dessus | 1 767 pts (3,4 %) | ≈ 48 € | 9,7 | +0,077 |
| Russell 2000 | **sous SMA200** | 111 pts (4,0 %) | ≈ 56 € | 7,1 | +0,120 |
| FTSE MIB | au-dessus | 2 001 pts (4,0 %) | ≈ 56 € | 6,7 | +0,068 |

Perte au stop = 500 € × levier × distance du stop. Le montant engagé (500 €) n'est pas la perte.
Quand le stop est large (Nasdaq aujourd'hui), la perte au stop dépasse nettement 50 € : chercher
pour cet indice le turbo au levier le plus bas possible (un levier de 2 la ramènerait à ≈ 58 €).
Si un turbo de levier plus bas que 2,8 existe sur un indice, le préférer.

## Produits disponibles (déclaration de l'utilisateur, 08/11/2026)

| Indice | Turbo call accessible | Détails à noter (ISIN, levier, parité, quanto, cotation jusqu'à 22h) |
|---|---|---|
| CAC 40 | oui (Boursomarkets, prix d'exercice 5 250, levier 2,79, échéance 19/03/2027) | ISIN à noter |
| Nasdaq 100 | oui | à compléter |
| Dow Jones | oui : levier le plus bas trouvé ≈ 3,2 : Turbo Illimité/Infini Call Goldman Sachs, **prix d'exercice 35 121,37 USD** (145,08 / 145,09 € le 08/11 ; levier affiché 3,50, levier réel 51 291 / (51 291 − 35 121) ≈ 3,17 ; barrière au-dessus du prix d'exercice, ≈ 29 % sous l'indice d'après le levier affiché) ; Société Générale 36 773,94 USD, levier 3,51 ; non quanto ; filtrer « Call » (la liste mélange calls et puts) | ISIN et cotation jusqu'à 22h à noter |
| Russell 2000 | oui : Turbo Illimité Best Call Société Générale, onglet Boursomarkets, **prix d'exercice 1 440,56 USD, levier 2,09** (11,81 / 11,82 € le 08/11 ; barrière = prix d'exercice, ≈ 48 % sous l'indice à 2 754) ; parité 100 ; non quanto | ISIN et cotation jusqu'à 22h à noter |
| S&P 500 | oui : Turbos Illimités/Infinis Call Goldman Sachs, onglet Boursomarkets, prix d'exercice 4 563 à 4 603 USD (≈ 25 €), levier affiché 2,90 à 2,94, **levier réel ≈ 2,65** (7 377 / (7 377 − 4 588), vérifié sur le prix du turbo) ; barrière au-dessus du prix d'exercice, ≈ 34 % sous l'indice ; non quanto | ISIN et cotation jusqu'à 22h à noter |
| DAX, Euro Stoxx 50, FTSE 100, SMI, FTSE MIB | oui (déclaration du 08/11) ; filtre « barrière maximum » = 65 % du cours : DAX 16 780, Euro Stoxx 50 4 010, FTSE 100 6 940, SMI 9 620, FTSE MIB 32 530 (cours du 06/11) ; FTSE 100 (GBP) et SMI (CHF) : quanto de préférence | levier réel le plus bas, ISIN à noter |

Levier réel = indice / (indice − prix d'exercice) ; c'est lui qui fixe la perte au stop (500 € × levier réel × distance du stop). Goldman Sachs affiche un levier plus élevé (mesuré jusqu'à la barrière, semble-t-il) : se fier au levier réel.

Historique 2012-2026 avec 500 € au levier 2,8, calcul descriptif (5 positions au plus, seulement les
indices exécutables) : 10 indices ≈ +220 €/an (depuis 2018 : +80 €/an) ; CAC + Nasdaq + Dow
≈ +111 €/an (depuis 2018 : +74 €/an), 30 trades/an, pire baisse −498 € ; CAC seul ≈ +18 €/an
(depuis 2018 : −11 €/an).

## Ce qu'il faut chercher chez Boursorama (une fois, avant le premier signal)

Pour chaque indice : un **turbo infini call** (« Turbo Infini », « Open End », « BEST »…)
sur l'indice lui-même, coté sur la plateforme, avec :
- le **levier le plus bas disponible** (≈ 2,8 chez Boursomarkets pour le CAC 40 : prix d'exercice 5 250, échéance 19/03/2027 ; barrière à au moins 35 % sous le cours, jamais plus de 2,85). Un levier plus élevé avec 500 € engagés augmente la perte au stop (levier 3,5 : ≈ 56 € pour un stop de 3,2 %) ;
- une **parité** qui garde le spread de 0,01 € proche de 1 point d'indice (parité 100 pour
  CAC, Euro Stoxx, S&P ; parité plus élevée possible sur DAX, Dow, FTSE MIB : vérifier le coût
  du spread en points = 0,01 × parité) ;
- pour les indices hors euro (S&P 500, Nasdaq 100, Dow Jones, Russell 2000, FTSE 100, SMI) :
  **quanto** de préférence (sans risque de change), sinon accepter environ ±0,2R de bruit par trade ;
- une **cotation jusqu'à 22h** pour les indices américains (signal à 21h50).

Noter l'ISIN retenu par indice dans la colonne `isin` du journal. **À vérifier en priorité**
(risque de ne trouver aucun turbo à faible levier) : Russell 2000, SMI, FTSE 100, FTSE MIB.
Si un indice n'a aucun produit adapté, le dire : le signal sera noté « non exécutable » (il
compte comme signal manqué au contrôle d'exécution).

## Horaires et calendriers

| Indice | Clôture (heure de Paris) | Enchère de clôture | Contrôle avant clôture | Jours fériés propres (marché fermé) |
|---|---|---|---|---|
| CAC 40 | 17h30 | 17h30-17h35 | 17h12 | Euronext : 1er janvier, Vendredi saint, lundi de Pâques, 1er mai, 25 et 26 décembre |
| DAX | 17h30 | 17h30-17h35 (Xetra) | 17h12 | Xetra : comme Euronext, plus 24 et 31 décembre |
| Euro Stoxx 50 | 17h30 | — (indice calculé) | 17h12 | Eurex / STOXX : comme Euronext |
| FTSE MIB | 17h30 | 17h30-17h35 | 17h12 | Borsa Italiana : comme Euronext, plus 24 et 31 décembre, 15 août |
| FTSE 100 | 17h30 (16h30 Londres) | 17h30-17h35 | 17h12 | Royaume-Uni : lundis fériés (début mai, fin mai, fin août), 26 décembre |
| SMI | 17h30 | 17h20-17h30 | 17h12 | Suisse : 2 janvier, Ascension, lundi de Pentecôte, 1er août, 24 et 31 décembre |
| S&P 500, Nasdaq 100, Dow Jones, Russell 2000 | **22h00** (16h00 New York) ; **21h00** les semaines de décalage d'heure d'été (environ 2e et 3e semaines de mars, dernière semaine d'octobre) | — | 21h42 (20h42 les semaines de décalage) | États-Unis : 1er janvier, Martin Luther King (3e lundi de janvier), Presidents' Day (3e lundi de février), Vendredi saint, Memorial Day (dernier lundi de mai), 19 juin, 4 juillet, Labor Day (1er lundi de septembre), Thanksgiving (4e jeudi de novembre), 25 décembre |

**Clôtures anticipées aux États-Unis (13h00 New York = 19h00 Paris)** : lendemain de
Thanksgiving (**vendredi 27/11/2026**), **jeudi 24/12/2026**, et parfois le 3 juillet. Ces jours-là
le contrôle de 21h42 arrive après la clôture : faire le contrôle US vers 18h40.

Les données des indices cash TradingView ont des **ouvertures fausses** (FTSE 100 surtout) :
le contrôle et le modèle n'utilisent que les clôtures, mais une sortie à l'ouverture se lit sur
le turbo ou le future, pas sur l'ouverture de l'indice cash.
