# CONTEXT.md — Sorare MLB Dashboard

## What this project is

A personal Streamlit dashboard for managing a Sorare MLB card portfolio. It connects to
a PostgreSQL database populated from the Sorare GraphQL API and MLB game data, and helps
the user pick the best team lineup for each gameweek competition.

## Domain vocabulary

**GW (Gameweek)** — A competition period in Sorare MLB, identified by an integer (`gw_int`).
Each GW maps to a set of real MLB games. The "next GW" is the upcoming fixture the user
is building a lineup for.

**Score / Score Sorare** — A per-game numerical score assigned to each player by Sorare,
stored in `mlb.game_scores.score`. This is the primary metric for all predictions and rankings.

**Card** — A Sorare digital collectible representing a real player. Each card has a rarity
and a `card_power` (between 1.01 and 1.20) that multiplies the player's score.

**Card power** — Multiplicative bonus on the player score. Always stored as `Decimal` in
PostgreSQL (via SQLAlchemy) — always convert with `pd.to_numeric()` or `float()` before arithmetic.

**Rarity** — Card tier: Limited, Rare, Super Rare, Unique (ascending value). Affects
eligibility for certain competitions.

**IS (In Season)** — "In Season" cards: cards from the current season, eligible for
Champions and Hot Streak competitions. Champions and Hot Streak require ≥ 6 IS cards out of 7.

**OOS / Classic Season** — Out-of-season cards. Allowed as the 7th slot in Champions/Hot Streak.
No restriction in Challenger.

**Score effectif (proj_score_eff)** — The effective projected score for a card: `proj_score × card_power`.
This is the metric the lineup suggestion algorithm maximises.

**Galerie (gallery)** — The user's card collection. Stored in `mlb.gallery_players`.
Only gallery cards are eligible for lineup building.

**Défi journalier (daily challenge)** — Tab 1 of the dashboard. Shows gallery players
who play on the selected day, ranked by their average on a chosen stat over a configurable
time window (5/10/20 games). The user selects a stat, a window, and an optional target
threshold to identify which players are "hot" on that indicator on a given game day.
Clicking a player opens a historical chart of their stat over time.

**Fenêtre (window)** — The number of recent games used to compute a player's stat average.
Options: 5, 10, or 20 games. Defined in `FENETRE_OPTIONS`.

**Lineup** — A team of 7 cards submitted to a competition. Saved in the app and compared
against ML suggestions.

**Arena** — An alternative competition format with 5 or 7 slots and different club-count
and card-eligibility constraints. 9 arena types are defined (see below).

**Platoon** — Whether a hitter's handedness (L/R/S) vs. the opposing pitcher's hand gives an advantage.
Three options are implemented: A (personal splits), B (league average), C (hybrid A+B).

**SP / RP / CI / MI / OF / Hitter / Libre** — Lineup slot types:
- SP: Starting Pitcher
- RP: Relief Pitcher
- CI: Corner Infield (1B or 3B)
- MI: Middle Infield (2B, SS, or C — Catcher is included in this slot)
- OF: Outfield
- Hitter: any of CI / MI / OF
- Libre: any of CI / MI / OF (in Arena context — not a true "any position" slot)

**slug** — URL-safe identifier for a player (`player_slug`) or team (`team_slug`). Primary key
throughout the database. Never use display names as keys.

**bat_hand** — Stored in `mlb.players.bat_hand` as long-form strings: `"RIGHT"`, `"LEFT"`, `"BOTH"`.
Always normalise to single-char before comparisons: `[:1]` then replace `"B"` → `"S"` (switch hitter).

## Key entities

| Entity | Table | Primary key |
|--------|-------|-------------|
| Player | `mlb.players` | `player_slug` |
| Team | `mlb.teams` | `team_slug` |
| Game | `mlb.games` | `game_id` |
| Gameweek | `mlb.gameweeks` | `gw_int` |
| Score per game | `mlb.game_scores` | `(player_slug, game_date, category)` |
| Score detail | `mlb.game_score_details` | `(player_slug, game_date, stat, category)` |
| Gallery card | `mlb.gallery_players` | `(player_slug, id_manager)` |
| Card purchase price | `mlb.card_purchase_prices` | — |
| Data freshness | `mlb.data_freshness` | `table_name` |

## Arena types

All arenas use max 6 cards per club (4 for Sandlot formats).

| Arena | Slots | Card filter |
|-------|-------|-------------|
| Standard | SP + RP + CI + MI + OF + Hitter + Libre, max 6/club | none |
| Beginner | same as Standard | none |
| Elite | same as Standard | none |
| American (AL) | same as Standard | only AL team cards (`active_club_slug` in AL set) |
| National (NL) | same as Standard | only NL team cards (`active_club_slug` in NL set) |
| OG (2022) | same as Standard | `card_name` contains "2022-23" |
| Legacy (2023-24) | same as Standard | `card_name` contains "2023-24" or "2024-25" |
| Sandlot 2SP+3H | SP1 + SP2 + H1 + H2 + H3, max 4/club | none |
| Sandlot 5H | H1 + H2 + H3 + H4 + H5, max 4/club | none |

