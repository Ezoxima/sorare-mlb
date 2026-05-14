-- ============================================================
-- Tables box score MLB
-- ============================================================

-- ------------------------------------------------------------
-- Résumé de match (1 ligne par match)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS mlb.game_innings CASCADE;
DROP TABLE IF EXISTS mlb.games CASCADE;

CREATE TABLE mlb.games (
    game_id               TEXT PRIMARY KEY,   -- UUID extrait de "Game:uuid"
    game_date             TIMESTAMPTZ,
    gw_int                INTEGER,
    fixture_slug          TEXT,
    home_team_slug        TEXT REFERENCES mlb.teams(team_slug),
    away_team_slug        TEXT REFERENCES mlb.teams(team_slug),
    home_score            INTEGER,
    away_score            INTEGER,
    home_hits             INTEGER,
    away_hits             INTEGER,
    home_errors           INTEGER,
    away_errors           INTEGER,
    home_probable_pitcher TEXT,              -- player_slug
    away_probable_pitcher TEXT,              -- player_slug
    winning_pitcher       TEXT,              -- player_slug
    losing_pitcher        TEXT,              -- player_slug
    winner_slug           TEXT,              -- team_slug
    competition_slug      TEXT,
    inning                INTEGER,
    scored                BOOLEAN,
    status                TEXT,
    venue                 TEXT,
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mlb_games_gw      ON mlb.games(gw_int);
CREATE INDEX idx_mlb_games_date    ON mlb.games(game_date);
CREATE INDEX idx_mlb_games_home    ON mlb.games(home_team_slug);
CREATE INDEX idx_mlb_games_away    ON mlb.games(away_team_slug);

-- ------------------------------------------------------------
-- Scores par manche (1 ligne par manche par match)
-- ------------------------------------------------------------
CREATE TABLE mlb.game_innings (
    game_id        TEXT REFERENCES mlb.games(game_id) ON DELETE CASCADE,
    inning_number  INTEGER,
    home_score     INTEGER,
    away_score     INTEGER,
    PRIMARY KEY (game_id, inning_number)
);

CREATE INDEX idx_mlb_game_innings_game ON mlb.game_innings(game_id);
