# ADR 0001 — EWMA par joueur pour les prédictions de score GW

**Status:** Accepted

## Context

Il faut prédire le score Sorare de chaque joueur pour la GW à venir.
Un modèle LightGBM global entraîné sur l'ensemble des joueurs MLB a été testé en premier.

Résultat : le modèle prédisait ~3 pts (médiane MLB) au lieu de ~7.3 pts (moyenne galerie).
Cause : biais de sélection — les joueurs en galerie sont des joueurs de qualité supérieure
à la médiane MLB, et un modèle global ne peut pas capturer cette sélection.

Par ailleurs, ~300 observations par joueur max — trop peu pour un modèle par joueur avec features.

## Decision

Utiliser une EWMA (Exponentially Weighted Moving Average) par joueur,
avec half-life = 25 matchs et sigma empirique calculé sur les 50 derniers matchs.

- `pred_median` = EWMA des scores historiques
- `pred_lo / pred_hi` = bornes IC 80% (1.282 σ), **par match**
- Projection GW dans l'app : `N × pred_median ± 1.282 × σ × √N` (théorème central limite)
- SPs capés à 1 match par GW
- Fallback si < 5 matchs historiques : moyenne de position sur l'ensemble de la galerie

## Consequences

- L'EWMA est optimal quand le signal est faible, le processus non-stationnaire
  (forme, blessures, transferts) et les données peu nombreuses.
- Implémenté dans `ml_predict_gw.py`, résultats dans `data/ml_predictions.parquet`.
- `pred_*` sont des valeurs **par match** — l'app scale par N au moment de l'affichage.
- Ne pas réintroduire un modèle global sauf demande explicite.
