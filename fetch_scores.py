"""
fetch_scores.py
---------------
Récupère l'historique des scores MLB pour tous les joueurs dans mlb.players.
Stratégie incrémentale : démarre à MAX(game_date) - 1 jour déjà en base.
Si la table est vide, récupère tout l'historique disponible.

Gère les two-way players (ex. Ohtani) : 1 ligne par (joueur, match, position).

Alimente :
  - mlb.game_scores        : 1 ligne par (joueur, match, position)
  - mlb.game_score_details : 1 ligne par (joueur, match, stat, category)

Usage :
    python fetch_scores.py           # incrémental depuis last date - 1j
    python fetch_scores.py --full    # re-fetch complet depuis le début
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

SORARE_API = "https://api.sorare.com/graphql"
SLEEP_BETWEEN_PLAYERS = 0.2
STORE_BATCH_SIZE = 100  # flush vers la DB tous les N joueurs

PITCHER_POSITIONS = {
    "SP", "RP",
    "baseball_starting_pitcher",
    "baseball_relief_pitcher",
}


def _position_to_category(position: str | None) -> str:
    if position and position.upper() in {p.upper() for p in PITCHER_POSITIONS}:
        return "PITCHING"
    return "HITTING"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _api_post(payload: dict, headers: dict, timeout: int = 30, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            resp = requests.post(SORARE_API, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                raise RuntimeError(f"Erreur GraphQL : {data['errors']}")
            return data
        except (requests.exceptions.RequestException, RuntimeError) as exc:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"    Tentative {attempt + 1} échouée ({exc}), retry dans {wait}s...")
            time.sleep(wait)


def _load_config():
    env_path = Path(__file__).parent / ".." / ".env"
    load_dotenv(dotenv_path=env_path)
    engine = create_engine(
        f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    api_headers = {
        "Content-Type": "application/json",
        "APIKEY": os.getenv("API_KEY"),
    }
    return engine, api_headers


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Migration schéma ───────────────────────────────────────────────────────────

def _ensure_schema(engine) -> None:
    """
    Migre les tables si nécessaire.
      game_scores : PK (player_slug, game_date) — position supprimée (source de doublons).
    """
    def _col_exists(conn, table: str, col: str) -> bool:
        return conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'mlb' AND table_name = :tbl AND column_name = :col
        """), {"tbl": table, "col": col}).scalar() is not None

    def _pk_columns(conn, table: str) -> list:
        return conn.execute(text("""
            SELECT kcu.column_name
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
              ON kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema    = tc.table_schema
            WHERE tc.table_schema = 'mlb' AND tc.table_name = :tbl
              AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.ordinal_position
        """), {"tbl": table}).scalars().all()

    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE mlb.game_scores ADD COLUMN IF NOT EXISTS category TEXT"
        ))

        if _col_exists(conn, "game_scores", "position"):
            # Dédupliquer : garder le score max par (joueur, match, category)
            conn.execute(text("""
                CREATE TEMP TABLE _gs_dedup AS
                SELECT DISTINCT ON (player_slug, game_date, category)
                    player_slug, game_date, gw_int, category, score, played_in_game
                FROM mlb.game_scores
                ORDER BY player_slug, game_date, category, score DESC NULLS LAST
            """))
            conn.execute(text("TRUNCATE mlb.game_scores"))
            conn.execute(text(
                "ALTER TABLE mlb.game_scores DROP CONSTRAINT IF EXISTS game_scores_pkey"
            ))
            conn.execute(text(
                "ALTER TABLE mlb.game_scores DROP COLUMN IF EXISTS position"
            ))
            conn.execute(text(
                "ALTER TABLE mlb.game_scores ADD PRIMARY KEY (player_slug, game_date, category)"
            ))
            conn.execute(text("""
                INSERT INTO mlb.game_scores (player_slug, game_date, gw_int, category, score, played_in_game)
                SELECT player_slug, game_date, gw_int, category, score, played_in_game
                FROM _gs_dedup
            """))
            conn.execute(text("DROP TABLE _gs_dedup"))
            print("  Migration game_scores : position supprimée, doublons dédupliqués par (player, date, category)")

        # ── game_score_details ───────────────────────────────────────────────
        if "category" not in _pk_columns(conn, "game_score_details"):
            conn.execute(text(
                "UPDATE mlb.game_score_details SET category = 'UNKNOWN' WHERE category IS NULL"
            ))
            conn.execute(text(
                "ALTER TABLE mlb.game_score_details DROP CONSTRAINT IF EXISTS game_score_details_pkey"
            ))
            conn.execute(text("""
                ALTER TABLE mlb.game_score_details
                ADD CONSTRAINT game_score_details_pkey
                PRIMARY KEY (player_slug, game_date, stat, category)
            """))
            print("  Migration game_score_details : PK -> (player_slug, game_date, stat, category)")


# ── Lecture DB ─────────────────────────────────────────────────────────────────

def get_start_date(engine) -> datetime | None:
    """MAX(game_date) - 1 jour depuis mlb.game_scores. None si table vide."""
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT MAX(game_date) - INTERVAL '1 day' FROM mlb.game_scores"
        )).fetchone()
    val = row[0] if row else None
    if val is None:
        return None
    return val if val.tzinfo else val.replace(tzinfo=timezone.utc)