## Prediction model

EWMA (Exponentially Weighted Moving Average) per player, implemented in `ml_predict_gw.py`.

- `pred_median` = EWMA of historical scores (half-life = 25 games)
- `pred_lo / pred_hi` = 80% CI bounds (1.282 σ), **per game**
- GW projection in the app: `N × pred_median ± 1.282 × σ × √N` where N = team's games in the GW
- SPs are capped at 1 game per GW
- Fallback for < 5 historical games: position-average across the gallery

A global LightGBM model was tried and abandoned — it predicted the MLB median (~3 pts) rather
than the gallery average (~7.3 pts) due to selection bias. EWMA is the validated approach.
Do not suggest re-introducing a global ML model unless the user asks.

## Business rules

- Max 6 cards from the same club per lineup (4 for 5-player Sandlot arenas)
- Champions / Hot Streak: ≥ 6 IS cards mandatory, 1 OOS slot allowed
- Challenger: no IS constraint
- Lineup suggestion algorithm maximises `proj_score_eff`, then forces IS constraint if needed

## Non-obvious constraints

- `card_power` comes from PostgreSQL as `Decimal` — always cast before arithmetic
- `bat_hand` in DB is long-form ("RIGHT"/"LEFT"/"BOTH") — normalise before any platoon logic
- `probable_pitcher` can be NULL for historical games — fall back to `winning_pitcher` / `losing_pitcher`
- Sorare's marketplace credit discount cannot be retrieved via API (confirmed with Sorare support)
- `ml_predictions.parquet` stores `pred_*` values per game, not per GW — the app scales by N
- Arena "Libre" slot accepts only hitter positions (CI/MI/OF), not pitchers
- **Arena competitions do NOT apply card_power (XP bonus)** — `proj_score_eff` in Arena equals `proj_score` (no multiplication). This is intentional per Sorare Arena rules. Only Compétitions (Champions/Hot Streak/Challenger) use card_power.

## Game-day window

MLB games start in US afternoons/evenings (18:00–22:30 ET), which is Paris time **00:00–04:30 the next day**.
The app defines a "game day" as a sliding window: **16:00 Paris → 08:00 Paris next day**.

This window must be used consistently everywhere:
- `load_today_games()` in `data_loaders.py`
- `_load_pp_today()` in `data_loaders.py`
- `_df_pp_today` filter in `app.py`

**Never** filter by raw `game_date.dt.date == today_paris` — UTC date ≠ Paris date for night games.

## Two-way players (e.g. Ohtani)

Ohtani (`shohei-ohtani-19940705`) has `agg_position_1 = 'CI'` (hitter role).
`mlb.game_scores` contains **two rows per game** for him: one `HITTING` and one `PITCHING`.

When computing his EWMA in `ml_predict_gw.py`, always filter `category = 'HITTING'`
(handled by the category filter added 2026-06-01). Without this filter, pitching rows (avg ~2 pts)
dilute the hitting EWMA (~11 pts), cutting predictions by ~40%.

## Lineup deduplication rules (Arena)

- **Intra-lineup**: same `player_slug` forbidden twice (regardless of card) — enforced in `_fill_is`
- **Inter-lineups**: same `card_name` forbidden across teams — player with IS + Classic cards can play in two different Arena teams

## IS / Classic card detection

A player with both IS and Classic cards of the same rarity:
- `_is_map` in `app.py` uses `.groupby("player_slug")["in_season_eligible"].any()` → `True` if any IS card exists
- Tab1 expansion (`_card_info_map`) stores `in_season_eligible` **per card** — each expanded row shows the correct IS/CLASSIC tag
- `calendar.parquet` `DISTINCT ON (player_slug, id_manager, card_display_rarity)` keeps only one card per rarity — do not rely on it for IS/Classic status

## Fraîcheur des données (data_freshness)

`mlb.data_freshness` centralise la date de dernière mise à jour de chaque table source.
Peuplée par `update_data.py` après chaque étape, exportée en `data/data_freshness.parquet`.

La sidebar affiche 6 groupes en lisant `load_data_freshness()` (retourne un `dict[table_name, Timestamp]`) :

| Groupe sidebar | Tables trackées | Date affichée |
|---|---|---|
| Prix joueurs | `card_prices` | `freshness_date` |
| Infos joueurs | `players`, `player_injuries` | min des deux |
| Galerie | `gallery_players` | `freshness_date` |
| Matchs | `games`, `pitcher_game_pitches`, `pitcher_season_stats` | min des trois |
| Météo | `game_weather` | `freshness_date` |
| Scores | `game_scores`, `game_score_details` | min des deux |

`freshness_date` est `NOW()` pour les snapshots, `MAX(game_date)` pour les scores,
`MIN(next_game_date)` pour `gallery_stats_agg`.

## Hitter prediction and DNP games

EWMA for hitters includes non-played games (DNP) with `score = 0`. This correctly reflects
the probability that a bench player doesn't play. Backup catchers or platoon players who sit out
frequently will have low predicted scores even if their per-game average is high.

Pitchers: DNP rows excluded — an SP not pitching on a given day carries no information about
their next start quality.
