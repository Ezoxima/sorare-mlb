"""
update_data.py
--------------
Mise à jour incrémentale de toutes les données MLB.

  [1/6] Galerie          → full refresh (prix, prochain match, etc. changent)
  [2/6] Game infos       → uniquement les GW absentes de mlb.games
  [3/6] Game scores/GW   → uniquement les GW absentes de mlb.game_scores
  [4/6] Nouveaux joueurs → historique complet pour les joueurs galerie sans données
  [5/6] Précalcul stats  → mlb.gallery_stats_agg (5/10/20 matchs, passe unique)
  [6/6] Prix cartes      → full refresh (prix volatils)

Usage :
    python update_data.py
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ── Imports métier des scripts spécialisés ─────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from fetch_game_infos import fetch_games, flatten as _flatten_games, store as _store_games
from fetch_gw_scores  import fetch_game_scores as _fetch_game_scores, \
                             flatten_to_rows as _flatten_gw_scores, \
                             store as _store_gw_scores
from fetch_scores     import fetch_scores_for_player, store_scores, get_gallery_slugs
from fetch_prices     import fetch_prices_for_player, store_prices, _load_fx_rates

SORARE_API = "https://api.sorare.com/graphql"
SLEEP      = 0.2    # entre les appels fixture-level
SLEEP_GAME = 0.15   # entre les appels game-level


# ── Config ─────────────────────────────────────────────────────────────────────

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
    manager_list = [
        m.strip() for m in os.getenv("SORARE_MANAGERS_MLB", "").split(",") if m.strip()
    ]
    return engine, api_headers, manager_list


# ── Helpers communs ────────────────────────────────────────────────────────────

def _all_fixtures(headers: dict) -> list[dict]:
    """Retourne tous les fixtures CLASSIC triés par gw_int croissant."""
    data = _api_post({
        "query": """{
          so5 {
            featuredSo5Fixtures(sport: BASEBALL, first: 1000, eventType: CLASSIC) {
              slug gameWeek canCompose
            }
          }
        }"""
    }, headers)
    fixtures = data["data"]["so5"]["featuredSo5Fixtures"]
    return sorted(fixtures, key=lambda f: f["gameWeek"])


def _gws_in_db(engine, table: str) -> set[int]:
    """Retourne l'ensemble des gw_int déjà présents dans mlb.<table>."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT DISTINCT gw_int FROM mlb.{table} WHERE gw_int IS NOT NULL"
        )).fetchall()
    return {r[0] for r in rows}


