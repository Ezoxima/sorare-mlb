-- Table centralisée de suivi de la fraîcheur des données
-- freshness_date : date métier (updated_at, MAX(game_date), MIN(next_game_date)…)
-- refreshed_at   : quand le script d'update a tourné

CREATE TABLE IF NOT EXISTS mlb.data_freshness (
    table_name      TEXT PRIMARY KEY,
    freshness_date  TIMESTAMPTZ,
    refreshed_at    TIMESTAMPTZ DEFAULT NOW()
);
