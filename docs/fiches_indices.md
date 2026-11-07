# Fiches pratiques par indice (swing, 07/11/2026)

Document opérationnel, compatible avec le moratoire : aucune règle n'est testée ni modifiée.
Les chiffres se reproduisent avec `python3 scripts/fiches_indices.py` (cache du 06/11 au soir) :
l'ATR et donc le stop, l'exposition et l'ordre changent chaque jour ; le contrôle avant
clôture (`swing_preclose.py`) donne les valeurs du jour au moment du signal.

## Tableau au 06/11/2026

| Indice | Tendance | Stop de la règle (2,5 ATR) | Exposition pour 25 € | Ordre conseillé | Levier | Trades/an (historique) | R/trade (historique, descriptif) |
|---|---|---|---|---|---|---|---|
| CAC 40 | **sous SMA200** | 257 pts (3,2 %) | 793 € | 500 € | 1,6 | 7,5 | +0,017 |
| DAX | au-dessus | 932 pts (3,6 %) | 693 € | 500 € | 1,4 | 7,0 | +0,042 |
| Euro Stoxx 50 | au-dessus | 214 pts (3,5 %) | 721 € | 500 € | 1,4 | 7,0 | +0,013 |
| S&P 500 | au-dessus | 252 pts (3,4 %) | 732 € | 500 € | 1,5 | 8,2 | +0,091 |
| Nasdaq 100 | **sous SMA200** | 1 577 pts (5,8 %) | 428 € | 500 € | ~1 (0,86 calculé) | 8,4 | +0,102 |
| FTSE 100 | au-dessus | 314 pts (2,9 %) | 849 € | 500 € | 1,7 | 6,9 | +0,048 |
| SMI | au-dessus | 432 pts (2,9 %) | 857 € | 500 € | 1,7 | 7,1 | +0,041 |
| Dow Jones | au-dessus | 1 767 pts (3,4 %) | 726 € | 500 € | 1,5 | 9,7 | +0,077 |
| Russell 2000 | **sous SMA200** | 111 pts (4,0 %) | 621 € | 500 € | 1,2 | 7,1 | +0,120 |
| FTSE MIB | au-dessus | 2 001 pts (4,0 %) | 625 € | 500 € | 1,3 | 6,7 | +0,068 |

Ordre ≈ 500 € (un peu plus au maximum, précision du 07/11) : ordre = max(500 €, exposition / 2,85), levier = exposition / ordre. Le montant engagé n'est pas la perte : perte au stop = ordre × levier × distance du stop ≈ 25 €. Quand l'exposition est sous 500 € (Nasdaq aujourd'hui,
stop de 5,8 %), l'ordre reste à 500 € et le risque réel dépasse 25 € (environ 29 € au levier 1 ;
**davantage si aucun turbo de levier proche de 1 n'existe** : au levier 1,5, l'exposition serait
de 750 € et le risque d'environ 44 €). Dans ce cas, prendre le turbo au levier le plus bas
disponible et noter le risque réel au journal.

## Ce qu'il faut chercher chez Boursorama (une fois, avant le premier signal)

Pour chaque indice : un **turbo infini call** (« Turbo Infini », « Open End », « BEST »…)
sur l'indice lui-même, coté sur la plateforme, avec :
- un **levier égal à exposition / 500 €** (le tableau : 1,2 à 1,7 aujourd'hui ; jamais plus de 2,85, soit une barrière à au moins 35 % sous le cours). Un levier plus élevé avec 500 € engagés augmente la perte au stop (levier 3,5 : ≈ 56 € au lieu de 25 €) ;
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
