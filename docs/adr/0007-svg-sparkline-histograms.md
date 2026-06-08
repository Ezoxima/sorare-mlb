# ADR 0007 — Mini histogrammes SVG inline pour l'historique des scores

**Status:** Accepted  
**Date:** 2026-06-08

## Context

Les onglets Équipe (tab6) et Mes Lineups (tab8) affichent des cartes joueur avec image.
L'utilisateur veut voir les 5 derniers scores sous chaque carte, avec un code couleur
par seuil (rouge < 2 pts → blanc > 45 pts), incluant les matchs non-joués (DNP).

Options envisagées :
- **Plotly/Altair mini chart** : overhead de rendu, pas de contrôle précis de la taille
  dans une cellule HTML compacte, nécessite un composant Streamlit séparé du `<img>`.
- **SVG inline via `st.markdown`** : taille exacte, rendu immédiat, colocalisé avec l'image
  dans le même bloc HTML, zero dépendance supplémentaire.

## Decision

Utiliser des SVG générés côté Python et injectés via `st.markdown(unsafe_allow_html=True)`.

Implémentation dans `data_loaders.py` :
- `_score_bar_color(v: float) -> str` : mappe une valeur à une couleur RGB selon les seuils.
- `gen_bar_sparkline_svg(scores, w, h, score_colors=False)` : génère le SVG.
  - `scores` est une `list` de `float | None` — `None` = DNP.
  - DNP → barre grise `rgb(100,116,139)` de hauteur `h//4`.
  - `mx` calculé sur les valeurs non-None uniquement (pas de division par zéro sur DNP-only).
  - `score_colors=True` active le dégradé par seuil ; `False` → couleur unique (`#38bdf8`).
- `load_last5_scores(slugs: tuple) -> dict` : lit `game_scores.parquet`, retourne les 5 dernières
  lignes par joueur **sans** filtre `played_in_game` (DNP inclus en tant que `None`).

Le bloc HTML final encapsule `<img>` + sparkline SVG + nom dans un `<div>` centré.

## Consequences

- Aucune dépendance supplémentaire (pas de plotly, pas d'altair).
- Le SVG est régénéré à chaque render Streamlit — coût négligeable (~µs par carte).
- `load_last5_scores` effectue une lecture parquet unique pour tous les slugs du tab,
  pas une requête par joueur.
- DNP clairement distingué de "score 0" grâce au sentinel `None`.
- **Ne pas filtrer `played_in_game`** dans `load_last5_scores` — c'est intentionnel.
  Filtrer produirait des barres manquantes au lieu de barres grises pour les jours DNP.
