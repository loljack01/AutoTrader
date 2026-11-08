# Fiches pratiques par indice (swing, 07/11/2026)

Document opérationnel, compatible avec le moratoire : aucune règle n'est testée ni modifiée.
Les chiffres se reproduisent avec `python3 scripts/fiches_indices.py` (cache du 06/11 au soir) :
l'ATR et donc le stop, l'exposition et l'ordre changent chaque jour ; le contrôle avant
clôture (`swing_preclose.py`) donne les valeurs du jour au moment du signal.

## Tableau au 06/11/2026 (500 € par ordre, turbo call au levier réel le plus bas trouvé le 08/11)

| Indice | Tendance | Stop de la règle (2,5 ATR) | Turbo retenu (levier réel) | Perte au stop avec 500 € (= 1R) | Trades/an | R/trade (historique) |
|---|---|---|---|---|---|---|
| CAC 40 | **sous SMA200** | 257 pts (3,2 %) | Boursomarkets 5 250 € (2,79) | ≈ 44 € | 7,5 | +0,017 |
| DAX | au-dessus | 932 pts (3,6 %) | Goldman Sachs 14 724 € (2,33) | ≈ 42 € | 7,0 | +0,042 |
| Euro Stoxx 50 | au-dessus | 214 pts (3,5 %) | Goldman Sachs 4 449 € (3,58) | ≈ 62 € | 7,0 | +0,013 |
| S&P 500 | au-dessus | 252 pts (3,4 %) | Goldman Sachs ~4 588 USD (2,65) | ≈ 45 € | 8,2 | +0,091 |
| Nasdaq 100 | **sous SMA200** | 1 577 pts (5,8 %) | Goldman Sachs 19 641,59 USD (3,67) | **≈ 107 €** (≈ 62 € au stop habituel de 3,35 %) | 8,4 | +0,102 |
| FTSE 100 | au-dessus | 314 pts (2,9 %) | Goldman Sachs 7 626,69 GBP (3,50) | ≈ 52 € | 6,9 | +0,048 |
| SMI | au-dessus | 432 pts (2,9 %) | Société Générale 7 798,17 CHF (2,11) | ≈ 31 € | 7,1 | +0,041 |
| Dow Jones | au-dessus | 1 767 pts (3,4 %) | Goldman Sachs 35 121,37 USD (3,17) | ≈ 55 € | 9,7 | +0,077 |
| Russell 2000 | **sous SMA200** | 111 pts (4,0 %) | Société Générale 1 440,56 USD (2,09) | ≈ 42 € | 7,1 | +0,120 |
| FTSE MIB | au-dessus | 2 001 pts (4,0 %) | Société Générale 36 958,91 € (3,82) | ≈ 76 € | 6,7 | +0,068 |

