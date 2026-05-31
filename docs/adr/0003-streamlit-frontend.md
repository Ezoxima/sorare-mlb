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
