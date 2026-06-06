"""
Pivote mlb.game_score_details (EAV, BDD locale) vers mlb.game_score_details_wide
(format wide, Supabase). La BDD locale n'est jamais modifiée.

Usage :
    python scripts/migrate_gsd_pivot.py

Variables d'environnement requises dans D:/git/sorare/.env :
    DB_USER / DB_PASSWORD / DB_HOST / DB_PORT / DB_NAME  (BDD locale)
    DATABASE_URL_SUPABASE                                 (Supabase)
"""

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parent.parent.parent / ".env")  # D:/git/sorare/.env

# ── Connexions ─────────────────────────────────────────────────────────────────
local_url = (
    f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
    f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
)
supabase_url = os.environ.get("DATABASE_URL_SUPABASE")
if not supabase_url:
    print("ERREUR : DATABASE_URL_SUPABASE manquant dans .env")
    sys.exit(1)

# Re-encode l'URL pour gérer les caractères spéciaux dans le mot de passe (&, @, etc.)
from urllib.parse import urlparse, urlunparse
_parsed = urlparse(supabase_url)
_safe_url = urlunparse(_parsed._replace(
    netloc=f"{quote_plus(_parsed.username)}:{quote_plus(_parsed.password)}@{_parsed.hostname}:{_parsed.port}"
))

local_engine    = create_engine(local_url)
supabase_engine = create_engine(_safe_url, connect_args={"sslmode": "require"})

# ── Chargement local ───────────────────────────────────────────────────────────
print("Chargement game_score_details depuis BDD locale...")
df = pd.read_sql("SELECT * FROM mlb.game_score_details", local_engine)
print(f"  {len(df):,} lignes chargées")
print(f"  Colonnes : {list(df.columns)}")

# gw_int récupéré depuis game_scores (joint sur player_slug + game_date)
print("Chargement gw_int depuis game_scores...")
gw = pd.read_sql(
    "SELECT player_slug, game_date, MAX(gw_int) AS gw_int FROM mlb.game_scores GROUP BY player_slug, game_date",
    local_engine,
)
df = df.merge(gw, on=["player_slug", "game_date"], how="left")

idx_cols = ["player_slug", "game_date", "gw_int", "category"]

# ── Pivot stat_value ───────────────────────────────────────────────────────────
print("Pivot en cours...")
wide_val = df.pivot_table(
    index=idx_cols,
    columns="stat",
    values="stat_value",
    aggfunc="first",
).reset_index()
wide_val.columns.name = None

# ── Pivot points ───────────────────────────────────────────────────────────────
wide_pts = df.pivot_table(
    index=idx_cols,
    columns="stat",
    values="points",
    aggfunc="first",
).reset_index()
wide_pts.columns.name = None

# Renommer les colonnes points avec suffixe _pts
stat_cols = [c for c in wide_pts.columns if c not in idx_cols]
wide_pts = wide_pts.rename(columns={c: f"{c}_pts" for c in stat_cols})

# ── Merge val + points ─────────────────────────────────────────────────────────
wide = wide_val.merge(
    wide_pts,
    on=idx_cols,
    how="left",
)

# game_date en date (pas datetime)
wide["game_date"] = pd.to_datetime(wide["game_date"], utc=True)

# Dédoublonnage sur la PK cible
wide = wide.drop_duplicates(subset=["player_slug", "game_date", "category"])
print(f"  -> {len(wide):,} lignes wide ({len(wide.columns)} colonnes)")

# ── Écriture Supabase ──────────────────────────────────────────────────────────
print("Écriture vers Supabase (par chunks de 2000)...")
with supabase_engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE mlb.game_score_details_wide"))

wide.to_sql(
    "game_score_details_wide",
    supabase_engine,
    schema="mlb",
    if_exists="append",
    index=False,
    chunksize=2000,
    method="multi",
)

print(f"OK - Migration terminee : {len(wide):,} lignes dans mlb.game_score_details_wide")