def get_all_player_slugs(engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT player_slug FROM mlb.players")).fetchall()
    return [r[0] for r in rows]


# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch_scores_for_player(
    slug: str,
    headers: dict,
    start_date: datetime | None,
) -> tuple[list, list]:
    """
    Retourne (scores_rows, details_rows) pour un joueur depuis start_date.
    Pagination arrêtée dès que toute une page est antérieure à start_date.
    """
    scores_rows = []
    details_rows = []
    has_next = True
    end_cursor = ""

    while has_next:
        query = f"""{{
          anyPlayer(slug: "{slug}") {{
            ... on BaseballPlayer {{
              allPlayerGameScores(after: "{end_cursor}") {{
                nodes {{
                  position
                  score
                  detailedScore {{
                    category
                    points
                    stat
                    statTyped {{ shortName }}
                    statValue
                  }}
                  anyPlayerGameStats {{ playedInGame }}
                  anyGame {{
                    date
                    so5Fixture {{ gameWeek }}
                  }}
                }}
                pageInfo {{ hasNextPage endCursor }}
              }}
            }}
          }}
        }}"""

        data = _api_post({"query": query}, headers)
        player_data = data["data"]["anyPlayer"]
        if not player_data:
            break

        nodes     = player_data["allPlayerGameScores"]["nodes"]
        page_info = player_data["allPlayerGameScores"]["pageInfo"]

        page_dates = []
        for node in nodes:
            game    = node.get("anyGame") or {}
            game_dt = _parse_dt(game.get("date"))
            if not game_dt:
                continue
            page_dates.append(game_dt)

            if start_date and game_dt < start_date:
                continue

            fixture  = game.get("so5Fixture") or {}
            gw_int   = fixture.get("gameWeek")
            played   = (node.get("anyPlayerGameStats") or {}).get("playedInGame", False)
            position = node.get("position")
            category = _position_to_category(position)

            scores_rows.append({
                "player_slug":    slug,
                "game_date":      game_dt,
                "gw_int":         gw_int,
                "category":       category,
                "score":          node.get("score"),
                "played_in_game": played,
            })

            if played:
                for detail in node.get("detailedScore") or []:
                    stat_typed      = detail.get("statTyped") or {}
                    detail_category = detail.get("category") or category
                    details_rows.append({
                        "player_slug":     slug,
                        "game_date":       game_dt,
                        "stat":            detail.get("stat"),
                        "stat_short_name": stat_typed.get("shortName"),
                        "category":        detail_category or "UNKNOWN",
                        "stat_value":      detail.get("statValue"),
                        "points":          detail.get("points"),
                    })

        # Arrêt anticipé : toute la page est avant start_date
        if start_date and page_dates and all(d < start_date for d in page_dates):
            break

        has_next   = page_info["hasNextPage"]
        end_cursor = page_info["endCursor"]

    return scores_rows, details_rows


# ── Store ──────────────────────────────────────────────────────────────────────

def store_scores(engine, all_scores: list, all_details: list) -> None:
    if not all_scores and not all_details:
        return

    def _upsert_scores(table, conn, keys, data_iter):
        rows = [dict(zip(keys, row)) for row in data_iter]
        if rows:
            stmt = pg_insert(table.table).values(rows)
            conn.execute(stmt.on_conflict_do_update(
                index_elements=["player_slug", "game_date", "category"],
                set_={"score": text("GREATEST(EXCLUDED.score, mlb.game_scores.score)")},
            ))

    def _insert_ignore_details(table, conn, keys, data_iter):
        rows = [dict(zip(keys, row)) for row in data_iter]
        if rows:
            stmt = pg_insert(table.table).values(rows).on_conflict_do_nothing()
            conn.execute(stmt)

    if all_scores:
        df = pd.DataFrame(all_scores)
        df["game_date"] = pd.to_datetime(df["game_date"], utc=True)
        with engine.begin() as conn:
            df.to_sql(
                "game_scores", con=conn, schema="mlb",
                if_exists="append", index=False,
                method=_upsert_scores, chunksize=1000,
            )
        print(f"  -> {len(df)} lignes game_scores")

    if all_details:
        df = pd.DataFrame(all_details)
        df["game_date"] = pd.to_datetime(df["game_date"], utc=True)
        with engine.begin() as conn:
            df.to_sql(
                "game_score_details", con=conn, schema="mlb",
                if_exists="append", index=False,
                method=_insert_ignore_details, chunksize=1000,
            )
        print(f"  -> {len(df)} lignes game_score_details")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    full_mode = "--full" in sys.argv
    engine, api_headers = _load_config()

    print("Vérification/migration du schéma...")
    _ensure_schema(engine)

    start_date = None if full_mode else get_start_date(engine)
    if start_date:
        print(f"Mode incrémental : matchs depuis {start_date.strftime('%Y-%m-%d %H:%M UTC')}")
    else:
        print("Mode complet : récupération de tout l'historique disponible")

    player_slugs = get_all_player_slugs(engine)
    total = len(player_slugs)
    print(f"{total} joueurs à traiter...")

    all_scores: list  = []
    all_details: list = []
    total_s = total_d = 0

    for i, slug in enumerate(player_slugs):
        s_rows, d_rows = fetch_scores_for_player(slug, api_headers, start_date)
        all_scores.extend(s_rows)
        all_details.extend(d_rows)
        time.sleep(SLEEP_BETWEEN_PLAYERS)

        if (i + 1) % 10 == 0 or i + 1 == total:
            remaining = total - (i + 1)
            print(f"  [{i+1}/{total}] {remaining} restants — {len(all_scores)} scores en attente", flush=True)

        if (i + 1) % STORE_BATCH_SIZE == 0:
            store_scores(engine, all_scores, all_details)
            total_s += len(all_scores)
            total_d += len(all_details)
            all_scores = []
            all_details = []

    # Flush restant
    store_scores(engine, all_scores, all_details)
    total_s += len(all_scores)
    total_d += len(all_details)

    print(f"\nTerminé — {total_s} scores, {total_d} détails enregistrés.")
