# ADR 0002 — PostgreSQL comme base de données principale

**Status:** Accepted

## Context

Le dashboard agrège des données hétérogènes : scores par match et par stat,
galerie de cartes, prédictions ML, prix de marché, calendriers, météo, park factors.
Il faut un stockage structuré interrogeable par des requêtes complexes
(jointures multi-tables, agrégations par GW, filtres temporels).

## Decision

PostgreSQL via SQLAlchemy + psycopg2, schéma `mlb`, hébergé localement.
Initialisation via `setup_db.py` (exécute `sql/init_mlb_schema.sql` + `sql/init_mlb_tables.sql`).

## Consequences

- Support natif des types Decimal/NUMERIC, BOOLEAN, TIMESTAMPTZ.
- `card_power` retourné comme `Decimal` par SQLAlchemy — toujours caster
  avec `pd.to_numeric()` ou `float()` avant toute opération arithmétique.
- Les parquets sous `data/` servent de cache lecture pour Streamlit
  (évite les requêtes répétées à chaque rerun Streamlit).
- La DB n'est pas accessible depuis Streamlit Cloud — les parquets sont commités dans le repo.

---

## Schéma — mlb

### `mlb.gallery_players`
Galerie des cartes d'un manager. Rechargée intégralement à chaque run via l'API Sorare.

| Colonne | Type | Description |
|---------|------|-------------|
| `id_manager` | TEXT | Identifiant interne du manager |
| `gallery_manager` | TEXT | Slug du manager Sorare |
| `card_slug` | TEXT | Identifiant unique de la carte |
| `card_name` | TEXT | Nom affiché de la carte (ex: "Shohei Ohtani 2022-23") |
| `player_name` | TEXT | Nom du joueur |
| `card_rarity` | TEXT | Rareté brute API (limited, rare, super_rare, unique) |
| `card_display_rarity` | TEXT | Rareté affichée |
| `card_grade` | INTEGER | Grade de la carte (XP) |
| `card_xp` | INTEGER | XP actuel |
| `card_power` | NUMERIC | Multiplicateur de score (1.01–1.20) — retourné en Decimal par SQLAlchemy |
| `card_display_position` | TEXT | Position affichée sur la carte |
| `player_slug` | TEXT | Clé primaire joueur |
| `in_season_eligible` | BOOLEAN | Carte IS (In Season) ou OOS (Classic Season) |
| `competition_slug` | TEXT | Compétition Sorare associée |
| `next_game_date` | TIMESTAMPTZ | Date du prochain match du joueur |
| `active_club_slug` | TEXT | Équipe active du joueur (utilisé pour les filtres AL/NL Arena) |
| `home_away` | TEXT | Domicile ou extérieur pour le prochain match |

---

### `mlb.teams`
Référentiel des 30 équipes MLB. Statique, mis à jour manuellement si besoin.

| Colonne | Type | Description |
|---------|------|-------------|
| `team_slug` | TEXT PK | Identifiant équipe (ex: "los-angeles-dodgers") |
| `team_name` | TEXT | Nom complet |
| `team_code` | TEXT | Abréviation 2-3 lettres (ex: "LAD") |
| `picture_url` | TEXT | URL du logo |

---

### `mlb.players`
Référentiel de tous les joueurs MLB actifs.

| Colonne | Type | Description |
|---------|------|-------------|
| `player_slug` | TEXT PK | Identifiant joueur |
| `display_name` | TEXT | Nom affiché |
| `team_slug` | TEXT FK | Équipe actuelle |
| `bat_hand` | TEXT | Main de frappe : "RIGHT" / "LEFT" / "BOTH" (format long — normaliser avant usage) |
| `position_1/2/3` | TEXT | Positions exactes MLB (SP, RP, C, 1B, 2B, SS, 3B, LF, CF, RF) |
| `agg_position_1/2/3` | TEXT | Positions agrégées Sorare (SP, RP, CI, MI, OF) |
| `avg_score_season` | NUMERIC | Score moyen sur la saison en cours |
| `next_gw_projected_score` | NUMERIC | Score projeté GW suivante (calculé par ml_predict_gw.py) |

---

### `mlb.gameweeks`
Game weeks Sorare, types CLASSIC et DAILY.

