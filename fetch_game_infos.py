"""
fetch_game_infos.py
-------------------
Récupère les données box score pour tous les matchs d'une gameweek MLB.

Un seul appel API suffit grâce au fragment GameOfBaseball sur anyGames.

Alimente :
  - mlb.games        : 1 ligne par match (scores, hits, erreurs, pitchers, stade…)
  - mlb.game_innings : 1 ligne par (match, manche)

Seuls les matchs terminés (scored=True) sont insérés.
Idempotent : supprime les données existantes de la GW avant réinsertion.

Usage :
    python fetch_game_infos.py
    python fetch_game_infos.py <fixture-slug>
    python fetch_game_infos.py <fixture-slug> DAILY
"""

import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SORARE_API = "https://api.sorare.com/graphql"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _api_post(payload: dict, headers: dict, timeout: int = 30, max_retries: int = 3) -> dict:
    import time
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


def _slug(node: dict | None) -> str | None:
    return node.get("slug") if node else None


# ── Fetch ──────────────────────────────────────────────────────────────────────

def _resolve_fixture_slug(slug: str | None, gw_type: str, headers: dict) -> tuple[str, int]:
    """Retourne (fixture_slug, gw_int) — cherche la prochaine composable si slug est None."""
    query = """
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

    data = _api_post({"query": query}, headers)
    fixtures = data["data"]["so5"]["featuredSo5Fixtures"]

    if slug:
        target = next((f for f in fixtures if f["slug"] == slug), None)
        if not target:
            raise ValueError(f"Fixture '{slug}' introuvable parmi les fixtures {gw_type}.")
    else:
        composable = [f for f in fixtures if f["canCompose"]]
        if not composable:
            raise ValueError(f"Aucune fixture {gw_type} composable trouvée.")
        target = composable[0]

    return target["slug"], target["gameWeek"]


def fetch_games(fixture_slug: str, gw_type: str, headers: dict) -> list[dict]:
    """Retourne la liste brute des matchs (fragment GameOfBaseball)."""
    query = """
    {
      so5 {
        so5Fixture(sport: BASEBALL, slug: "%s", eventType: %s) {
          anyGames {
            ... on GameOfBaseball {
              id
              date
              homeTeam { slug name }
              awayTeam { slug name }
              awayHits
              awayErrors
              awayProbablePitcher { slug }
              awayScore
              competition { slug }
              homeErrors
              homeHits
              homeProbablePitcher { slug }
              homeScore
              inning { number }
              losingPitcher { slug }
              scored
              scoresByInning { awayScore homeScore periodNumber }
              statusTyped
              venue
              winner { slug }
              winningPitcher { slug }
            }
          }
        }
      }
    }
    """ % (fixture_slug, gw_type)

    data = _api_post({"query": query}, headers)
    return data["data"]["so5"]["so5Fixture"]["anyGames"]


# ── Flatten ────────────────────────────────────────────────────────────────────

_INT_MAX = 2_147_483_647
_INT_MIN = -2_147_483_648


def _safe_int(val, label: str = "") -> int | None:
    """Retourne val casté en int Python, ou None si hors bornes INTEGER PostgreSQL."""
    if val is None:
        return None
    try:
        v = int(val)
    except (TypeError, ValueError):
        return None
    if not (_INT_MIN <= v <= _INT_MAX):
        print(f"  [WARN] {label}={v!r} hors limites INTEGER → ignoré")
        return None
    return v


def flatten(raw_games: list, gw_int: int, fixture_slug: str,
            include_unscored: bool = False) -> tuple[list, list]:
    """
    Retourne (game_rows, inning_rows).
    Par défaut ignore les matchs non encore joués (scored=False).
    include_unscored=True : inclut tous les matchs (date, équipes, probable pitchers).
    """
    game_rows   = []
    inning_rows = []

    for g in raw_games:
        if not g:
            continue
        if not g.get("scored") and not include_unscored:
            continue

        game_id = g["id"].split(":")[-1]

        game_rows.append({
            "game_id":               game_id,
            "game_date":             g["date"],
            "gw_int":                gw_int,
            "fixture_slug":          fixture_slug,
            "home_team_slug":        _slug(g.get("homeTeam")),
            "away_team_slug":        _slug(g.get("awayTeam")),
            "home_score":            _safe_int(g.get("homeScore"),  f"game {game_id} home_score"),
            "away_score":            _safe_int(g.get("awayScore"),  f"game {game_id} away_score"),
            "home_hits":             _safe_int(g.get("homeHits"),   f"game {game_id} home_hits"),
            "away_hits":             _safe_int(g.get("awayHits"),   f"game {game_id} away_hits"),
            "home_errors":           _safe_int(g.get("homeErrors"), f"game {game_id} home_errors"),
            "away_errors":           _safe_int(g.get("awayErrors"), f"game {game_id} away_errors"),
            "home_probable_pitcher": _slug(g.get("homeProbablePitcher")),
            "away_probable_pitcher": _slug(g.get("awayProbablePitcher")),
            "winning_pitcher":       _slug(g.get("winningPitcher")),
            "losing_pitcher":        _slug(g.get("losingPitcher")),
            "winner_slug":           _slug(g.get("winner")),
            "competition_slug":      _slug(g.get("competition")),
            "inning":                _safe_int((g.get("inning") or {}).get("number"), f"game {game_id} inning"),
            "scored":                g.get("scored"),
            "status":                g.get("statusTyped"),
            "venue":                 g.get("venue"),
        })

        for inn in g.get("scoresByInning") or []:
            period = _safe_int(inn["periodNumber"], f"game {game_id} periodNumber")
            if period is None:
                continue  # ne pas insérer une manche avec PK NULL
            inning_rows.append({
                "game_id":       game_id,
                "inning_number": period,
                "home_score":    _safe_int(inn["homeScore"], f"game {game_id} inn{period} home"),
                "away_score":    _safe_int(inn["awayScore"], f"game {game_id} inn{period} away"),
            })

    return game_rows, inning_rows


# ── Store ──────────────────────────────────────────────────────────────────────

def store(engine, game_rows: list, inning_rows: list, gw_int: int) -> None:
    if not game_rows:
        print("  Aucun match à enregistrer.")
        return

    with engine.begin() as conn:
        # ON DELETE CASCADE sur game_innings supprime les manches automatiquement
        conn.execute(text("DELETE FROM mlb.games WHERE gw_int = :gw"), {"gw": gw_int})

    df_games = pd.DataFrame(game_rows).drop_duplicates(subset=["game_id"])
    df_games.to_sql("games", engine, schema="mlb", if_exists="append", index=False)
    print(f"  {len(df_games)} matchs dans mlb.games")

    df_innings = pd.DataFrame(inning_rows).drop_duplicates(subset=["game_id", "inning_number"])
    df_innings.to_sql("game_innings", engine, schema="mlb", if_exists="append", index=False)
    print(f"  {len(df_innings)} manches dans mlb.game_innings")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine, api_headers = _load_config()

    fixture_slug_arg = sys.argv[1] if len(sys.argv) > 1 else None
    gw_type          = sys.argv[2] if len(sys.argv) > 2 else "CLASSIC"

    print(f"Résolution fixture {gw_type}{' : ' + fixture_slug_arg if fixture_slug_arg else ' (prochaine composable)'}...")
    fixture_slug, gw_int = _resolve_fixture_slug(fixture_slug_arg, gw_type, api_headers)
    print(f"GW{gw_int} — {fixture_slug}")

    print("Récupération des matchs...")
    raw_games  = fetch_games(fixture_slug, gw_type, api_headers)
    n_total    = len([g for g in raw_games if g])
    n_scored   = len([g for g in raw_games if g and g.get("scored")])
    n_pending  = n_total - n_scored
    print(f"  {n_total} matchs — {n_scored} terminés, {n_pending} à venir/en cours")

    game_rows, inning_rows = flatten(raw_games, gw_int, fixture_slug)

    print("Enregistrement en base...")
    store(engine, game_rows, inning_rows, gw_int)
    print("Terminé !")
