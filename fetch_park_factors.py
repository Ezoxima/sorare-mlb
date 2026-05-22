"""
fetch_park_factors.py
---------------------
Peuple mlb.park_factors avec les facteurs de parc MLB.

Sources : Baseball Reference + FanGraphs (moyennes 3 ans, saison 2024/2025).
100 = neutre, 110 = +10% pour cette stat dans ce stade, 90 = -10%.

Ces valeurs sont mises a jour manuellement 1x/an (apres chaque offseason).
Derniere mise a jour : 2025 (valeurs 2022-2024, multi-year average).

Stats stockees :
  R   = Runs (production offensive globale)
  HR  = Home Runs (le plus impactant pour les scores Sorare)
  H   = Hits
  2B  = Doubles
  3B  = Triples
  BB  = Walks
  K   = Strikeouts

Colonnes _L / _R = split batter gaucher / droitier.
NULL = pas de donnee split disponible (utilise factor_overall comme fallback).

Usage :
    python fetch_park_factors.py
    python fetch_park_factors.py --season 2024
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

# ── Donnees ────────────────────────────────────────────────────────────────────
#
# Format : (team_slug, stat, overall, L, R)
# Sources :
#   - Baseball Reference park factors (multi-year average 2022-2024)
#   - FanGraphs Guts! park factors
#   - Statcast Park Factors (Baseball Savant)
#
# Splits L/R = performance du batter gaucher (L) ou droitier (R) dans ce stade.
# NULL = pas de donnee split suffisante.
#
# Valeurs notables :
#   - Coors Field (COL) : altitude 5200ft -> balle voyage ~9% plus loin
#   - Oracle Park (SF)  : vent de la Baie de San Francisco -> suppression HR
#   - Yankee Stadium    : porch RF court (314ft) -> faveur massive pour LH HR
#   - Fenway Park       : Green Monster LF -> doubles LH++, HR LH--
#   - Tropicana/Rogers  : dome -> pas d'effet meteo direct

PARK_FACTORS_2025 = [
    # ── Division Est NL ───────────────────────────────────────────────────────
    # team_slug,                stat,  overall,    L,     R
    ("atlanta-braves",          "R",    100,     100,   100),
    ("atlanta-braves",          "HR",   101,     102,   100),
    ("atlanta-braves",          "H",    100,     100,   100),
    ("atlanta-braves",          "2B",   100,     100,   100),
    ("atlanta-braves",          "3B",    98,    None,  None),
    ("atlanta-braves",          "BB",   100,    None,  None),
    ("atlanta-braves",          "K",    100,    None,  None),

    ("miami-marlins",           "R",     96,      96,    96),
    ("miami-marlins",           "HR",    96,      96,    96),
    ("miami-marlins",           "H",     98,      98,    98),
    ("miami-marlins",           "2B",    97,    None,  None),
    ("miami-marlins",           "3B",    97,    None,  None),
    ("miami-marlins",           "BB",    99,    None,  None),
    ("miami-marlins",           "K",    100,    None,  None),

    ("new-york-mets",           "R",     97,      97,    97),
    ("new-york-mets",           "HR",    96,      97,    95),
    ("new-york-mets",           "H",     98,      99,    97),
    ("new-york-mets",           "2B",    98,    None,  None),
    ("new-york-mets",           "3B",   100,    None,  None),
    ("new-york-mets",           "BB",    99,    None,  None),
    ("new-york-mets",           "K",    101,    None,  None),

    ("philadelphia-phillies",   "R",    103,     103,   103),
    ("philadelphia-phillies",   "HR",   107,     108,   106),
    ("philadelphia-phillies",   "H",    102,     102,   102),
    ("philadelphia-phillies",   "2B",   105,    None,  None),
    ("philadelphia-phillies",   "3B",    97,    None,  None),
    ("philadelphia-phillies",   "BB",   101,    None,  None),
    ("philadelphia-phillies",   "K",     99,    None,  None),

    ("washington-nationals",    "R",     99,      99,    99),
    ("washington-nationals",    "HR",   100,     100,   100),
    ("washington-nationals",    "H",    100,     100,   100),
    ("washington-nationals",    "2B",   100,    None,  None),
    ("washington-nationals",    "3B",   102,    None,  None),
    ("washington-nationals",    "BB",   100,    None,  None),
    ("washington-nationals",    "K",    100,    None,  None),

    # ── Division Centrale NL ──────────────────────────────────────────────────
    # Wrigley : vent variable depuis le lac Michigan -> tres sensible a la meteo
    ("chicago-cubs",            "R",    105,     105,   105),
    ("chicago-cubs",            "HR",   107,     108,   106),
    ("chicago-cubs",            "H",    103,     103,   103),
    ("chicago-cubs",            "2B",   103,    None,  None),
    ("chicago-cubs",            "3B",    96,    None,  None),
    ("chicago-cubs",            "BB",   101,    None,  None),
    ("chicago-cubs",            "K",     99,    None,  None),

    # GABP Cincinnati : park HR+ bien connu
    ("cincinnati-reds",         "R",    107,     107,   107),
    ("cincinnati-reds",         "HR",   113,     114,   112),
    ("cincinnati-reds",         "H",    103,     103,   103),
    ("cincinnati-reds",         "2B",   104,    None,  None),
    ("cincinnati-reds",         "3B",   101,    None,  None),
    ("cincinnati-reds",         "BB",   102,    None,  None),
    ("cincinnati-reds",         "K",     98,    None,  None),

    ("milwaukee-brewers",       "R",     99,      99,    99),
    ("milwaukee-brewers",       "HR",   100,     100,   100),
    ("milwaukee-brewers",       "H",    100,     100,   100),
    ("milwaukee-brewers",       "2B",   100,    None,  None),
    ("milwaukee-brewers",       "3B",    99,    None,  None),
    ("milwaukee-brewers",       "BB",   100,    None,  None),
    ("milwaukee-brewers",       "K",    100,    None,  None),

    # PNC Park : pitcher's park leger
    ("pittsburgh-pirates",      "R",     97,      97,    97),
    ("pittsburgh-pirates",      "HR",    97,      97,    97),
    ("pittsburgh-pirates",      "H",     98,      98,    98),
    ("pittsburgh-pirates",      "2B",    98,    None,  None),
    ("pittsburgh-pirates",      "3B",   102,    None,  None),
    ("pittsburgh-pirates",      "BB",    99,    None,  None),
    ("pittsburgh-pirates",      "K",    101,    None,  None),

    ("st-louis-cardinals",      "R",     99,      99,    99),
    ("st-louis-cardinals",      "HR",    98,      99,    97),
    ("st-louis-cardinals",      "H",    100,     100,   100),
    ("st-louis-cardinals",      "2B",   100,    None,  None),
    ("st-louis-cardinals",      "3B",   100,    None,  None),
    ("st-louis-cardinals",      "BB",   100,    None,  None),
    ("st-louis-cardinals",      "K",    100,    None,  None),

    # ── Division Ouest NL ─────────────────────────────────────────────────────
    ("arizona-diamondbacks",    "R",    103,     103,   103),
    ("arizona-diamondbacks",    "HR",   106,     107,   105),
    ("arizona-diamondbacks",    "H",    102,     102,   102),
    ("arizona-diamondbacks",    "2B",   103,    None,  None),
    ("arizona-diamondbacks",    "3B",   101,    None,  None),
    ("arizona-diamondbacks",    "BB",   101,    None,  None),
    ("arizona-diamondbacks",    "K",     99,    None,  None),

    # Coors Field : effet altitude exceptionnel (balle +9% de distance)
    ("colorado-rockies",        "R",    117,     117,   117),
    ("colorado-rockies",        "HR",   120,     122,   118),
    ("colorado-rockies",        "H",    112,     113,   111),
    ("colorado-rockies",        "2B",   110,     111,   109),
    ("colorado-rockies",        "3B",   149,     148,   150),  # triples++
    ("colorado-rockies",        "BB",   104,    None,  None),
    ("colorado-rockies",        "K",     96,    None,  None),

    ("los-angeles-dodgers",     "R",     97,      97,    97),
    ("los-angeles-dodgers",     "HR",    97,      97,    97),
    ("los-angeles-dodgers",     "H",     98,      98,    98),
    ("los-angeles-dodgers",     "2B",    99,    None,  None),
    ("los-angeles-dodgers",     "3B",   100,    None,  None),
    ("los-angeles-dodgers",     "BB",    99,    None,  None),
    ("los-angeles-dodgers",     "K",    100,    None,  None),

    # Petco Park : pitcher's park reconnu
    ("san-diego-padres",        "R",     94,      94,    94),
    ("san-diego-padres",        "HR",    91,      92,    90),
    ("san-diego-padres",        "H",     96,      96,    96),
    ("san-diego-padres",        "2B",    96,    None,  None),
    ("san-diego-padres",        "3B",   101,    None,  None),
    ("san-diego-padres",        "BB",    98,    None,  None),
    ("san-diego-padres",        "K",    102,    None,  None),

    # Oracle Park : vent de la Baie -> suppression HR marquee
    ("san-francisco-giants",    "R",     93,      93,    93),
    ("san-francisco-giants",    "HR",    86,      87,    85),
    ("san-francisco-giants",    "H",     96,      96,    96),
    ("san-francisco-giants",    "2B",    97,    None,  None),
    ("san-francisco-giants",    "3B",   105,    None,  None),
    ("san-francisco-giants",    "BB",    98,    None,  None),
    ("san-francisco-giants",    "K",    102,    None,  None),

    # ── Division Est AL ───────────────────────────────────────────────────────
    ("baltimore-orioles",       "R",    101,     101,   101),
    ("baltimore-orioles",       "HR",   103,     103,   103),
    ("baltimore-orioles",       "H",    101,     101,   101),
    ("baltimore-orioles",       "2B",   101,    None,  None),
    ("baltimore-orioles",       "3B",    99,    None,  None),
    ("baltimore-orioles",       "BB",   100,    None,  None),
    ("baltimore-orioles",       "K",    100,    None,  None),

    # Fenway Park : Green Monster LF -> doubles++ (surtout LH), HR LH moindre car mur
    ("boston-red-sox",          "R",    106,     106,   106),
    ("boston-red-sox",          "HR",   100,      94,   105),  # LH: mur absorbe les HR
    ("boston-red-sox",          "H",    109,     110,   108),
    ("boston-red-sox",          "2B",   124,     140,   110),  # Green Monster -> doubles++
    ("boston-red-sox",          "3B",    86,    None,  None),  # 3B-- (trop petit)
    ("boston-red-sox",          "BB",   103,    None,  None),
    ("boston-red-sox",          "K",     98,    None,  None),

    # Yankee Stadium : porch RF 314ft -> HR LH massivement favorises
    ("new-york-yankees",        "R",    107,     110,   104),
    ("new-york-yankees",        "HR",   115,     128,    97),  # LH hitters TRES favorises
    ("new-york-yankees",        "H",    102,     103,   101),
    ("new-york-yankees",        "2B",   102,    None,  None),
    ("new-york-yankees",        "3B",    95,    None,  None),
    ("new-york-yankees",        "BB",   102,    None,  None),
    ("new-york-yankees",        "K",     99,    None,  None),

    # Tropicana : dome + turf -> suppression HR, vitesse balle differente
    ("tampa-bay-rays",          "R",     94,      94,    94),
    ("tampa-bay-rays",          "HR",    89,      89,    89),
    ("tampa-bay-rays",          "H",     97,      97,    97),
    ("tampa-bay-rays",          "2B",    97,    None,  None),
    ("tampa-bay-rays",          "3B",   105,    None,  None),  # turf -> 3B++
    ("tampa-bay-rays",          "BB",    99,    None,  None),
    ("tampa-bay-rays",          "K",    101,    None,  None),

    # Rogers Centre : dome + turf
    ("toronto-blue-jays",       "R",    104,     104,   104),
    ("toronto-blue-jays",       "HR",   109,     110,   108),
    ("toronto-blue-jays",       "H",    102,     102,   102),
    ("toronto-blue-jays",       "2B",   102,    None,  None),
    ("toronto-blue-jays",       "3B",   106,    None,  None),  # turf -> 3B++
    ("toronto-blue-jays",       "BB",   101,    None,  None),
    ("toronto-blue-jays",       "K",     99,    None,  None),

    # ── Division Centrale AL ──────────────────────────────────────────────────
    ("chicago-white-sox",       "R",    100,     100,   100),
    ("chicago-white-sox",       "HR",   105,     105,   105),
    ("chicago-white-sox",       "H",    100,     100,   100),
    ("chicago-white-sox",       "2B",   100,    None,  None),
    ("chicago-white-sox",       "3B",    98,    None,  None),
    ("chicago-white-sox",       "BB",   100,    None,  None),
    ("chicago-white-sox",       "K",    100,    None,  None),

    ("cleveland-guardians",     "R",     97,      97,    97),
    ("cleveland-guardians",     "HR",    97,      97,    97),
    ("cleveland-guardians",     "H",     98,      98,    98),
    ("cleveland-guardians",     "2B",    98,    None,  None),
    ("cleveland-guardians",     "3B",   100,    None,  None),
    ("cleveland-guardians",     "BB",    99,    None,  None),
    ("cleveland-guardians",     "K",    101,    None,  None),

    # Comerica Park : grand CF (420ft) -> suppression leger
    ("detroit-tigers",          "R",     97,      97,    97),
    ("detroit-tigers",          "HR",    95,      95,    95),
    ("detroit-tigers",          "H",    100,     100,   100),
    ("detroit-tigers",          "2B",   100,    None,  None),
    ("detroit-tigers",          "3B",   102,    None,  None),
    ("detroit-tigers",          "BB",    99,    None,  None),
    ("detroit-tigers",          "K",    101,    None,  None),

    ("kansas-city-royals",      "R",     97,      97,    97),
    ("kansas-city-royals",      "HR",    94,      94,    94),
    ("kansas-city-royals",      "H",     99,      99,    99),
    ("kansas-city-royals",      "2B",    99,    None,  None),
    ("kansas-city-royals",      "3B",   101,    None,  None),
    ("kansas-city-royals",      "BB",    99,    None,  None),
    ("kansas-city-royals",      "K",    101,    None,  None),

    ("minnesota-twins",         "R",    101,     101,   101),
    ("minnesota-twins",         "HR",   105,     105,   105),
    ("minnesota-twins",         "H",    101,     101,   101),
    ("minnesota-twins",         "2B",   101,    None,  None),
    ("minnesota-twins",         "3B",    99,    None,  None),
    ("minnesota-twins",         "BB",   100,    None,  None),
    ("minnesota-twins",         "K",    100,    None,  None),

    # ── Division Ouest AL ─────────────────────────────────────────────────────
    ("houston-astros",          "R",    100,     100,   100),
    ("houston-astros",          "HR",   100,     100,   100),
    ("houston-astros",          "H",    101,     101,   101),
    ("houston-astros",          "2B",   101,    None,  None),
    ("houston-astros",          "3B",    99,    None,  None),
    ("houston-astros",          "BB",   100,    None,  None),
    ("houston-astros",          "K",    100,    None,  None),

    ("los-angeles-angels",      "R",    100,     100,   100),
    ("los-angeles-angels",      "HR",   101,     101,   101),
    ("los-angeles-angels",      "H",    101,     101,   101),
    ("los-angeles-angels",      "2B",   100,    None,  None),
    ("los-angeles-angels",      "3B",   101,    None,  None),
    ("los-angeles-angels",      "BB",   100,    None,  None),
    ("los-angeles-angels",      "K",    100,    None,  None),

    # Oakland/Sacramento (Sutter Health Park) : parc AAA, donnees limitees
    ("oakland-athletics",       "R",    102,     102,   102),
    ("oakland-athletics",       "HR",   100,     100,   100),
    ("oakland-athletics",       "H",    101,     101,   101),
    ("oakland-athletics",       "2B",   100,    None,  None),
    ("oakland-athletics",       "3B",   103,    None,  None),
    ("oakland-athletics",       "BB",   101,    None,  None),
    ("oakland-athletics",       "K",    100,    None,  None),

    ("seattle-mariners",        "R",     98,      98,    98),
    ("seattle-mariners",        "HR",    97,      97,    97),
    ("seattle-mariners",        "H",     99,      99,    99),
    ("seattle-mariners",        "2B",    99,    None,  None),
    ("seattle-mariners",        "3B",   100,    None,  None),
    ("seattle-mariners",        "BB",    99,    None,  None),
    ("seattle-mariners",        "K",    101,    None,  None),

    ("texas-rangers",           "R",    104,     104,   104),
    ("texas-rangers",           "HR",   106,     107,   105),
    ("texas-rangers",           "H",    103,     103,   103),
    ("texas-rangers",           "2B",   103,    None,  None),
    ("texas-rangers",           "3B",   100,    None,  None),
    ("texas-rangers",           "BB",   101,    None,  None),
    ("texas-rangers",           "K",     99,    None,  None),
]

COLUMNS = ["team_slug", "stat", "factor_overall", "factor_l", "factor_r"]


# ── Main ───────────────────────────────────────────────────────────────────────

def run(season: int = 2025):
    engine = create_engine(DB_URL)

    # Verifie que la table existe
    with engine.connect() as conn:
        exists = conn.execute(text(
            "SELECT to_regclass('mlb.park_factors')"
        )).scalar()
    if not exists:
        print("Table mlb.park_factors absente. Lancer init_stadiums.py d'abord.")
        return

    print(f"Insertion des park factors saison {season}...")
    df = pd.DataFrame(PARK_FACTORS_2025, columns=COLUMNS)
    df["season"] = season
    df["source"] = "bbref_fangraphs_2022-2024_avg"

    with engine.begin() as conn:
        meta = MetaData(schema="mlb")
        meta.reflect(bind=engine, schema="mlb", only=["park_factors"])
        tbl = meta.tables["mlb.park_factors"]

        stmt = pg_insert(tbl).values(df.to_dict("records"))
        stmt = stmt.on_conflict_do_update(
            index_elements=["team_slug", "season", "stat"],
            set_={
                "factor_overall": stmt.excluded.factor_overall,
                "factor_l":       stmt.excluded.factor_l,
                "factor_r":       stmt.excluded.factor_r,
                "source":         stmt.excluded.source,
                "updated_at":     text("NOW()"),
            },
        )
        conn.execute(stmt)

    n_teams = df["team_slug"].nunique()
    n_stats = df["stat"].nunique()
    print(f"  {len(df)} lignes inserees ({n_teams} equipes x {n_stats} stats) pour saison {season}")

    # ── Resume des extremes (park le plus offensif / defensif par stat) ────────
    print(f"\nExtremes par stat (saison {season}) :")
    for stat in ["HR", "R", "H", "2B"]:
        sub = df[df["stat"] == stat].sort_values("factor_overall")
        if sub.empty:
            continue
        lo = sub.iloc[0]
        hi = sub.iloc[-1]
        print(f"  {stat:3s}  min={lo['factor_overall']:3.0f} ({lo['team_slug']:<28s})  "
              f"max={hi['factor_overall']:3.0f} ({hi['team_slug']})")

    # Alerte stades avec splits L/R notables (ecart > 10pts)
    split_df = df.dropna(subset=["factor_l", "factor_r"]).copy()
    split_df["split_gap"] = (split_df["factor_l"] - split_df["factor_r"]).abs()
    notable_splits = split_df[split_df["split_gap"] > 10].sort_values("split_gap", ascending=False)
    if not notable_splits.empty:
        print(f"\nSplits L/R notables (ecart > 10 pts) :")
        for _, row in notable_splits.iterrows():
            print(f"  {row['team_slug']:<28s} {row['stat']:3s}  "
                  f"L={row['factor_l']:.0f}  R={row['factor_r']:.0f}  "
                  f"(ecart={row['split_gap']:.0f})")

    print("\nTermine.")
    print("Note : valeurs basees sur moyennes 2022-2024.")
    print("Mettre a jour PARK_FACTORS_2025 chaque offseason avec les nouvelles stats.")


if __name__ == "__main__":
    season = 2025
    for arg in sys.argv[1:]:
        if arg.startswith("--season"):
            season = int(arg.split("=")[-1]) if "=" in arg else int(sys.argv[sys.argv.index(arg) + 1])
    run(season)