| Colonne | Type | Description |
|---------|------|-------------|
| `gw_id` | TEXT PK | ID Sorare de la GW |
| `gw_int` | INTEGER | Numéro entier de la GW (clé de jointure principale) |
| `gw_type` | TEXT | CLASSIC ou DAILY |
| `gw_upcoming` | BOOLEAN | True si c'est la prochaine GW composable |
| `gw_begin_date` | TIMESTAMPTZ | Début de la GW |
| `gw_end_date` | TIMESTAMPTZ | Fin de la GW |

---

### `mlb.game_scores`
Score Sorare global par (joueur, match). Une ligne par joueur par match.

| Colonne | Type | Description |
|---------|------|-------------|
| `player_slug` | TEXT PK | Joueur |
| `game_date` | TIMESTAMPTZ PK | Date du match |
| `category` | TEXT PK | HITTING ou PITCHING (pour two-way players) |
| `gw_int` | INTEGER | GW associée |
| `score` | NUMERIC | Score Sorare total du match |
| `played_in_game` | BOOLEAN | False si le joueur n'a pas joué (score = 0, pas de stats) |

---

### `mlb.game_score_details`
Détail des stats individuelles par (joueur, match, stat). Uniquement les matchs joués.

| Colonne | Type | Description |
|---------|------|-------------|
| `player_slug` | TEXT PK | Joueur |
| `game_date` | TIMESTAMPTZ PK | Date du match |
| `stat` | TEXT PK | Nom de la stat (ex: "single", "home_run", "strikeout_as_pitcher") |
| `stat_short_name` | TEXT | Nom court affiché dans le dashboard |
| `category` | TEXT PK | HITTING ou PITCHING |
| `stat_value` | NUMERIC | Valeur brute de la stat |
| `points` | NUMERIC | Points Sorare attribués pour cette stat |

---

### `mlb.games`
Résumé de match (1 ligne par match MLB).

| Colonne | Type | Description |
|---------|------|-------------|
| `game_id` | TEXT PK | UUID du match (extrait de "Game:uuid" Sorare) |
| `game_date` | TIMESTAMPTZ | Date et heure du match |
| `gw_int` | INTEGER | GW associée |
| `home_team_slug` | TEXT FK | Équipe à domicile |
| `away_team_slug` | TEXT FK | Équipe visiteuse |
| `home_probable_pitcher` | TEXT | player_slug du SP prévu domicile (peut être NULL) |
| `away_probable_pitcher` | TEXT | player_slug du SP prévu visiteur (peut être NULL) |
| `winning_pitcher` | TEXT | player_slug du pitcher gagnant (fallback si probable_pitcher NULL) |
| `losing_pitcher` | TEXT | player_slug du pitcher perdant |
| `winner_slug` | TEXT | team_slug de l'équipe gagnante |
| `status` | TEXT | Statut du match (scheduled, final, etc.) |

---

### `mlb.game_innings`
Score par manche (1 ligne par manche par match).

| Colonne | Type | Description |
|---------|------|-------------|
| `game_id` | TEXT PK FK | Match |
| `inning_number` | INTEGER PK | Numéro de manche |
| `home_score` | INTEGER | Points marqués par l'équipe domicile dans cette manche |
| `away_score` | INTEGER | Points marqués par l'équipe visiteuse dans cette manche |

---

### `mlb.player_injuries`
Snapshot des blessures actives (1 ligne par joueur blessé, rechargé à chaque run).

| Colonne | Type | Description |
|---------|------|-------------|
| `player_slug` | TEXT PK | Joueur |
| `active` | BOOLEAN | Blessure encore active |
| `kind` | TEXT | Type de blessure |
| `status` | TEXT | Statut (day-to-day, IL10, IL60…) |
| `expected_end_date` | DATE | Date de retour estimée |

---

### `mlb.card_prices`
Prix de marché par (joueur, rareté, inSeason). Rechargé à chaque run.

| Colonne | Type | Description |
|---------|------|-------------|
| `player_slug` | TEXT PK | Joueur |
| `rarity` | TEXT PK | limited / rare / super_rare / unique |
| `in_season` | BOOLEAN PK | Carte IS ou OOS |
| `price_eur` | NUMERIC | Prix en euros (taux de change figé dans fetch_prices.py) |
| `sealable_for` | INTEGER | Valeur de scellement en crédits Sorare |

---

### `mlb.card_purchase_prices`
Prix d'achat des cartes par le manager (issu de l'historique des trades Sorare).

