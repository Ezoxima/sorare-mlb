"""
init_stadiums.py
----------------
Cree et peuple les tables contextuelles pour les projections MLB :
  - mlb.stadiums     : 30 stades MLB (statique, ~1x/an)
  - mlb.park_factors : facteurs de parc par saison (rempli par fetch_park_factors.py)
  - mlb.game_weather : meteo par match (rempli par fetch_weather.py)

Toutes les tables sont creees en IF NOT EXISTS — idempotent, sans perte de donnees.
Les stades sont upserted : relancer le script met les donnees a jour sans reset.

Usage :
    python init_stadiums.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Table, MetaData

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).parent.parent / ".env")

DB_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}"
)

# ── DDL ────────────────────────────────────────────────────────────────────────

CREATE_STADIUMS = """
CREATE TABLE IF NOT EXISTS mlb.stadiums (
    team_slug       TEXT PRIMARY KEY,   -- FK vers mlb.teams.team_slug
    venue           TEXT,               -- nom tel que retourne par l'API Sorare (mlb.games.venue)
    stadium_name    TEXT,               -- nom officiel complet
    city            TEXT,
    state           TEXT,               -- code etat US (ou province CA)
    latitude        NUMERIC,
    longitude       NUMERIC,
    altitude_ft     INTEGER,            -- altitude en pieds (critique pour Coors Field)
    is_dome         BOOLEAN DEFAULT false,
    roof_type       TEXT,               -- 'open' | 'retractable' | 'fixed_dome'
    surface         TEXT,               -- 'grass' | 'turf'
    lf_dist_ft      INTEGER,            -- distance au mur LF (pieds)
    cf_dist_ft      INTEGER,            -- distance au mur CF
    rf_dist_ft      INTEGER,            -- distance au mur RF
    lf_wall_ft      NUMERIC,            -- hauteur mur LF (Fenway Green Monster = 37ft!)
    rf_wall_ft      NUMERIC,            -- hauteur mur RF
    capacity        INTEGER,
    -- Orientation du stade pour calcul du vent (degres, 0=N, sens horaire)
    -- Orientation = direction depuis home plate vers CF
    cf_orientation_deg  INTEGER
);
"""

CREATE_PARK_FACTORS = """
CREATE TABLE IF NOT EXISTS mlb.park_factors (
    team_slug       TEXT    NOT NULL,
    season          INTEGER NOT NULL,
    stat            TEXT    NOT NULL,   -- 'HR' | 'H' | 'R' | 'BB' | 'K' | '2B' | '3B'
    factor_overall  NUMERIC,            -- 100 = neutre, 110 = +10%, 90 = -10%
    factor_L        NUMERIC,            -- batter gaucher vs ce stade
    factor_R        NUMERIC,            -- batter droitier vs ce stade
    source          TEXT,               -- 'fangraphs' | 'bbref' | 'statcast'
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (team_slug, season, stat)
);
"""

CREATE_GAME_WEATHER = """
CREATE TABLE IF NOT EXISTS mlb.game_weather (
    game_id         TEXT PRIMARY KEY,   -- ref mlb.games.game_id (pas de FK pour permettre pre-fetch)
    temperature_f   NUMERIC,
    humidity_pct    NUMERIC,
    wind_speed_mph  NUMERIC,
    wind_dir_deg    INTEGER,            -- direction D'OU vient le vent (0=N, 90=E, 180=S, 270=W)
    wind_label      TEXT,               -- 'out' | 'in' | 'cross_L' | 'cross_R' | 'dome' | 'calm'
    precip_mm       NUMERIC,
    condition       TEXT,               -- 'clear' | 'cloudy' | 'rain' | 'dome'
    is_forecast     BOOLEAN DEFAULT false,  -- true = prevision, false = observe
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
"""

# ── Donnees stades ─────────────────────────────────────────────────────────────
#
# Sources :
#   - Dimensions : Baseball Reference, ESPN, MLB.com
#   - Coordonnees GPS : Google Maps (home plate)
#   - Altitudes : Wikipedia / NOAA
#   - Orientation CF : approximative (voir fetch_weather.py pour le calcul exact)
#
# IMPORTANT : team_slug doit correspondre EXACTEMENT a mlb.teams.team_slug.
# Si des slugs ne matchent pas apres insertion, le script affiche un avertissement.
# Verifier avec : SELECT team_slug FROM mlb.teams ORDER BY team_slug;
#
# Colonnes : team_slug, venue, stadium_name, city, state,
#            lat, lon, alt_ft, is_dome, roof_type, surface,
#            lf, cf, rf, lf_wall, rf_wall, capacity, cf_orientation_deg

STADIUMS = [
    # ── Division Est NL ───────────────────────────────────────────────────────
    ("atlanta-braves",
     "Truist Park", "Truist Park",
     "Cumberland", "GA",
     33.8908, -84.4678, 987,
     False, "open", "grass",
     335, 400, 325, 8, 8, 41084, 20),

    ("miami-marlins",
     "loanDepot park", "loanDepot park",
     "Miami", "FL",
     25.7781, -80.2197, 6,
     True, "retractable", "grass",
     344, 407, 335, 8, 8, 36742, 345),

    ("new-york-mets",
     "Citi Field", "Citi Field",
     "New York", "NY",
     40.7571, -73.8458, 20,
     False, "open", "grass",
     335, 408, 330, 8, 8, 41922, 10),

    ("philadelphia-phillies",
     "Citizens Bank Park", "Citizens Bank Park",
     "Philadelphia", "PA",
     39.9061, -75.1665, 20,
     False, "open", "grass",
     329, 401, 330, 8, 8, 43651, 5),

    ("washington-nationals",
     "Nationals Park", "Nationals Park",
     "Washington", "DC",
     38.8730, -77.0074, 25,
     False, "open", "grass",
     336, 402, 335, 8, 8, 41339, 355),

    # ── Division Centrale NL ──────────────────────────────────────────────────
    ("chicago-cubs",
     "Wrigley Field", "Wrigley Field",
     "Chicago", "IL",
     41.9484, -87.6553, 595,
     False, "open", "grass",
     355, 400, 353, 11, 11, 41649, 90),  # orienté vers le lac Michigan (vent variable)

    ("cincinnati-reds",
     "Great American Ball Park", "Great American Ball Park",
     "Cincinnati", "OH",
     39.0979, -84.5073, 483,
     False, "open", "grass",
     328, 404, 325, 12, 8, 42319, 25),

    ("milwaukee-brewers",
     "American Family Field", "American Family Field",
     "Milwaukee", "WI",
     43.0280, -87.9712, 634,
     True, "retractable", "turf",
     344, 400, 345, 8, 8, 41900, 350),

    ("pittsburgh-pirates",
     "PNC Park", "PNC Park",
     "Pittsburgh", "PA",
     40.4469, -80.0057, 730,
     False, "open", "grass",
     325, 399, 320, 6, 21, 38362, 5),   # mur RF "Clemente Wall" 21ft

    ("st-louis-cardinals",
     "Busch Stadium", "Busch Stadium",
     "St. Louis", "MO",
     38.6226, -90.1928, 455,
     False, "open", "grass",
     336, 400, 335, 8, 8, 44494, 15),

    # ── Division Ouest NL ─────────────────────────────────────────────────────
    ("arizona-diamondbacks",
     "Chase Field", "Chase Field",
     "Phoenix", "AZ",
     33.4453, -112.0667, 1082,
     True, "retractable", "turf",
     330, 407, 335, 7, 25, 48633, 345),

    ("colorado-rockies",
     "Coors Field", "Coors Field",
     "Denver", "CO",
     39.7559, -104.9942, 5200,    # altitude critique : balle voyage ~9% plus loin
     False, "open", "grass",
     347, 415, 350, 8, 14, 46897, 345),

    ("los-angeles-dodgers",
     "Dodger Stadium", "Dodger Stadium",
     "Los Angeles", "CA",
     34.0739, -118.2400, 510,
     False, "open", "grass",
     330, 395, 330, 8, 8, 56000, 350),

    ("san-diego-padres",
     "Petco Park", "Petco Park",
     "San Diego", "CA",
     32.7073, -117.1566, 62,
     False, "open", "grass",
     334, 396, 322, 8, 8, 40162, 315),

    ("san-francisco-giants",
     "Oracle Park", "Oracle Park",
     "San Francisco", "CA",
     37.7786, -122.3893, 10,
     False, "open", "grass",
     339, 399, 309, 8, 8, 41915, 50),  # vent dominant depuis la Baie = vent entrant

    # ── Division Est AL ───────────────────────────────────────────────────────
    ("baltimore-orioles",
     "Oriole Park at Camden Yards", "Oriole Park at Camden Yards",
     "Baltimore", "MD",
     39.2839, -76.6217, 40,
     False, "open", "grass",
     333, 410, 318, 7, 7, 45971, 30),

    ("boston-red-sox",
     "Fenway Park", "Fenway Park",
     "Boston", "MA",
     42.3467, -71.0972, 20,
     False, "open", "grass",
     310, 420, 302, 37, 5, 37755, 65),  # Green Monster LF = 37.2ft

    ("new-york-yankees",
     "Yankee Stadium", "Yankee Stadium",
     "New York", "NY",
     40.8296, -73.9262, 55,
     False, "open", "grass",
     318, 408, 314, 8, 8, 54251, 355),  # porch RF court (314ft) favorise LH hitters

    ("tampa-bay-rays",
     "Tropicana Field", "Tropicana Field",
     "St. Petersburg", "FL",
     27.7683, -82.6534, 5,
     True, "fixed_dome", "turf",
     315, 404, 322, 9, 9, 25025, 0),    # dome fixe : meteo irrelevante

    ("toronto-blue-jays",
     "Rogers Centre", "Rogers Centre",
     "Toronto", "ON",
     43.6414, -79.3894, 250,
     True, "fixed_dome", "turf",
     328, 400, 328, 10, 10, 49286, 0),  # dome fixe

    # ── Division Centrale AL ──────────────────────────────────────────────────
    ("chicago-white-sox",
     "Guaranteed Rate Field", "Guaranteed Rate Field",
     "Chicago", "IL",
     41.8300, -87.6339, 595,
     False, "open", "grass",
     330, 400, 335, 8, 8, 40615, 5),

    ("cleveland-guardians",
     "Progressive Field", "Progressive Field",
     "Cleveland", "OH",
     41.4959, -81.6853, 610,
     False, "open", "grass",
     325, 405, 325, 19, 8, 34788, 15),

    ("detroit-tigers",
     "Comerica Park", "Comerica Park",
     "Detroit", "MI",
     42.3390, -83.0485, 585,
     False, "open", "grass",
     345, 420, 330, 8, 8, 41083, 30),

    ("kansas-city-royals",
     "Kauffman Stadium", "Kauffman Stadium",
     "Kansas City", "MO",
     39.0517, -94.4803, 905,
     False, "open", "grass",
     330, 410, 330, 8, 8, 37903, 10),

    ("minnesota-twins",
     "Target Field", "Target Field",
     "Minneapolis", "MN",
     44.9817, -93.2781, 830,
     False, "open", "grass",
     339, 404, 328, 8, 8, 38544, 350),

    # ── Division Ouest AL ─────────────────────────────────────────────────────
    ("houston-astros",
     "Minute Maid Park", "Minute Maid Park",
     "Houston", "TX",
     29.7572, -95.3555, 43,
     True, "retractable", "grass",
     315, 435, 326, 9, 7, 41168, 345),

    ("los-angeles-angels",
     "Angel Stadium", "Angel Stadium of Anaheim",
     "Anaheim", "CA",
     33.8003, -117.8827, 160,
     False, "open", "grass",
     347, 396, 350, 8, 8, 45517, 15),

    # Oakland A's -> Sacramento (Sutter Health Park) en 2025
    # VERIFIER : le slug Sorare est peut-etre "athletics" sans "oakland-"
    ("oakland-athletics",
     "Sutter Health Park", "Sutter Health Park",
     "Sacramento", "CA",
     38.5729, -121.5064, 25,
     False, "open", "grass",
     330, 403, 325, 8, 8, 14014, 350),

    ("seattle-mariners",
     "T-Mobile Park", "T-Mobile Park",
     "Seattle", "WA",
     47.5914, -122.3324, 20,
     True, "retractable", "grass",
     331, 401, 326, 8, 8, 47943, 355),

    ("texas-rangers",
     "Globe Life Field", "Globe Life Field",
     "Arlington", "TX",
     32.7474, -97.0828, 551,
     True, "retractable", "turf",
     334, 407, 326, 8, 8, 40518, 345),
]

COLUMNS = [
    "team_slug", "venue", "stadium_name", "city", "state",
    "latitude", "longitude", "altitude_ft",
    "is_dome", "roof_type", "surface",
    "lf_dist_ft", "cf_dist_ft", "rf_dist_ft",
    "lf_wall_ft", "rf_wall_ft", "capacity",
    "cf_orientation_deg",
]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    engine = create_engine(DB_URL)

    print("Creation des tables...")
    with engine.begin() as conn:
        conn.execute(text(CREATE_STADIUMS))
        conn.execute(text(CREATE_PARK_FACTORS))
        conn.execute(text(CREATE_GAME_WEATHER))
    print("  mlb.stadiums        OK")
    print("  mlb.park_factors    OK")
    print("  mlb.game_weather    OK")

    print(f"\nInsertion de {len(STADIUMS)} stades...")
    df = pd.DataFrame(STADIUMS, columns=COLUMNS)

    with engine.begin() as conn:
        meta = MetaData(schema="mlb")
        meta.reflect(bind=engine, schema="mlb", only=["stadiums"])
        tbl = meta.tables["mlb.stadiums"]

        stmt = pg_insert(tbl).values(df.to_dict("records"))
        stmt = stmt.on_conflict_do_update(
            index_elements=["team_slug"],
            set_={c: stmt.excluded[c] for c in COLUMNS if c != "team_slug"},
        )
        conn.execute(stmt)

    print(f"  {len(df)} stades inseres/mis a jour")

    # ── Verification : slugs non reconnus dans mlb.teams ──────────────────────
    print("\nVerification des team_slugs vs mlb.teams...")
    known = pd.read_sql("SELECT team_slug FROM mlb.teams", engine)
    known_set = set(known["team_slug"])
    inserted_set = set(df["team_slug"])

    missing = inserted_set - known_set
    if missing:
        print(f"  ATTENTION : {len(missing)} slug(s) dans mlb.stadiums absent(s) de mlb.teams :")
        for s in sorted(missing):
            print(f"    - {s}")
        print("  -> Verifier avec : SELECT team_slug FROM mlb.teams ORDER BY team_slug;")
        print("  -> Corriger les slugs dans STADIUMS et relancer.")
    else:
        print("  Tous les slugs correspondent a mlb.teams.")

    extra = known_set - inserted_set
    if extra:
        print(f"  INFO : {len(extra)} equipe(s) dans mlb.teams sans stade defini :")
        for s in sorted(extra):
            print(f"    - {s}")

    # ── Resume stades notables ─────────────────────────────────────────────────
    print("\nStades a impact fort sur les projections :")
    df2 = df.copy()
    df2["note"] = ""
    df2.loc[df2["altitude_ft"] > 1000, "note"] += " altitude"
    df2.loc[df2["is_dome"], "note"] += " dome"
    df2.loc[df2["lf_wall_ft"] > 15, "note"] += " mur-LF"
    df2.loc[df2["rf_wall_ft"] > 15, "note"] += " mur-RF"
    df2.loc[df2["cf_dist_ft"] >= 415, "note"] += " CF-profond"
    notable = df2[df2["note"].str.strip() != ""][
        ["team_slug", "stadium_name", "altitude_ft", "roof_type",
         "lf_dist_ft", "cf_dist_ft", "rf_dist_ft", "lf_wall_ft", "note"]
    ]
    print(notable.to_string(index=False))

    print("\nTermine.")
    print("\nProchaines etapes :")
    print("  python fetch_park_factors.py   # park factors depuis pybaseball (requiert: pip install pybaseball)")
    print("  python fetch_weather.py        # meteo historique + forecast via Open-Meteo")


if __name__ == "__main__":
    main()
