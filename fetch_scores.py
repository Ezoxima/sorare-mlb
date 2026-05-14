"""
fetch_scores.py
---------------
Récupère l'historique des scores MLB par joueur (API allPlayerGameScores)
et alimente :
  - mlb.game_scores        : 1 ligne par (joueur, match)
  - mlb.game_score_details : 1 ligne par (joueur, match, stat) — matchs joués uniquement

Cible : joueurs uniques présents dans mlb.gallery_players.

Long à la première exécution (1 appel API paginé par joueur).

Usage :
    python fetch_scores.py
"""

import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SORARE_API = "https://api.sorare.com/graphql"


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


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")


# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch_scores_for_player(slug: str, headers: dict) -> tuple[list, list]:
    """
    Retourne (scores_rows, details_rows) pour un joueur.
    details_rows ne contient que les matchs joués (played_in_game = True).
    """
    scores_rows = []
    details_rows = []
    has_next = True
    end_cursor = ""
    page = 0

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
                    statTyped {{
                      shortName
                    }}
                    statValue
                    totalScore
                  }}
                  anyPlayerGameStats {{
                    playedInGame
                  }}
                  anyGame {{
                    date
                    so5Fixture {{
                      gameWeek
                    }}
                  }}
                }}
                pageInfo {{
                  hasNextPage
                  endCursor
                }}
              }}
            }}
          }}
        }}"""

        data = _api_post({"query": query}, headers)
        player_data = data["data"]["anyPlayer"]

        if not player_data:
            break

        nodes = player_data["allPlayerGameScores"]["nodes"]
        page_info = player_data["allPlayerGameScores"]["pageInfo"]
        page += 1

        for node in nodes:
            game = node.get("anyGame") or {}
            game_date = _parse_date(game.get("date"))
            if not game_date:
                continue

            fixture = game.get("so5Fixture") or {}
            gw_int = fixture.get("gameWeek")

            stats = node.get("anyPlayerGameStats") or {}
            played = stats.get("playedInGame", False)

            scores_rows.append({
                "player_slug":    slug,
                "game_date":      game_date,
                "gw_int":         gw_int,
                "position":       node.get("position"),
                "score":          node.get("score"),
                "played_in_game": played,
            })

            if played:
                for detail in node.get("detailedScore") or []:
                    stat_typed = detail.get("statTyped") or {}
                    details_rows.append({
                        "player_slug":     slug,
                        "game_date":       game_date,
                        "stat":            detail.get("stat"),
                        "stat_short_name": stat_typed.get("shortName"),
                        "category":        detail.get("category"),
                        "stat_value":      detail.get("statValue"),
                        "points":          detail.get("points"),
                    })

        has_next = page_info["hasNextPage"]
        end_cursor = page_info["endCursor"]

    return scores_rows, details_rows


# ── Store ──────────────────────────────────────────────────────────────────────

def store_scores(engine, all_scores: list, all_details: list) -> None:
    slugs = list({r["player_slug"] for r in all_scores})

    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM mlb.game_score_details WHERE player_slug = ANY(:slugs)"
        ), {"slugs": slugs})
        conn.execute(text(
            "DELETE FROM mlb.game_scores WHERE player_slug = ANY(:slugs)"
        ), {"slugs": slugs})

    if all_scores:
        df_scores = pd.DataFrame(all_scores).drop_duplicates(subset=["player_slug", "game_date"])
        df_scores.to_sql("game_scores", engine, schema="mlb", if_exists="append", index=False)
        print(f"  {len(df_scores)} lignes dans mlb.game_scores")

    if all_details:
        df_details = pd.DataFrame(all_details).drop_duplicates(subset=["player_slug", "game_date", "stat"])
        df_details.to_sql("game_score_details", engine, schema="mlb", if_exists="append", index=False)
        print(f"  {len(df_details)} lignes dans mlb.game_score_details")


# ── Main ───────────────────────────────────────────────────────────────────────

def get_gallery_slugs(engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT player_slug FROM mlb.gallery_players WHERE NOT sealed"
        )).fetchall()
    return [r[0] for r in rows]


if __name__ == "__main__":
    engine, api_headers = _load_config()

    player_slugs = get_gallery_slugs(engine)
    total = len(player_slugs)
    print(f"Récupération des scores pour {total} joueurs de la galerie...")

    all_scores = []
    all_details = []

    for i, slug in enumerate(player_slugs):
        remaining = total - (i + 1)
        print(f"  [{i+1}/{total}] {slug} ({remaining} restants)")
        s_rows, d_rows = fetch_scores_for_player(slug, api_headers)
        all_scores.extend(s_rows)
        all_details.extend(d_rows)

    print("Enregistrement en base...")
    store_scores(engine, all_scores, all_details)
    print("Terminé !")
