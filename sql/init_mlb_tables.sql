-- ============================================================
-- Tables MLB — hors gallery_players (déjà créée dans init_mlb_schema.sql)
-- ============================================================

-- ------------------------------------------------------------
-- Référentiel équipes
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.teams CASCADE;
CREATE TABLE mlb.teams (
    team_slug   TEXT PRIMARY KEY,
    team_name   TEXT
);

-- ------------------------------------------------------------
-- Référentiel joueurs
-- Positions stockées en colonnes (max 3) : exact (SP, RP, C…)
-- et agrégée (SP, RP, MI, CI, OF) issue du mapping poste_mlb.json
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.players CASCADE;
CREATE TABLE mlb.players (
    player_slug         TEXT PRIMARY KEY,
    display_name        TEXT,
    age                 INTEGER,
    team_slug           TEXT REFERENCES mlb.teams(team_slug),
    country             TEXT,
    bat_hand            TEXT,
    shirt_number        INTEGER,
    appearances         INTEGER,
    season_appearances  INTEGER,
    avg_score_season    NUMERIC,
    position_1          TEXT,
    position_2          TEXT,
    position_3          TEXT,
    agg_position_1      TEXT,
    agg_position_2      TEXT,
    agg_position_3      TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mlb_players_team ON mlb.players(team_slug);

-- ------------------------------------------------------------
-- Blessures — snapshot du dernier run (1 ligne par joueur blessé)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.player_injuries CASCADE;
CREATE TABLE mlb.player_injuries (
    player_slug         TEXT PRIMARY KEY,
    active              BOOLEAN,
    kind                TEXT,
    details             TEXT,
    status              TEXT,
    expected_end_date   DATE,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ------------------------------------------------------------
-- Game weeks CLASSIC et DAILY
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.gameweeks CASCADE;
CREATE TABLE mlb.gameweeks (
    gw_id           TEXT PRIMARY KEY,
    gw_int          INTEGER,
    gw_slug         TEXT,
    gw_type         TEXT,       -- CLASSIC | DAILY
    gw_upcoming     BOOLEAN,
    gw_begin_date   TIMESTAMPTZ,
    gw_end_date     TIMESTAMPTZ
);

CREATE INDEX idx_mlb_gw_int ON mlb.gameweeks(gw_int);

-- ------------------------------------------------------------
-- Score global par (joueur, match)
-- played_in_game = false → le joueur n'a pas joué (pas de stats)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.game_scores CASCADE;
CREATE TABLE mlb.game_scores (
    player_slug     TEXT,
    game_date       TIMESTAMPTZ,
    gw_int          INTEGER,
    position        TEXT,
    score           NUMERIC,
    played_in_game  BOOLEAN,
    PRIMARY KEY (player_slug, game_date)
);

CREATE INDEX idx_mlb_game_scores_slug_date ON mlb.game_scores(player_slug, game_date DESC);
CREATE INDEX idx_mlb_game_scores_gw        ON mlb.game_scores(gw_int);

-- ------------------------------------------------------------
-- Détail des scores par (joueur, match, stat)
-- Uniquement les matchs joués (played_in_game = true)
-- Équivalent de dwh_sorare_v2.score_players_details_v2 pour le foot
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.game_score_details CASCADE;
CREATE TABLE mlb.game_score_details (
    player_slug     TEXT,
    game_date       TIMESTAMPTZ,
    stat            TEXT,
    stat_short_name TEXT,
    category        TEXT,
    stat_value      NUMERIC,
    points          NUMERIC,
    PRIMARY KEY (player_slug, game_date, stat)
);

CREATE INDEX idx_mlb_gsd_slug_date ON mlb.game_score_details(player_slug, game_date DESC);
CREATE INDEX idx_mlb_gsd_stat      ON mlb.game_score_details(stat);

-- ------------------------------------------------------------
-- Prix de marché par (joueur, rareté, inSeason)
-- Rechargé à chaque run — taux de change figés dans le script
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.card_prices CASCADE;
CREATE TABLE mlb.card_prices (
    player_slug     TEXT,
    rarity          TEXT,       -- limited | rare | super_rare | unique
    in_season       BOOLEAN,
    price_eur       NUMERIC,
    sealable_for    INTEGER,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (player_slug, rarity, in_season)
);

CREATE INDEX idx_mlb_card_prices_slug ON mlb.card_prices(player_slug);