| Colonne | Type | Description |
|---------|------|-------------|
| `card_slug` | TEXT | Carte achetée |
| `manager_slug` | TEXT | Manager acheteur |
| `deal_id` | TEXT | Identifiant de la transaction |
| `deal_type` | TEXT | Type de transaction (direct_offer, auction…) |
| `transaction_date` | TIMESTAMPTZ | Date de l'achat |
| `price_eur_cents` | INTEGER | Prix d'achat en centimes d'euros (avant remise crédits) |

---

### `mlb.stadiums`
Caractéristiques physiques des 30 stades MLB. Statique, mis à jour ~1x/an.

| Colonne | Type | Description |
|---------|------|-------------|
| `team_slug` | TEXT PK | Équipe résidente |
| `stadium_name` | TEXT | Nom du stade |
| `altitude_ft` | INTEGER | Altitude (impact sur la distance des home runs) |
| `is_dome` | BOOLEAN | Stade couvert |
| `roof_type` | TEXT | open / retractable / fixed_dome |
| `surface` | TEXT | grass / turf |
| `lf/cf/rf_dist_ft` | INTEGER | Distance des murs (LF, CF, RF) en pieds |
| `cf_orientation_deg` | INTEGER | Orientation home→CF en degrés (pour calcul vent) |

---

### `mlb.park_factors`
Facteurs de terrain par (équipe, saison, stat). Source : pybaseball.

| Colonne | Type | Description |
|---------|------|-------------|
| `team_slug` | TEXT PK | Équipe |
| `season` | INTEGER PK | Saison MLB |
| `stat` | TEXT PK | HR / H / R / BB / K / 2B / 3B |
| `factor_overall` | NUMERIC | 100 = neutre, 110 = +10% favorise les offensives |
| `factor_L` | NUMERIC | Facteur pour les frappeurs gauchers |
| `factor_R` | NUMERIC | Facteur pour les frappeurs droitiers |

---

### `mlb.game_weather`
Météo par match. Source : Open-Meteo (gratuit).

| Colonne | Type | Description |
|---------|------|-------------|
| `game_id` | TEXT PK | Match (pas de FK pour permettre le pré-fetch) |
| `temperature_f` | NUMERIC | Température en Fahrenheit |
| `wind_speed_mph` | NUMERIC | Vitesse du vent en mph |
| `wind_dir_deg` | INTEGER | Direction d'où vient le vent (0=N, 90=E) |
| `wind_label` | TEXT | out / in / cross_L / cross_R / dome / calm |
| `condition` | TEXT | clear / cloudy / rain / dome |
| `is_forecast` | BOOLEAN | True si météo prévisionnelle (avant le match) |

---

### `mlb.pitcher_season_stats`
Stats saison des lanceurs (ERA+, FIP, etc.). Source : pybaseball via `fetch_pitcher_season_stats.py`.
Une ligne par (joueur, saison).

---

### `mlb.pitcher_game_pitches`
Nombre de lancers par match sur les 30 derniers jours. Source : MLB Stats API via `fetch_pitch_counts.py`.

| Colonne | Type | Description |
|---------|------|-------------|
| `player_slug` | TEXT PK | Lanceur |
| `game_date` | TIMESTAMPTZ PK | Date du match |
| `pitches` | INTEGER | Nombre total de lancers |
| `strikes` | INTEGER | Lancers strikes |
| `batters_faced` | INTEGER | Frappeurs affrontés |
| `innings_pitched_outs` | INTEGER | Retraits effectués |

---

### `mlb.data_freshness`
Table centralisée de suivi de la fraîcheur des données. Un enregistrement par table source,
mis à jour par `update_data.py` après chaque étape d'alimentation. Remplace les colonnes
`updated_at` individuelles comme source de vérité pour la sidebar.

| Colonne | Type | Description |
|---------|------|-------------|
| `table_name` | TEXT PK | Nom de la table source (ex: `game_scores`, `card_prices`) |
| `freshness_date` | TIMESTAMPTZ | Date métier pertinente : `NOW()` pour les snapshots, `MAX(game_date)` pour les scores, `MIN(next_game_date)` pour `gallery_stats_agg` |
| `refreshed_at` | TIMESTAMPTZ | Horodatage du run `update_data.py` qui a écrit cet enregistrement |

Tables trackées : `players`, `player_injuries`, `gallery_players`, `games`, `game_weather`,
`game_scores`, `game_score_details`, `gallery_stats_agg`, `card_prices`,
`pitcher_season_stats`, `pitcher_game_pitches`.
