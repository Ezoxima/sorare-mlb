# ADR 0004 — Parquets locaux comme couche de cache entre PostgreSQL et Streamlit

**Status:** Accepted

## Context

Streamlit rerun à chaque interaction utilisateur. Les requêtes PostgreSQL
(scores, galerie, prédictions) sont trop lentes pour être exécutées à chaque rerun.
Par ailleurs, Streamlit Cloud n'a pas accès à la base de données locale.

## Decision

Les données sont pré-calculées par `update_data.py` et stockées sous `data/*.parquet`.
Streamlit lit uniquement les parquets via `@st.cache_data`. Les parquets sont commités
dans le repo git pour permettre le déploiement sur Streamlit Cloud.

| Fichier | Contenu |
|---------|---------|
| `data/ml_predictions.parquet` | Prédictions EWMA pour tous les joueurs de la GW (pred_median/lo/hi par match, colonnes platoon) |
| `data/card_prices.parquet` | Galerie + prix de marché + card_power |
| `data/calendar.parquet` | Calendrier des joueurs de la galerie |

## Consequences

- Cache statique : les données affichées sont celles du dernier `update_data.py`.
  L'app ne reflète pas les changements DB en temps réel.
- `ml_predictions.parquet` stocke `pred_*` par match — l'app multiplie par N
  au moment de l'affichage (ne pas stocker la projection GW directement).
- En cas de désync Streamlit Cloud (app qui affiche de vieilles données) :
  vérifier les logs sur share.streamlit.io, sinon recréer l'app.
