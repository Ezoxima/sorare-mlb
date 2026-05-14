-- Schéma MLB pour les données Sorare Baseball
CREATE SCHEMA IF NOT EXISTS mlb;

-- Table galerie : une ligne = une carte dans la galerie d'un manager
-- Rechargée intégralement à chaque run via l'API Sorare
CREATE TABLE IF NOT EXISTS mlb.gallery_players (
    id_manager                      TEXT,
    gallery_manager                 TEXT,
    card_slug                       TEXT,
    card_name                       TEXT,
    player_name                     TEXT,
    card_rarity                     TEXT,
    card_display_rarity             TEXT,
    card_grade                      INTEGER,
    card_xp                         INTEGER,
    card_xp_needed_current_grade    INTEGER,
    card_xp_needed_next_grade       INTEGER,
    card_power                      NUMERIC,
    card_display_position           TEXT,
    player_slug                     TEXT,
    player_age                      INTEGER,
    in_season_eligible              BOOLEAN,
    competition_slug                TEXT,
    competition_name                TEXT,
    home_team_slug                  TEXT,
    home_team_name                  TEXT,
    away_team_slug                  TEXT,
    away_team_name                  TEXT,
    next_game_date                  TIMESTAMPTZ,
    sealed                          BOOLEAN,
    active_club_slug                TEXT,
    home_away                       TEXT
);

CREATE INDEX IF NOT EXISTS idx_mlb_gallery_player_slug ON mlb.gallery_players(player_slug);
CREATE INDEX IF NOT EXISTS idx_mlb_gallery_id_manager  ON mlb.gallery_players(id_manager);
