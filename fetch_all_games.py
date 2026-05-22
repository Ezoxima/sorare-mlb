"""
fetch_all_games.py
------------------
Récupère TOUS les matchs terminés depuis GW1 jusqu'à la GW la plus récente,
et les insère dans mlb.games + mlb.game_innings via upsert (idempotent).

Utilise les slugs de fixture stockés dans mlb.gameweeks.
Ne re-fetch pas les GWs déjà complètes (toutes lignes scored=True présentes).

Usage :
    python fetch_all_games.py           # GWs manquantes uniquement
    python fetch_all_games.py --full    # refait toutes les GWs (force refresh)
    python fetch_all_games.py --from 50 # depuis la GW 50 uniquement
"""

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from fetch_game_infos import fetch_games, flatten as _flatten

SORARE_API          = "https://api.sorare.com/graphql"
SLEEP_BETWEEN_GW    = 0.5   # politesse API


# ── Config ─────────────────────────────────────────────────────────────────────

def _load_config():
    load_dotenv(Path(__file__).parent / ".." / ".env")
    engine = create_engine(
        f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    headers = {
        "Content-Type": "application/json",
        "APIKEY": os.getenv("API_KEY"),
    }
    return engine, headers


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _gws_in_db(engine) -> set[int]:
    """GW ints déjà présents dans mlb.games."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT gw_int FROM mlb.games")).fetchall()
    return {r[0] for r in rows}


def _all_gw_slugs(engine) -> list[tuple[int, str]]:
    """Retourne [(gw_int, gw_slug), ...] triés par gw_int depuis mlb.gameweeks CLASSIC."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT gw_int, gw_slug FROM mlb.gameweeks "
            "WHERE gw_type = 'CLASSIC' ORDER BY gw_int"
        )).fetchall()
    return [(r[0], r[1]) for r in rows]


# ── Upsert ─────────────────────────────────────────────────────────────────────

def _upsert_games(engine, game_rows: list, inning_rows: list, gw_int: int) -> tuple[int, int]:
    """Upsert dans mlb.games et mlb.game_innings. Retourne (n_games, n_innings)."""
    if not game_rows:
        return 0, 0

    meta = MetaData()
    meta.reflect(bind=engine, schema="mlb", only=["games", "game_innings"])
    tbl_games   = meta.tables["mlb.games"]
    tbl_innings = meta.tables["mlb.game_innings"]

    # Déduplication sans pandas — évite la conversion None→NaN→float qui plante INTEGER
    seen_ids: set[str] = set()
    deduped_games = []
    for row in game_rows:
        gid = row["game_id"]
        if gid not in seen_ids:
            seen_ids.add(gid)
            deduped_games.append(row)

    with engine.begin() as conn:
        for rec in deduped_games:
            stmt = (
                pg_insert(tbl_games)
                .values(**rec)
                .on_conflict_do_update(
                    index_elements=["game_id"],
                    set_={k: getattr(pg_insert(tbl_games).excluded, k)
                          for k in rec if k != "game_id"},
                )
            )
            try:
                conn.execute(stmt)
            except Exception as e:
                print(f"\n  [ERREUR] game_id={rec.get('game_id')}: {e}")
                for k, v in rec.items():
                    print(f"    {k}: {v!r} ({type(v).__name__})")
                raise

        if inning_rows:
            seen_inn: set[tuple] = set()
            deduped_inn = []
            for row in inning_rows:
                key = (row["game_id"], row["inning_number"])
                if key not in seen_inn:
                    seen_inn.add(key)
                    deduped_inn.append(row)

            for rec in deduped_inn:
                stmt = (
                    pg_insert(tbl_innings)
                    .values(**rec)
                    .on_conflict_do_nothing()
                )
                try:
                    conn.execute(stmt)
                except Exception as e:
                    print(f"\n  [ERREUR inning] game_id={rec.get('game_id')}: {e}")
                    for k, v in rec.items():
                        print(f"    {k}: {v!r} ({type(v).__name__})")
                    raise

    return len(deduped_games), len(inning_rows)


# ── Main ───────────────────────────────────────────────────────────────────────

def run(engine, headers, full_mode: bool = False, from_gw: int = 1):
    all_gws    = _all_gw_slugs(engine)
    done_gws   = _gws_in_db(engine) if not full_mode else set()

    to_fetch = [
        (gw_int, slug) for gw_int, slug in all_gws
        if gw_int >= from_gw and gw_int not in done_gws
    ]

    print(f"  {len(all_gws)} GWs connues — {len(done_gws)} déjà en base — "
          f"{len(to_fetch)} à récupérer")

    if not to_fetch:
        print("  Tout est déjà à jour.")
        return

    total_games = total_innings = 0

    for idx, (gw_int, slug) in enumerate(to_fetch):
        print(f"  GW{gw_int} ({slug})...", end=" ", flush=True)
        try:
            raw = fetch_games(slug, "CLASSIC", headers)
        except Exception as exc:
            print(f"ERREUR : {exc}")
            time.sleep(2)
            continue

        n_total  = sum(1 for g in raw if g)
        n_scored = sum(1 for g in raw if g and g.get("scored"))

        game_rows, inning_rows = _flatten(raw, gw_int, slug)
        n_g, n_i = _upsert_games(engine, game_rows, inning_rows, gw_int)
        total_games   += n_g
        total_innings += n_i

        print(f"{n_scored}/{n_total} matchs termines -> {n_g} upsertes")
        time.sleep(SLEEP_BETWEEN_GW)

    print(f"\n  Total : {total_games} matchs, {total_innings} manches upsertés.")


if __name__ == "__main__":
    full_mode = "--full" in sys.argv
    from_gw   = 1
    for arg in sys.argv[1:]:
        if arg.startswith("--from"):
            parts = arg.split()
            if len(parts) == 2:
                from_gw = int(parts[1])
        elif arg.isdigit():
            from_gw = int(arg)

    # Support "--from 50" ou "--from=50"
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--from" and i < len(sys.argv):
            try:
                from_gw = int(sys.argv[i + 1])
            except (IndexError, ValueError):
                pass
        elif arg.startswith("--from="):
            try:
                from_gw = int(arg.split("=", 1)[1])
            except ValueError:
                pass

    mode_str = "complet (force refresh)" if full_mode else f"incrémental (depuis GW{from_gw})"
    print(f"[Games] Récupération historique matchs MLB — mode {mode_str}...")
    engine, api_headers = _load_config()
    run(engine, api_headers, full_mode=full_mode, from_gw=from_gw)