def _game_ids_from_db(engine, gw_int: int) -> list[dict]:
    """Retourne les IDs et dates des matchs depuis mlb.games pour une GW donnée."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT 'Game:' || game_id AS full_id, game_date "
            "FROM mlb.games WHERE gw_int = :gw"
        ), {"gw": gw_int}).fetchall()
    return [{"id": r[0], "date": r[1].isoformat()} for r in rows]


# ── 1. Galerie ─────────────────────────────────────────────────────────────────

def _get_gallery(slug: str, headers: dict) -> pd.DataFrame:
    from datetime import datetime
    has_next_page = True
    end_cursor    = ""
    cards_data    = []
    page          = 0

    while has_next_page:
        query = f"""{{
          user(slug: "{slug}") {{
            slug nickname
            cards(sport: BASEBALL rarities: [limited, rare, super_rare, unique] after: "{end_cursor}") {{
              nodes {{
                ... on BaseballCard {{
                  slug name pictureUrl rarityTyped displayRarity
                  grade xp xpNeededForCurrentGrade xpNeededForNextGrade
                  power inSeasonEligible sealed anyPositions
                  baseballPlayer {{
                    slug displayName age
                    activeClub {{ slug }}
                    nextGame {{
                      date
                      competition {{ slug displayName }}
                      homeTeam {{ slug ... on Club {{ name }} ... on NationalTeam {{ name }} }}
                      awayTeam {{ slug ... on Club {{ name }} ... on NationalTeam {{ name }} }}
                    }}
                  }}
                }}
              }}
              pageInfo {{ endCursor hasNextPage }}
            }}
          }}
        }}"""

        resp     = _api_post({"query": query}, headers)
        user     = resp["data"]["user"]
        nickname = user["nickname"]
        nodes    = user["cards"]["nodes"]
        page_info = user["cards"]["pageInfo"]
        page += 1
        print(f"    page {page} ({len(nodes)} cartes)")

        for card in nodes:
            player   = card["baseballPlayer"]
            club_slug = player["activeClub"]["slug"] if player["activeClub"] else None

            next_game_date = competition_slug = competition_name = None
            home_team_slug = home_team_name = away_team_slug = away_team_name = home_away = None

            ng = player.get("nextGame")
            if ng:
                ht = ng.get("homeTeam") or {}
                at = ng.get("awayTeam") or {}
                home_team_slug = ht.get("slug")
                home_team_name = ht.get("name")
                away_team_slug = at.get("slug")
                away_team_name = at.get("name")
                competition_slug = ng["competition"]["slug"]
                competition_name = ng["competition"]["displayName"]
                next_game_date   = datetime.fromisoformat(
                    ng["date"].replace("Z", "+00:00")
                ).strftime("%Y-%m-%d %H:%M:%S")
                if club_slug:
                    home_away = "home" if club_slug == home_team_slug else \
                                "away" if club_slug == away_team_slug else None

            positions = card.get("anyPositions") or []
            cards_data.append({
                "id_manager":                   slug,
                "gallery_manager":              nickname,
                "card_slug":                    card["slug"],
                "card_name":                    card["name"],
                "picture_url":                  card.get("pictureUrl"),
                "player_name":                  player["displayName"],
                "card_rarity":                  card["rarityTyped"],
                "card_display_rarity":          card["displayRarity"],
                "card_grade":                   card["grade"],
                "card_xp":                      card["xp"],
                "card_xp_needed_current_grade": card["xpNeededForCurrentGrade"],
                "card_xp_needed_next_grade":    card["xpNeededForNextGrade"],
                "card_power":                   card["power"],
                "card_display_position":        positions[0] if positions else None,
                "player_slug":                  player["slug"],
                "player_age":                   player["age"],
                "in_season_eligible":           card["inSeasonEligible"],
                "competition_slug":             competition_slug,
                "competition_name":             competition_name,
                "home_team_slug":               home_team_slug,
                "home_team_name":               home_team_name,
                "away_team_slug":               away_team_slug,
                "away_team_name":               away_team_name,
                "next_game_date":               next_game_date,
                "sealed":                       card["sealed"],
                "active_club_slug":             club_slug,
                "home_away":                    home_away,
            })

        has_next_page = page_info["hasNextPage"]
        end_cursor    = page_info["endCursor"]

    return pd.DataFrame(cards_data)


def refresh_gallery(engine, manager_list: list, headers: dict) -> None:
    if not manager_list:
        raise ValueError("SORARE_MANAGERS_MLB vide — aucun manager à charger.")
    frames = []
    for slug in manager_list:
        print(f"  -> {slug}")
        frames.append(_get_gallery(slug, headers))
    df = pd.concat(frames, ignore_index=True)
    df.to_sql("gallery_players", con=engine, schema="mlb", if_exists="replace", index=False)
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mlb_gallery_player_slug ON mlb.gallery_players(player_slug)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mlb_gallery_id_manager  ON mlb.gallery_players(id_manager)"))
    print(f"  {len(df)} cartes dans mlb.gallery_players")


# ── 2. Game infos ──────────────────────────────────────────────────────────────

def update_game_infos(engine, headers: dict, all_fixtures: list) -> None:
    gws_done = _gws_in_db(engine, "games")
    missing  = [f for f in all_fixtures if not f["canCompose"] and f["gameWeek"] not in gws_done]

    if not missing:
        print("  A jour.")
        return

    gw_range = f"GW{missing[0]['gameWeek']} a GW{missing[-1]['gameWeek']}"
    print(f"  {len(missing)} GW manquantes ({gw_range})")

    for i, f in enumerate(missing):
        raw  = fetch_games(f["slug"], "CLASSIC", headers)
        n    = sum(1 for g in raw if g and g.get("scored"))
        game_rows, inning_rows = _flatten_games(raw, f["gameWeek"], f["slug"])
        _store_games(engine, game_rows, inning_rows, f["gameWeek"])
        print(f"  [{i+1}/{len(missing)}] GW{f['gameWeek']} — {n} matchs terminés")
        time.sleep(SLEEP)


# ── 3. Game scores par GW ──────────────────────────────────────────────────────

def update_gw_scores(engine, headers: dict, all_fixtures: list) -> None:
    gws_done = _gws_in_db(engine, "game_scores")
    missing  = [f for f in all_fixtures if not f["canCompose"] and f["gameWeek"] not in gws_done]

    if not missing:
        print("  A jour.")
        return

    gw_range = f"GW{missing[0]['gameWeek']} a GW{missing[-1]['gameWeek']}"
    print(f"  {len(missing)} GW manquantes ({gw_range})")

    for i, f in enumerate(missing):
        gw_int       = f["gameWeek"]
        fixture_info = {"gw_int": gw_int}

        # IDs depuis mlb.games (mis à jour à l'étape précédente)
        game_metas = _game_ids_from_db(engine, gw_int)
        if not game_metas:
            print(f"  [{i+1}/{len(missing)}] GW{gw_int} — aucun match en base, ignoré")
            continue

        all_score_rows, all_detail_rows = [], []
        n_played = 0
        for gm in game_metas:
            game_data = _fetch_game_scores(gm["id"], headers)
            if game_data["statusTyped"] == "scheduled":
                time.sleep(SLEEP_GAME)
                continue
            s_rows, d_rows = _flatten_gw_scores(fixture_info, gm, game_data)
            all_score_rows.extend(s_rows)
            all_detail_rows.extend(d_rows)
            n_played += 1
            time.sleep(SLEEP_GAME)

        _store_gw_scores(engine, all_score_rows, all_detail_rows, gw_int)
        print(f"  [{i+1}/{len(missing)}] GW{gw_int} — {n_played}/{len(game_metas)} matchs")
        time.sleep(SLEEP)


# ── 4. Historique nouveaux joueurs galerie ─────────────────────────────────────

def update_new_players(engine, headers: dict) -> None:
    gallery_slugs = set(get_gallery_slugs(engine))
    if not gallery_slugs:
        print("  Galerie vide.")
        return

    with engine.connect() as conn:
        already_scored = {r[0] for r in conn.execute(text(
            "SELECT DISTINCT player_slug FROM mlb.game_scores WHERE player_slug = ANY(:slugs)"
        ), {"slugs": list(gallery_slugs)}).fetchall()}

    new_slugs = sorted(gallery_slugs - already_scored)
    if not new_slugs:
        print("  Aucun nouveau joueur.")
        return

    print(f"  {len(new_slugs)} joueur(s) sans historique...")
    all_scores, all_details = [], []
    for i, slug in enumerate(new_slugs):
        print(f"  [{i+1}/{len(new_slugs)}] {slug}")
        s, d = fetch_scores_for_player(slug, headers)
        all_scores.extend(s)
        all_details.extend(d)

    if all_scores:
        store_scores(engine, all_scores, all_details)


# ── 5. Précalcul stats galerie ────────────────────────────────────────────────

def precompute_gallery_stats(engine) -> None:
    """Précalcule les stats galerie (5/10/20 matchs) en une passe et stocke dans mlb.gallery_stats_agg."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS mlb.gallery_stats_agg"))
        conn.execute(text("""
            CREATE TABLE mlb.gallery_stats_agg AS
            WITH gallery AS (
                SELECT DISTINCT ON (player_slug, id_manager, card_display_rarity)
                    player_slug, player_name, card_display_rarity, card_display_position,
                    id_manager, gallery_manager, next_game_date,
                    home_team_name, away_team_name, home_away, competition_name
                FROM mlb.gallery_players
                WHERE NOT sealed
                ORDER BY player_slug, id_manager, card_display_rarity
            ),
            qualifying_games AS MATERIALIZED (
                SELECT gs.player_slug, gs.game_date,
                       ROW_NUMBER() OVER (PARTITION BY gs.player_slug ORDER BY gs.game_date DESC) AS rk
                FROM mlb.game_scores gs
                WHERE gs.played_in_game = true
                  AND gs.player_slug IN (SELECT DISTINCT player_slug FROM gallery)
            ),
            w AS MATERIALIZED (
                SELECT g.player_slug, g.id_manager, g.gallery_manager, g.player_name,
                       g.card_display_rarity, g.card_display_position,
                       g.home_team_name, g.away_team_name, g.home_away,
                       g.competition_name, g.next_game_date,
                       gsd.stat, gsd.stat_short_name, gsd.category, gsd.stat_value, qg.rk
                FROM gallery g
                JOIN qualifying_games qg ON g.player_slug = qg.player_slug
                JOIN mlb.game_score_details gsd
                    ON qg.player_slug = gsd.player_slug AND qg.game_date = gsd.game_date
                WHERE qg.rk <= 20
            ),
            agg AS (
                SELECT player_slug, id_manager, gallery_manager, player_name,
                       card_display_rarity, card_display_position,
                       home_team_name, away_team_name, home_away,
                       competition_name, next_game_date, stat, stat_short_name, category,
                       ROUND(AVG(stat_value) FILTER (WHERE rk <= 5 )::numeric, 3) AS avg_5,
                       ROUND(AVG(stat_value) FILTER (WHERE rk <= 10)::numeric, 3) AS avg_10,
                       ROUND(AVG(stat_value) FILTER (WHERE rk <= 20)::numeric, 3) AS avg_20,
                       COUNT(DISTINCT CASE WHEN rk <= 5  THEN rk END)::integer    AS nb_5,
                       COUNT(DISTINCT CASE WHEN rk <= 10 THEN rk END)::integer    AS nb_10,
                       COUNT(DISTINCT CASE WHEN rk <= 20 THEN rk END)::integer    AS nb_20
                FROM w
                GROUP BY player_slug, id_manager, gallery_manager, player_name,
                         card_display_rarity, card_display_position, home_team_name,
                         away_team_name, home_away, competition_name, next_game_date,
                         stat, stat_short_name, category
            )
            SELECT player_slug, id_manager, gallery_manager, player_name,
                   card_display_rarity, card_display_position,
                   home_team_name, away_team_name, home_away,
                   competition_name, next_game_date, stat, stat_short_name, category,
                   avg_5  AS moyenne, nb_5  AS nb_matchs, '5 matchs'  AS fenetre FROM agg
            UNION ALL
            SELECT player_slug, id_manager, gallery_manager, player_name,
                   card_display_rarity, card_display_position,
                   home_team_name, away_team_name, home_away,
                   competition_name, next_game_date, stat, stat_short_name, category,
                   avg_10 AS moyenne, nb_10 AS nb_matchs, '10 matchs' AS fenetre FROM agg
            UNION ALL
            SELECT player_slug, id_manager, gallery_manager, player_name,
                   card_display_rarity, card_display_position,
                   home_team_name, away_team_name, home_away,
                   competition_name, next_game_date, stat, stat_short_name, category,
                   avg_20 AS moyenne, nb_20 AS nb_matchs, '20 matchs' AS fenetre FROM agg
        """))
        conn.execute(text(
            "CREATE INDEX ON mlb.gallery_stats_agg(gallery_manager, fenetre, stat)"
        ))
        conn.execute(text(
            "CREATE INDEX ON mlb.gallery_stats_agg(player_slug)"
        ))
    print("  Table mlb.gallery_stats_agg reconstruite.")