Perte au stop = 500 € × levier réel × distance du stop. Le montant engagé (500 €) n'est pas la perte.
Historique 2012-2026 avec ces leviers (descriptif) : ≈ +236 €/an avant impôt (depuis 2018 : +94 €/an),
pire période de 3 mois −514 €, pire baisse −1 052 €, pire trade −119 €, perte au stop médiane 40 €
(90e centile 69 €, maximum 119 €) ; arrêt à −500 € au total atteint dans la 1re année pour 5 % des mois
de départ, à un moment quelconque pour 15 %.
Levier réel = indice / (indice − prix d'exercice). Goldman Sachs affiche un levier faux hors zone euro
(cours de l'indice en USD ou GBP divisé par le prix en euros) : trop haut sur les indices américains,
trop bas sur le FTSE 100.

## Produits disponibles (déclaration de l'utilisateur, 08/11/2026)

| Indice | Turbo call accessible | Détails à noter (ISIN, levier, parité, quanto, cotation jusqu'à 22h) |
|---|---|---|
| CAC 40 | oui (Boursomarkets, prix d'exercice 5 250, levier 2,79, échéance 19/03/2027) | ISIN à noter |
| Nasdaq 100 | oui : levier réel le plus bas trouvé **≈ 3,67** : Turbo Illimité/Infini Call Goldman Sachs, prix d'exercice 19 641,59 USD (65,89 € le 08/11 ; levier affiché 4,01, gonflé par l'EUR/USD ; prix d'exercice 27 % sous l'indice, barrière un peu au-dessus) ; Société Générale Best 20 199,29 USD, levier 3,94 ; perte au stop ≈ 62 € pour un stop médian de 3,35 % (≈ 107 € avec le stop actuel de 5,8 %) ; non quanto | ISIN et cotation jusqu'à 22h à noter |
| Dow Jones | oui : levier le plus bas trouvé ≈ 3,2 : Turbo Illimité/Infini Call Goldman Sachs, **prix d'exercice 35 121,37 USD** (145,08 / 145,09 € le 08/11 ; levier affiché 3,50, levier réel 51 291 / (51 291 − 35 121) ≈ 3,17 ; prix d'exercice 31,5 % sous l'indice, barrière un peu au-dessus, à lire sur la fiche) ; Société Générale 36 773,94 USD, levier 3,51 ; non quanto ; filtrer « Call » (la liste mélange calls et puts) | ISIN et cotation jusqu'à 22h à noter |
| Russell 2000 | oui : Turbo Illimité Best Call Société Générale, onglet Boursomarkets, **prix d'exercice 1 440,56 USD, levier 2,09** (11,81 / 11,82 € le 08/11 ; barrière = prix d'exercice, ≈ 48 % sous l'indice à 2 754) ; parité 100 ; non quanto | ISIN et cotation jusqu'à 22h à noter |
| S&P 500 | oui : Turbos Illimités/Infinis Call Goldman Sachs, onglet Boursomarkets, prix d'exercice 4 563 à 4 603 USD (≈ 25 €), levier affiché 2,90 à 2,94, **levier réel ≈ 2,65** (7 377 / (7 377 − 4 588), vérifié sur le prix du turbo) ; prix d'exercice 38 % sous l'indice, barrière un peu au-dessus, à lire sur la fiche ; non quanto | ISIN et cotation jusqu'à 22h à noter |
| DAX | oui : Turbo Illimité/Infini Call Goldman Sachs, **prix d'exercice 14 724,13 €, levier 2,32** (109,48 / 109,49 € le 08/11 ; ≈ 43 % sous l'indice) | ISIN à noter |
| Euro Stoxx 50 | oui : levier le plus bas trouvé **3,58** : Turbo Illimité/Infini Call Goldman Sachs, prix d'exercice 4 449,08 € (16,90 / 16,91 €) ; perte au stop ≈ 63 € (stop 3,5 %) ; chercher plus bas dans l'onglet « Autres » (frais à vérifier) | ISIN à noter |
| FTSE 100 | oui : Goldman Sachs Best Call 7 626,69 GBP, levier réel ≈ 3,50 (affiché 2,93, faux) ; liste mal triée à cause de l'affichage Goldman : prendre le call au prix d'exercice le plus bas | ISIN à noter |
| FTSE MIB | oui : Société Générale Best Call 36 958,91 €, levier 3,85 (réel ≈ 3,82), parité 1 000, écart achat/vente 0,03 € (≈ 30 points, 0,06 %) | ISIN à noter |
| SMI | oui : Société Générale Best Call 7 798,17 CHF, levier 2,11, parité ≈ 200, non quanto | ISIN à noter |

Levier réel = indice / (indice − prix d'exercice) ; c'est lui qui fixe la perte au stop (500 € × levier réel × distance du stop). Sur les indices américains, Goldman Sachs affiche un levier trop élevé : cours de l'indice en dollars divisé par le prix du turbo en euros (× parité), donc gonflé du cours EUR/USD (≈ 1,11) ; Société Générale affiche le levier réel. Se fier au levier réel.

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
