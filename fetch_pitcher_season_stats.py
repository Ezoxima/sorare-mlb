"""
fetch_pitcher_season_stats.py
-----------------------------
Calcule ERA et ERA+ des pitchers depuis mlb.game_score_details (données internes).

  pitching_innings_pitched (stat_short_name='IP') = outs enregistrés → /3 = IP
  pitching_earned_runs     (stat_short_name='ER') = earned runs

  ERA       = (ER / IP) × 9
  ERA+_est  = 100 × league_ERA / player_ERA   (sans ajustement par parc —
              géré séparément dans ml_predict_gw.py via mlb.park_factors)

Stocke dans mlb.pitcher_season_stats.

Usage:
    python fetch_pitcher_season_stats.py
    python fetch_pitcher_season_stats.py --season 2024
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).parent.parent / ".env")

MIN_OUTS = 30   # = 10 innings minimum (filtre le bruit des courtes sorties)

DB_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME')}"
)


def fetch(engine, season: int) -> pd.DataFrame:
    """Calcule ERA / ERA+ depuis game_score_details pour la saison donnée."""

    # La saison MLB commence début avril ; on prend le 1er mars pour être large
    season_start = f"{season}-03-01"

    print(f"  Calcul ERA depuis game_score_details (saison {season}, depuis {season_start})...")

    df = pd.read_sql(text("""
        WITH raw AS (
            SELECT
                gsd.player_slug,
                SUM(CASE WHEN gsd.stat_short_name = 'IP' THEN gsd.stat_value ELSE 0 END) AS total_outs,
                SUM(CASE WHEN gsd.stat_short_name = 'ER' THEN gsd.stat_value ELSE 0 END) AS total_er
            FROM mlb.game_score_details gsd
            WHERE gsd.category = 'PITCHING'
              AND gsd.game_date >= :start
            GROUP BY gsd.player_slug
        ),
        qualified AS (
            SELECT player_slug,
                   total_outs / 3.0            AS innings_pitched,
                   total_er,
                   total_er / (total_outs / 3.0) * 9 AS era
            FROM raw
            WHERE total_outs >= :min_outs
              AND total_outs > 0
        ),
        league AS (
            SELECT
                SUM(total_er) / NULLIF(SUM(total_outs) / 3.0, 0) * 9 AS lg_era
            FROM raw
            WHERE total_outs >= :min_outs
        )
        SELECT
            q.player_slug,
            :season          AS season,
            ROUND(q.innings_pitched::numeric, 2) AS innings_pitched,
            ROUND(q.era::numeric, 3)             AS era,
            ROUND(100.0 * l.lg_era / NULLIF(q.era, 0), 1) AS era_plus_est,
            ROUND(l.lg_era::numeric, 3)          AS league_era
        FROM qualified q
        CROSS JOIN league l
        ORDER BY q.innings_pitched DESC
    """), engine, params={"start": season_start, "min_outs": MIN_OUTS, "season": season})

    if df.empty:
        print("  Aucune donnée PITCHING trouvée.")
        return df

    valid = df[df["era"].notna() & (df["era"] > 0)]
    lg = float(df["league_era"].iloc[0]) if not df.empty else 4.20
    print(f"  {len(valid)} pitchers qualifiés · ERA ligue : {lg:.2f}")
    return df


def store(engine, df: pd.DataFrame) -> None:
    season = int(df["season"].iloc[0])
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mlb.pitcher_season_stats (
                player_slug     TEXT        NOT NULL,
                season          INTEGER     NOT NULL,
                innings_pitched NUMERIC,
                era             NUMERIC,
                era_plus_est    NUMERIC,
                league_era      NUMERIC,
                updated_at      TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (player_slug, season)
            )
        """))
        conn.execute(text(
            "DELETE FROM mlb.pitcher_season_stats WHERE season = :s"
        ), {"s": season})
    df.to_sql(
        "pitcher_season_stats", engine, schema="mlb",
        if_exists="append", index=False,
    )
    print(f"  {len(df)} lignes → mlb.pitcher_season_stats")


def run(engine=None, season: int | None = None) -> pd.DataFrame:
    if season is None:
        season = datetime.now().year
    if engine is None:
        engine = create_engine(DB_URL)
    df = fetch(engine, season)
    if not df.empty:
        store(engine, df)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calcule ERA/ERA+ pitchers depuis la BDD")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    args = parser.parse_args()
    run(season=args.season)