# ── 6. Prix cartes ─────────────────────────────────────────────────────────────

def update_prices(engine, headers: dict) -> None:
    gallery_slugs = get_gallery_slugs(engine)
    total = len(gallery_slugs)
    if not total:
        print("  Galerie vide.")
        return

    print(f"  {total} joueurs ({total * 8} appels API)...")
    print("  Chargement des taux de change...")
    fx = _load_fx_rates()

    all_rows = []
    for i, slug in enumerate(gallery_slugs):
        remaining = total - (i + 1)
        if remaining % 20 == 0:
            print(f"    {remaining} joueurs restants...")
        all_rows.extend(fetch_prices_for_player(slug, headers, fx))

    store_prices(engine, all_rows)


# ── 7. Export parquet ──────────────────────────────────────────────────────────

def export_to_parquet(engine) -> None:
    """Exporte toutes les données de l'app en fichiers parquet pour Streamlit Cloud."""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    def _df(conn, q, params=None):
        res = conn.execute(text(q), params or {})
        return pd.DataFrame(res.fetchall(), columns=list(res.keys()))

    with engine.connect() as conn:

        _df(conn, "SELECT * FROM mlb.gallery_stats_agg").to_parquet(
            data_dir / "gallery_stats.parquet", index=False)
        print("  gallery_stats.parquet")

        _df(conn, """
            SELECT DISTINCT ON (g.player_slug, g.id_manager, g.card_display_rarity)
                g.id_manager, g.gallery_manager, g.player_name, g.player_slug,
                g.card_display_rarity, g.card_display_position,
                g.next_game_date, g.home_team_name, g.away_team_name,
                g.home_away, g.active_club_slug, g.in_season_eligible,
                gs_agg.nb_played, gs_agg.nb_total,
                COALESCE(ROUND(100.0 * gs_agg.nb_played / NULLIF(gs_agg.nb_total,0))::integer, NULL) AS pct_played
            FROM mlb.gallery_players g
            LEFT JOIN (
                SELECT player_slug,
                       SUM(CASE WHEN played_in_game THEN 1 ELSE 0 END) AS nb_played,
                       COUNT(*) AS nb_total
                FROM mlb.game_scores
                WHERE gw_int >= (SELECT MAX(gw_int) - 9 FROM mlb.game_scores)
                GROUP BY player_slug
            ) gs_agg ON g.player_slug = gs_agg.player_slug
            WHERE g.next_game_date IS NOT NULL AND NOT g.sealed
            ORDER BY g.player_slug, g.id_manager, g.card_display_rarity, g.next_game_date
        """).to_parquet(data_dir / "calendar.parquet", index=False)
        print("  calendar.parquet")

        _df(conn, """
            SELECT g.id_manager, g.gallery_manager, g.card_name, g.picture_url,
                   g.player_name, g.player_slug, g.card_display_rarity, g.card_display_position,
                   g.card_power, g.card_grade, g.card_xp, g.card_xp_needed_next_grade,
                   g.in_season_eligible, g.active_club_slug,
                   cp_is.price_eur  AS price_in_season,
                   cp_oos.price_eur AS price_out_season,
                   cp_is.sealable_for,
                   p.next_gw_projected_score
            FROM mlb.gallery_players g
            LEFT JOIN mlb.card_prices cp_is
                ON g.player_slug = cp_is.player_slug
               AND LOWER(g.card_display_rarity) = cp_is.rarity AND cp_is.in_season = true
            LEFT JOIN mlb.card_prices cp_oos
                ON g.player_slug = cp_oos.player_slug
               AND LOWER(g.card_display_rarity) = cp_oos.rarity AND cp_oos.in_season = false
            LEFT JOIN mlb.players p ON g.player_slug = p.player_slug
            WHERE NOT g.sealed
            ORDER BY CASE LOWER(g.card_display_rarity)
                WHEN 'unique' THEN 0 WHEN 'super_rare' THEN 1 WHEN 'rare' THEN 2 ELSE 3 END,
                COALESCE(cp_is.price_eur, 0) DESC
        """).to_parquet(data_dir / "card_prices.parquet", index=False)
        print("  card_prices.parquet")

        _df(conn, "SELECT player_slug FROM mlb.player_injuries WHERE active = true").to_parquet(
            data_dir / "injuries.parquet", index=False)
        print("  injuries.parquet")

        slugs = _df(conn, "SELECT DISTINCT player_slug FROM mlb.gallery_players WHERE NOT sealed")["player_slug"].tolist()

        _df(conn, """
            SELECT player_slug, game_date, gw_int, score, played_in_game, position
            FROM mlb.game_scores
            WHERE player_slug = ANY(:slugs)
            ORDER BY player_slug, game_date DESC
        """, {"slugs": slugs}).to_parquet(data_dir / "game_scores.parquet", index=False)
        print("  game_scores.parquet")

        _df(conn, """
            WITH ranked AS (
                SELECT player_slug, game_date,
                       ROW_NUMBER() OVER (PARTITION BY player_slug ORDER BY game_date DESC) AS rk
                FROM mlb.game_scores
                WHERE played_in_game = true AND player_slug = ANY(:slugs)
            )
            SELECT gsd.player_slug, gsd.game_date, gsd.stat, gsd.stat_short_name,
                   gsd.category, gsd.stat_value
            FROM mlb.game_score_details gsd
            JOIN ranked r ON gsd.player_slug = r.player_slug AND gsd.game_date = r.game_date
            WHERE r.rk <= 30
        """, {"slugs": slugs}).to_parquet(data_dir / "game_score_details.parquet", index=False)
        print("  game_score_details.parquet")

        _df(conn, """
            SELECT game_id, game_date, gw_int,
                   home_team_slug, away_team_slug,
                   home_probable_pitcher, away_probable_pitcher
            FROM mlb.games
        """).to_parquet(data_dir / "games.parquet", index=False)
        print("  games.parquet")

        _df(conn, """
            SELECT player_slug, display_name, team_slug, position_1, agg_position_1
            FROM mlb.players
        """).to_parquet(data_dir / "players.parquet", index=False)
        print("  players.parquet")

    print("  Export terminé.")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine, api_headers, manager_list = _load_config()

    print("\n[1/7] Galerie...")
    refresh_gallery(engine, manager_list, api_headers)

    print("\n  Chargement des fixtures CLASSIC disponibles...")
    all_fixtures = _all_fixtures(api_headers)
    completed    = [f for f in all_fixtures if not f["canCompose"]]
    print(f"  {len(completed)} fixtures terminees (GW{completed[0]['gameWeek']} - GW{completed[-1]['gameWeek']})")

    print("\n[2/7] Game infos (box scores)...")
    update_game_infos(engine, api_headers, all_fixtures)

    print("\n[3/7] Game scores par GW (tous joueurs)...")
    update_gw_scores(engine, api_headers, all_fixtures)

    print("\n[4/7] Historique nouveaux joueurs galerie...")
    update_new_players(engine, api_headers)

    print("\n[5/7] Précalcul stats galerie...")
    precompute_gallery_stats(engine)

    print("\n[6/7] Prix cartes...")
    update_prices(engine, api_headers)

    print("\n[7/7] Export parquet...")
    export_to_parquet(engine)

    print("\n[8/8] Predictions ML (prochaine GW)...")
    try:
        from ml_predict_gw import run as ml_run
        ml_run(engine)
    except Exception as e:
        print(f"  Avertissement predictions ML : {e}")

    print("\nMise a jour complete !")
