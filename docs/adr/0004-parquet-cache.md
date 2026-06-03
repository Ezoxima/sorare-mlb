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

| Fichier | Contenu | Loader |
|---------|---------|--------|
| `data/gallery_stats.parquet` | Galerie + stats agrégées par (joueur, fenêtre, stat) — source principale Tab 1 | `load_data()` |
| `data/calendar.parquet` | Calendrier joueurs galerie (prochain match, matchup, % joués) | `load_calendar()` |
| `data/card_prices.parquet` | Galerie + prix marché IS/OOS + card_power + position | `load_card_prices()` |
| `data/all_players_market.parquet` | Prix marché tous joueurs (onglet Marché) | `load_all_players_market()` |
| `data/game_scores.parquet` | Scores galerie (30 derniers matchs, category HITTING/PITCHING) | — |
| `data/game_score_details.parquet` | Détail stats galerie (30 derniers matchs joués) | — |
| `data/game_score_details_db.parquet` | Détail stats tous joueurs (onglet Base de données, 20 matchs) | — |
| `data/games.parquet` | Résumé matchs MLB (date, équipes, SP prévus) | `load_today_games()` |
| `data/players.parquet` | Référentiel joueurs (slug, nom, équipe, position) | — |
| `data/players_seen.parquet` | Tous joueurs vus dans les matchs fetchés (noms + position) | — |
| `data/teams.parquet` | Référentiel équipes (slug, code, logo URL) | `load_team_codes()` / `load_team_logos()` |
| `data/injuries.parquet` | Joueurs blessés actifs (player_slug uniquement) | `load_injured_players()` |
| `data/ml_predictions.parquet` | Prédictions EWMA (pred_median/lo/hi par match, platoon A/B/C, facteurs contextuels) | `load_ml_predictions()` |
| `data/leaderboard_rewards.parquet` | Seuils de récompenses GW par compétition (Arena) | `load_leaderboard_rewards()` |
| `data/pitcher_pitches.parquet` | Nombre de lancers par match sur 30 jours (fetch_pitch_counts.py) | — |
| `data/data_freshness.parquet` | Fraîcheur des données par table source (pour sidebar) | `load_data_freshness()` |

## Consequences

- Cache statique : les données affichées sont celles du dernier `update_data.py`.
  L'app ne reflète pas les changements DB en temps réel.
- `ml_predictions.parquet` stocke `pred_*` **par match** — l'app multiplie par N
  au moment de l'affichage (ne pas stocker la projection GW directement).
- `data_freshness.parquet` est exporté deux fois par run complet : à l'étape 11 (export
  global) puis ré-exporté à la fin de l'étape 12 (pitcher stats) pour inclure les upserts
  tardifs sans relancer tout l'export.
- En cas de désync Streamlit Cloud (app qui affiche de vieilles données) :
  vérifier les logs sur share.streamlit.io, sinon recréer l'app.
