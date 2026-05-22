"""
init_ref_data.py
----------------
Charge les données de référence MLB dans PostgreSQL :
  - mlb.teams        : toutes les équipes actives
  - mlb.players      : tous les joueurs actifs (positions mappées)
  - mlb.player_injuries : blessures en cours
  - mlb.gameweeks    : GW Classic + Daily

Long à la première exécution (1 appel API par joueur pour les infos).

Usage :
    python init_ref_data.py
"""

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SORARE_API = "https://api.sorare.com/graphql"
POS_MAP_FILE = Path(__file__).parent / "infos" / "poste_mlb.json"


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


def _load_position_maps() -> tuple[dict, dict]:
    pos_data = json.loads(POS_MAP_FILE.read_text(encoding="utf-8"))
    map_exact = dict(zip(pos_data["position"], pos_data["exact_position"]))
    map_agg   = dict(zip(pos_data["position"], pos_data["agg_position"]))
    return map_exact, map_agg


def _map_positions(raw_positions: list, map_exact: dict, map_agg: dict) -> dict:
    """
    Prend la liste anyPositions (max 3), retourne les colonnes position_* et agg_position_*.
    Les agg positions dupliquées sont remplacées par None (ex: 2B + SS → MI, MI → MI, None).
    """
    exact = [map_exact.get(p) for p in raw_positions[:3]]
    exact += [None] * (3 - len(exact))

    seen_agg = set()
    agg = []
    for p in raw_positions[:3]:
        a = map_agg.get(p)
        if a and a not in seen_agg:
            seen_agg.add(a)
            agg.append(a)
        else:
            agg.append(None)
    agg += [None] * (3 - len(agg))

    return {
        "position_1":    exact[0],
        "position_2":    exact[1],
        "position_3":    exact[2],
        "agg_position_1": agg[0],
        "agg_position_2": agg[1],
        "agg_position_3": agg[2],
    }


def _truncate(engine, *tables: str) -> None:
    with engine.begin() as conn:
        for table in tables:
            conn.execute(text(f"TRUNCATE {table} CASCADE"))


# ── Teams ──────────────────────────────────────────────────────────────────────

def fetch_teams(headers: dict) -> pd.DataFrame:
    query = """{
      teams(sport: BASEBALL) {
        nodes {
          slug
          name
          code
          pictureUrl
        }
      }
    }"""
    data = _api_post({"query": query}, headers)
    nodes = data["data"]["teams"]["nodes"]
    return pd.DataFrame([{
        "team_slug":    n["slug"],
        "team_name":    n["name"],
        "team_code":    n.get("code"),
        "picture_url":  n.get("pictureUrl"),
    } for n in nodes])


def store_teams(engine, df: pd.DataFrame) -> None:
    _truncate(engine, "mlb.teams")
    df.to_sql("teams", engine, schema="mlb", if_exists="append", index=False)
    print(f"  {len(df)} équipes enregistrées dans mlb.teams")

    parquet_path = Path(__file__).parent / "data" / "teams.parquet"
    df[["team_slug", "team_code"]].to_parquet(parquet_path, index=False)
    print(f"  Export → {parquet_path}")


# ── Players ────────────────────────────────────────────────────────────────────

def fetch_player_slugs_by_team(team_slugs: list, headers: dict) -> list[dict]:
    """Retourne [{slug, team_slug}, ...] pour tous les joueurs actifs."""
    all_players = []
    total = len(team_slugs)

    for i, team_slug in enumerate(team_slugs):
        has_next = True
        end_cursor = ""

        while has_next:
            query = f"""{{
              team(slug: "{team_slug}") {{
                activePlayers(after: "{end_cursor}") {{
                  nodes {{ slug }}
                  pageInfo {{ hasNextPage endCursor }}
                }}
              }}
            }}"""
            data = _api_post({"query": query}, headers)
            team_data = data["data"]["team"]["activePlayers"]

            for node in team_data["nodes"]:
                all_players.append({"player_slug": node["slug"], "team_slug": team_slug})

            has_next = team_data["pageInfo"]["hasNextPage"]
            end_cursor = team_data["pageInfo"]["endCursor"]

        remaining = total - (i + 1)
        if remaining % 5 == 0:
            print(f"    {remaining} équipes restantes...")

    return all_players


def fetch_player_details(slug: str, headers: dict) -> dict:
    query = f"""{{
      anyPlayer(slug: "{slug}") {{
        ... on BaseballPlayer {{
          slug
          displayName
          age
          activeClub {{
            slug
          }}
          country {{
            name
          }}
          batHand
          anyPositions
          appearances
          seasonAppearances
          shirtNumber
          nextClassicFixtureProjectedScore
          injuries {{
            active
            details
            expectedEndDate
            kind
            status
          }}
          averageScore(type: SEASON_AVERAGE_SCORE)
        }}
      }}
    }}"""
    data = _api_post({"query": query}, headers)
    return data["data"]["anyPlayer"]


