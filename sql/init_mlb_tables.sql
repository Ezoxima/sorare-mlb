-- ============================================================
-- Tables MLB — hors gallery_players (déjà créée dans init_mlb_schema.sql)
-- ============================================================

-- ------------------------------------------------------------
-- Référentiel équipes
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.teams CASCADE;
CREATE TABLE mlb.teams (
    team_slug   TEXT PRIMARY KEY,
    team_name   TEXT,
    team_code   TEXT,
    picture_url TEXT
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
    avg_score_season            NUMERIC,
    next_gw_projected_score     NUMERIC,
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
    player_slug     TEXT        NOT NULL,
    game_date       TIMESTAMPTZ NOT NULL,
    gw_int          INTEGER,
    category        TEXT        NOT NULL DEFAULT 'HITTING',
    score           NUMERIC,
    played_in_game  BOOLEAN,
    PRIMARY KEY (player_slug, game_date, category)
);

CREATE INDEX idx_mlb_game_scores_slug_date ON mlb.game_scores(player_slug, game_date DESC);
CREATE INDEX idx_mlb_game_scores_gw        ON mlb.game_scores(gw_int);

-- ------------------------------------------------------------
-- Détail des scores par (joueur, match, stat, category)
-- Uniquement les matchs joués (played_in_game = true)
-- category dans la PK pour gérer les two-way players (même stat en pitching et hitting)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.game_score_details CASCADE;
CREATE TABLE mlb.game_score_details (
    player_slug     TEXT        NOT NULL,
    game_date       TIMESTAMPTZ NOT NULL,
    stat            TEXT        NOT NULL,
    stat_short_name TEXT,
    category        TEXT        NOT NULL DEFAULT 'UNKNOWN',
    stat_value      NUMERIC,
    points          NUMERIC,
    PRIMARY KEY (player_slug, game_date, stat, category)
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

-- ------------------------------------------------------------
-- Stades MLB (statique, ~30 lignes, mis à jour ~1x/an)
-- Créé/peuplé par init_stadiums.py (upsert, ne pas DROP ici)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.stadiums CASCADE;
CREATE TABLE mlb.stadiums (
    team_slug           TEXT PRIMARY KEY,
    venue               TEXT,
    stadium_name        TEXT,
    city                TEXT,
    state               TEXT,
    latitude            NUMERIC,
    longitude           NUMERIC,
    altitude_ft         INTEGER,
    is_dome             BOOLEAN DEFAULT false,
    roof_type           TEXT,       -- 'open' | 'retractable' | 'fixed_dome'
    surface             TEXT,       -- 'grass' | 'turf'
    lf_dist_ft          INTEGER,
    cf_dist_ft          INTEGER,
    rf_dist_ft          INTEGER,
    lf_wall_ft          NUMERIC,
    rf_wall_ft          NUMERIC,
    capacity            INTEGER,
    cf_orientation_deg  INTEGER     -- direction home->CF en degrés (pour calcul vent)
);

-- ------------------------------------------------------------
-- Park factors par (équipe, saison, stat)
-- Peuplé par fetch_park_factors.py via pybaseball
-- 100 = neutre, 110 = +10%, 90 = -10%
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.park_factors CASCADE;
CREATE TABLE mlb.park_factors (
    team_slug       TEXT        NOT NULL,
    season          INTEGER     NOT NULL,
    stat            TEXT        NOT NULL,   -- 'HR' | 'H' | 'R' | 'BB' | 'K' | '2B' | '3B'
    factor_overall  NUMERIC,
    factor_L        NUMERIC,
    factor_R        NUMERIC,
    source          TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (team_slug, season, stat)
);

-- ------------------------------------------------------------
-- Météo par match
-- Peuplé par fetch_weather.py via Open-Meteo (gratuit)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.game_weather CASCADE;
CREATE TABLE mlb.game_weather (
    game_id         TEXT PRIMARY KEY,   -- ref mlb.games.game_id (pas de FK pour pré-fetch)
    temperature_f   NUMERIC,
    humidity_pct    NUMERIC,
    wind_speed_mph  NUMERIC,
    wind_dir_deg    INTEGER,            -- direction d'où vient le vent (0=N, 90=E...)
    wind_label      TEXT,               -- 'out' | 'in' | 'cross_L' | 'cross_R' | 'dome' | 'calm'
    precip_mm       NUMERIC,
    condition       TEXT,               -- 'clear' | 'cloudy' | 'rain' | 'dome'
    is_forecast     BOOLEAN DEFAULT false,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
