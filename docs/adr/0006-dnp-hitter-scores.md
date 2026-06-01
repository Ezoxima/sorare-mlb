# ADR 0006 — Inclusion des matchs non-joués (DNP) dans l'EWMA hitter

**Status:** Accepted  
**Date:** 2026-06-01

## Context

L'EWMA des hitters était calculée uniquement sur `played_in_game = true`.
Cela surestimait systématiquement les joueurs qui jouent peu (backup catchers, platoon players)
car seules leurs bonnes performances (quand ils jouent) entraient dans la moyenne.

Exemple : un backup catcher qui joue 3% des matchs avait une EWMA de 2.07 pts.
Sa vraie espérance de score par match d'équipe est ~0.06 pts (il ne jouera probablement pas).

`mlb.game_scores` contient des lignes `played_in_game = false` pour les matchs où le joueur
était dans l'effectif mais n'a pas joué. Ces lignes ont `score = 0` (confirmé en base).

## Decision

Inclure les matchs non-joués (DNP) dans l'EWMA **pour les hitters uniquement** :

1. La requête `scores` retire `AND played_in_game = true` pour les hitters, l'ajoute via le filtre catégorie
2. Les lignes DNP (`played_in_game = false, category = 'HITTING'`) sont conservées avec `score = 0`
3. Déduplication par `(player_slug, game_date)` avec priorité au rang `played_in_game = true` (via sort + drop_duplicates)
4. Re-tri chronologique **obligatoire** après la déduplication — l'EWMA étant sensible à l'ordre

**Pitchers (SP/RP)** : inchangé, `played_in_game = true AND category = 'PITCHING'` uniquement.
Un SP non-lanceur ce jour-là ne renseigne pas sur sa prochaine performance.

**Hitter splits** (facteur platoon) : inchangé, `played_in_game = true` uniquement.
Les DNP n'ont pas d'adversaire → inutiles pour les splits L/R.

## Consequences

- Les backup players ont une EWMA proche de 0, reflétant leur vraie espérance GW
- Les titulaires réguliers (7% DNP) voient une baisse marginale (~2%)
- La prédiction tient compte du temps de jeu effectif, pas uniquement de la qualité quand le joueur joue
- Relancer `python ml_predict_gw.py` pour régénérer `data/ml_predictions.parquet` après ce changement
