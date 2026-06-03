# ADR 0003 — Streamlit comme frontend du dashboard

**Status:** Accepted

## Context

Dashboard utilisé par une petite équipe (~20 personnes) autour du projet Sorare MLB.
Besoin de visualisations interactives (tableaux, graphiques, filtres) sans développement
frontend dédié. L'équipe est Python-native, pas de ressource frontend disponible.

## Decision

Streamlit : framework Python-natif, déploiement en une commande sur Streamlit Cloud,
intégration directe avec pandas/plotly/altair, pas de HTML/CSS/JS requis.

## Consequences

- Chaque interaction utilisateur déclenche un rerun complet du script →
  gestion fine du `st.session_state` requise pour les widgets avec clés.
- Convention de nommage des clés widgets : `f"{tab}_{index}_{nom}"` pour
  éviter les conflits inter-onglets (bug widget key corrigé).
- Déployé sur Streamlit Cloud (share.streamlit.io) avec parquets commités
  dans le repo — pas de connexion DB cloud, pas de mise à jour en temps réel.
- Multi-utilisateurs limité : Streamlit Cloud gère la concurrence mais
  le cache `@st.cache_data` est partagé entre sessions.

## Pattern filtres — Direction A (2026-06-03)

Les deux panneaux de filtres (`app.py` + `tab1_defis.py`) suivent le "Direction A" pattern :

- **Conteneur** : `st.container(border=True)` — le CSS override `[data-testid="stVerticalBlockBorderWrapper"]`
  donne le rendu dark panel (fond `--bg-1`, bordure `--line`, border-radius 11px).
- **Header** : `st.markdown('<div class="filt-head">...')` — chevron `∧` + titre `.t` + info droite `.r`.
  Les classes `.filt-head .r` et les labels widgets ont le **même style** (10px, monospace, fg-3, uppercase).
- **Widgets** : `st.pills` pour les sélections (remplace `st.segmented_control`), `st.selectbox` pour
  Statistique et Jour de match.
- **Séparateurs** : colonnes-espaceurs étroites (ratio 0.08–0.1) avec `<div class="vsep">` HTML.
- **Clés session_state stables** : `filter_cat`, `filter_fen`, `filter_stat`, `sel_day`, `filter_target`
  — ne pas les changer, plusieurs tabs les lisent.
- **Objectif** : `st.number_input` + bouton ↺ (reset → `st.session_state["filter_target"] = 0`) + bouton ⓘ (disabled, tooltip).

**Règle CSS critique** : le sélecteur global `[data-testid="stButton"] > button` a `text-transform:uppercase`.
Les pills buttons héritent de cette règle → toujours ajouter `text-transform:none!important` sur
`[data-testid="stPills"] button` pour préserver la casse des options (ex: "Classic", "Joués").
