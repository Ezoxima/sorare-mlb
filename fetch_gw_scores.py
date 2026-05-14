"""
fetch_gw_scores.py
------------------
Récupère toutes les données de score pour l'ensemble des matchs d'une gameweek MLB.

Stratégie API :
  1. so5 > featuredSo5Fixtures  → slug + IDs de matchs de la GW
  2. anyGame(id: $id)           → playerGameScores complets par match (1 appel/match)

Alimente :
  - mlb.game_scores        : 1 ligne par (joueur, match)
  - mlb.game_score_details : 1 ligne par (joueur, match, stat)

Par défaut cible la prochaine fixture CLASSIC composable.
On peut passer un slug explicite : python fetch_gw_scores.py baseball-15-18-may-2026

Usage :
    python fetch_gw_scores.py
    python fetch_gw_scores.py <fixture-slug>
    python fetch_gw_scores.py <fixture-slug> DAILY
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

SORARE_API = "https://api.sorare.com/graphql"
SLEEP_BETWEEN_CALLS = 0.15   # secondes entre chaque appel match


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


# ── Fetch fixture ──────────────────────────────────────────────────────────────

def fetch_fixture(slug: str | None, gw_type: str, headers: dict) -> dict:
    """
    Retourne { slug, gw_int, games: [{id, date, home_team, away_team}] }.
    Si slug est None, prend la première fixture composable du type donné.

    2 appels nécessaires : anyGames interdit dans une liste de fixtures.
    """
    # Appel 1 : liste des fixtures pour trouver le bon slug
    q_list = """
    {
      so5 {
        featuredSo5Fixtures(sport: BASEBALL, first: 20, eventType: %s) {
          slug
          gameWeek
          canCompose
        }
      }
    }
    """ % gw_type

    data = _api_post({"query": q_list}, headers)
    fixtures = data["data"]["so5"]["featuredSo5Fixtures"]

    if slug:
        target = next((f for f in fixtures if f["slug"] == slug), None)
        if not target:
            raise ValueError(f"Fixture '{slug}' introuvable parmi les fixtures {gw_type} disponibles.")
    else:
        composable = [f for f in fixtures if f["canCompose"]]
        if not composable:
            raise ValueError(f"Aucune fixture {gw_type} composable trouvée.")
        target = composable[0]

    # Appel 2 : matchs de la fixture ciblée
    q_games = """
    {
      so5 {
        so5Fixture(sport: BASEBALL, slug: "%s", eventType: %s) {
          anyGames {
            id
            date
            homeTeam { slug name }
            awayTeam { slug name }
          }
        }
      }
    }
    """ % (target["slug"], gw_type)

    data2 = _api_post({"query": q_games}, headers)
    games  = data2["data"]["so5"]["so5Fixture"]["anyGames"]

    return {
        "slug":   target["slug"],
        "gw_int": target["gameWeek"],
        "games":  games,
    }


# ── Fetch scores par match ─────────────────────────────────────────────────────

GAME_QUERY = """
query($id: ID!) {
  anyGame(id: $id) {
    id
    statusTyped
    homeScore
    awayScore
    playerGameScores {
      score
      position
      anyPlayer { slug displayName }
      anyPlayerGameStats { playedInGame }
      detailedScore {
        category
        stat
        statValue
        points
        statTyped { shortName }
      }
    }
  }
}
"""


def fetch_game_scores(game_id: str, headers: dict) -> dict:
    data = _api_post({"query": GAME_QUERY, "variables": {"id": game_id}}, headers)
    return data["data"]["anyGame"]


# ── Flatten ────────────────────────────────────────────────────────────────────

def flatten_to_rows(fixture: dict, game_meta: dict, game_data: dict) -> tuple[list, list]:
    """
    Retourne (score_rows, detail_rows) pour un match.
    score_rows   → mlb.game_scores
    detail_rows  → mlb.game_score_details
    """
    score_rows  = []
    detail_rows = []

    gw_int    = fixture["gw_int"]
    game_date = game_meta["date"]
    played_in = game_data.get("anyPlayerGameStats", {}) or {}

    for ps in game_data.get("playerGameScores") or []:
        player = ps.get("anyPlayer") or {}
        slug   = player.get("slug")
        if not slug:
            continue

        played = (ps.get("anyPlayerGameStats") or {}).get("playedInGame", False)

        score_rows.append({
            "player_slug":    slug,
            "game_date":      game_date,
            "gw_int":         gw_int,
            "position":       ps.get("position"),
            "score":          ps.get("score"),
            "played_in_game": played,
        })

        for stat in ps.get("detailedScore") or []:
            detail_rows.append({
                "player_slug":     slug,
                "game_date":       game_date,
                "stat":            stat.get("stat"),
                "stat_short_name": (stat.get("statTyped") or {}).get("shortName"),
                "category":        stat.get("category"),
                "stat_value":      stat.get("statValue"),
                "points":          stat.get("points"),
            })

    return score_rows, detail_rows


# ── Store ──────────────────────────────────────────────────────────────────────

def store(engine, all_score_rows: list, all_detail_rows: list, gw_int: int) -> None:
    if not all_score_rows:
        print("  Aucune donnée à enregistrer.")
        return

    # Normaliser game_date en UTC avant dedup (l'API renvoie parfois des offsets
    # différents pour le même instant, ex. +01:00 vs +00:00, ce qui trompe pandas)
    df_scores = pd.DataFrame(all_score_rows)
    df_scores["game_date"] = pd.to_datetime(df_scores["game_date"], utc=True)
    df_scores = df_scores.drop_duplicates(subset=["player_slug", "game_date"])

    df_details = pd.DataFrame(all_detail_rows)
    df_details["game_date"] = pd.to_datetime(df_details["game_date"], utc=True)
    df_details = df_details.drop_duplicates(subset=["player_slug", "game_date", "stat"])

    # ON CONFLICT DO NOTHING : un même match physique peut apparaître dans plusieurs
    # fixtures Sorare (ex. Opening Series + GW régulière). On skip les doublons.
    def _insert_ignore(table, conn, keys, data_iter):
        rows = [dict(zip(keys, row)) for row in data_iter]
        if rows:
            stmt = pg_insert(table.table).values(rows).on_conflict_do_nothing()
            conn.execute(stmt)

    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM mlb.game_score_details gsd
            USING mlb.game_scores gs
            WHERE gsd.player_slug = gs.player_slug
              AND gsd.game_date   = gs.game_date
              AND gs.gw_int       = :gw_int
        """), {"gw_int": gw_int})
        conn.execute(text(
            "DELETE FROM mlb.game_scores WHERE gw_int = :gw_int"
        ), {"gw_int": gw_int})
        df_scores.to_sql(
            "game_scores", con=conn, schema="mlb",
            if_exists="append", index=False, method=_insert_ignore, chunksize=1000,
        )
        df_details.to_sql(
            "game_score_details", con=conn, schema="mlb",
            if_exists="append", index=False, method=_insert_ignore, chunksize=1000,
        )

    print(f"  {len(df_scores)} lignes dans mlb.game_scores")
    print(f"  {len(df_details)} lignes dans mlb.game_score_details")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine, api_headers = _load_config()

    fixture_slug = sys.argv[1] if len(sys.argv) > 1 else None
    gw_type      = sys.argv[2] if len(sys.argv) > 2 else "CLASSIC"

    print(f"Recherche fixture {gw_type}{' : ' + fixture_slug if fixture_slug else ' (prochaine composable)'}...")
    fixture = fetch_fixture(fixture_slug, gw_type, api_headers)
    games   = fixture["games"]
    print(f"GW{fixture['gw_int']} — {fixture['slug']} — {len(games)} matchs")

    all_score_rows  = []
    all_detail_rows = []
    game_dates      = []
    total = len(games)

    for i, game_meta in enumerate(games):
        gid  = game_meta["id"]
        home = game_meta["homeTeam"]["name"]
        away = game_meta["awayTeam"]["name"]
        print(f"  [{i+1}/{total}] {away} @ {home}", end="", flush=True)

        game_data = fetch_game_scores(gid, api_headers)
        status    = game_data["statusTyped"]

        if status == "scheduled":
            print(f" — ignoré [scheduled]")
            time.sleep(SLEEP_BETWEEN_CALLS)
            continue

        scores = game_data.get("playerGameScores") or []
        print(f" — {len(scores)} joueurs [{status}]")

        s_rows, d_rows = flatten_to_rows(fixture, game_meta, game_data)
        all_score_rows.extend(s_rows)
        all_detail_rows.extend(d_rows)
        game_dates.append(game_meta["date"])

        time.sleep(SLEEP_BETWEEN_CALLS)

    print(f"\nTotal : {len(all_score_rows)} lignes joueur/match, {len(all_detail_rows)} lignes stats")
    print("Enregistrement en base...")
    store(engine, all_score_rows, all_detail_rows, fixture["gw_int"])
    print("Terminé !")