def fetch_and_store_players(engine, team_slugs: list, headers: dict) -> None:
    map_exact, map_agg = _load_position_maps()

    print(f"  Récupération des slugs joueurs ({len(team_slugs)} équipes)...")
    player_refs = fetch_player_slugs_by_team(team_slugs, headers)
    team_by_slug = {p["player_slug"]: p["team_slug"] for p in player_refs}
    player_slugs = list(team_by_slug.keys())
    print(f"  {len(player_slugs)} joueurs actifs trouvés")

    players_rows = []
    injuries_rows = []
    total = len(player_slugs)

    for i, slug in enumerate(player_slugs):
        remaining = total - (i + 1)
        if remaining % 50 == 0:
            print(f"    {remaining} joueurs restants...")

        p = fetch_player_details(slug, headers)
        if not p:
            continue

        positions = p.get("anyPositions") or []
        pos_cols = _map_positions(positions, map_exact, map_agg)

        avg_score = p.get("averageScore")
        shirt = p.get("shirtNumber")

        next_gw_score = p.get("nextClassicFixtureProjectedScore")
        active_club = p.get("activeClub") or {}
        players_rows.append({
            "player_slug":               p["slug"],
            "display_name":              p["displayName"],
            "age":                       p.get("age"),
            "team_slug":                 active_club.get("slug") or team_by_slug.get(slug),
            "country":                   p["country"]["name"] if p.get("country") else None,
            "bat_hand":                  p.get("batHand"),
            "shirt_number":              shirt,
            "appearances":               p.get("appearances"),
            "season_appearances":        p.get("seasonAppearances"),
            "avg_score_season":          float(avg_score) if avg_score is not None else None,
            "next_gw_projected_score":   float(next_gw_score) if next_gw_score is not None else None,
            **pos_cols,
        })

        injuries = p.get("injuries") or []
        if injuries:
            inj = injuries[0]
            end_date = inj.get("expectedEndDate")
            injuries_rows.append({
                "player_slug":      slug,
                "active":           inj.get("active"),
                "kind":             inj.get("kind"),
                "details":          inj.get("details"),
                "status":           inj.get("status"),
                "expected_end_date": end_date[:10] if end_date else None,
            })

    _truncate(engine, "mlb.player_injuries", "mlb.players")
    df_players = pd.DataFrame(players_rows)
    df_players.to_sql("players", engine, schema="mlb", if_exists="append", index=False)
    print(f"  {len(df_players)} joueurs enregistrés dans mlb.players")

    if injuries_rows:
        df_injuries = pd.DataFrame(injuries_rows)
        df_injuries.to_sql("player_injuries", engine, schema="mlb", if_exists="append", index=False)
        print(f"  {len(df_injuries)} blessures enregistrées dans mlb.player_injuries")
    else:
        print("  Aucune blessure active")


# ── Gameweeks ──────────────────────────────────────────────────────────────────

def fetch_gameweeks(gw_type: str, headers: dict) -> pd.DataFrame:
    query = f"""{{
      so5 {{
        featuredSo5Fixtures(sport: BASEBALL first: 1000 eventType: {gw_type}) {{
          gameWeek
          id
          slug
          canCompose
          cutOffDate
          endDate
        }}
      }}
    }}"""
    data = _api_post({"query": query}, headers)
    fixtures = data["data"]["so5"]["featuredSo5Fixtures"]

    rows = []
    for f in fixtures:
        rows.append({
            "gw_id":         f["id"].split(":")[-1],
            "gw_int":        f["gameWeek"],
            "gw_slug":       f["slug"],
            "gw_type":       gw_type,
            "gw_upcoming":   f["canCompose"],
            "gw_begin_date": f["cutOffDate"],
            "gw_end_date":   f["endDate"],
        })
    return pd.DataFrame(rows)


def store_gameweeks(engine, df: pd.DataFrame) -> None:
    gw_type = df["gw_type"].iloc[0]
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM mlb.gameweeks WHERE gw_type = '{gw_type}'"))
    df.to_sql("gameweeks", engine, schema="mlb", if_exists="append", index=False)
    print(f"  {len(df)} gameweeks {gw_type} enregistrées dans mlb.gameweeks")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine, api_headers = _load_config()

    print("Chargement des équipes...")
    df_teams = fetch_teams(api_headers)
    store_teams(engine, df_teams)

    print("Chargement des joueurs (long)...")
    fetch_and_store_players(engine, df_teams["team_slug"].tolist(), api_headers)

    print("Chargement des gameweeks CLASSIC...")
    df_classic = fetch_gameweeks("CLASSIC", api_headers)
    store_gameweeks(engine, df_classic)

    print("Chargement des gameweeks DAILY...")
    df_daily = fetch_gameweeks("DAILY", api_headers)
    store_gameweeks(engine, df_daily)

    print("Terminé !")
