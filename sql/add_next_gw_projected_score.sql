ALTER TABLE mlb.players
    ADD COLUMN IF NOT EXISTS next_gw_projected_score NUMERIC;
