"""
update_data.py
--------------
Mise à jour incrémentale de toutes les données MLB.

  [1/10] Players & équipes → full refresh mlb.players + mlb.teams (lent : 1 appel/joueur)
  [2/10] Galerie           → full refresh (prix, prochain match, etc. changent)
  [3/10] Game infos        → uniquement les GW absentes de mlb.games
  [4/10] Météo             → upsert mlb.game_weather (Open-Meteo, 7j passés + 16j futurs)
  [5/10] Game scores/GW    → uniquement les GW absentes de mlb.game_scores
  [6/10] Nouveaux joueurs  → historique complet pour les joueurs galerie sans données
  [7/10] Précalcul stats   → mlb.gallery_stats_agg (5/10/20 matchs, passe unique)
  [8/10] Prix cartes       → full refresh (prix volatils)
  [9/10] Prix d'achat      → historique trades via API Sorare (crédits limités)
  [10/10] Export parquet   → fichiers data/*.parquet pour Streamlit

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
                             store as _store_gw_scores, \
                             extract_players_from_game as _extract_gw_players, \
                             store_players_seen as _store_players_seen
from fetch_scores     import fetch_scores_for_player, store_scores
from fetch_prices     import fetch_prices_for_player, store_prices, _load_fx_rates
from fetch_card_trades import fetch_trades, store_trades
from fetch_weather    import run as _weather_run
from init_ref_data    import fetch_teams, store_teams, fetch_and_store_players

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


def get_gallery_slugs(engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT player_slug FROM mlb.gallery_players WHERE NOT sealed"
        )).fetchall()
    return [r[0] for r in rows]


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


def _score_snapshot(engine) -> str | None:
    """Empreinte de mlb.game_scores : MAX(date) + COUNT(*). Détecte les insertions
    sur des dates passées (ex. backfill two-way players) que le MAX seul manquerait."""
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT MAX(game_date)::text || '|' || COUNT(*)::text FROM mlb.game_scores"
        )).fetchone()
    return row[0] if row else None


def _gallery_stats_exists(engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='mlb' AND table_name='gallery_stats_agg')"
        )).fetchone()
    return bool(row[0]) if row else False


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
                "card_display_position_2":      positions[1] if len(positions) > 1 else None,
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
    else:
        gw_range = f"GW{missing[0]['gameWeek']} a GW{missing[-1]['gameWeek']}"
        print(f"  {len(missing)} GW manquantes ({gw_range})")
        for i, f in enumerate(missing):
            raw  = fetch_games(f["slug"], "CLASSIC", headers)
            n    = sum(1 for g in raw if g and g.get("scored"))
            game_rows, inning_rows = _flatten_games(raw, f["gameWeek"], f["slug"])
            _store_games(engine, game_rows, inning_rows, f["gameWeek"])
            print(f"  [{i+1}/{len(missing)}] GW{f['gameWeek']} — {n} matchs terminés")
            time.sleep(SLEEP)

    # GW à venir (canCompose=True) : charge les matchs schedulés (dates + équipes)
    upcoming = [f for f in all_fixtures if f["canCompose"]]
    for f in upcoming:
        raw = fetch_games(f["slug"], "CLASSIC", headers)
        game_rows, inning_rows = _flatten_games(raw, f["gameWeek"], f["slug"],
                                                include_unscored=True)
        if game_rows:
            _store_games(engine, game_rows, inning_rows, f["gameWeek"])
            n = len(game_rows)
            print(f"  GW{f['gameWeek']} (à venir) — {n} matchs schedulés chargés")
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

        all_score_rows, all_detail_rows, all_player_rows = [], [], []
        n_played = 0
        for gm in game_metas:
            game_data = _fetch_game_scores(gm["id"], headers)
            if game_data["statusTyped"] == "scheduled":
                time.sleep(SLEEP_GAME)
                continue
            s_rows, d_rows = _flatten_gw_scores(fixture_info, gm, game_data)
            all_score_rows.extend(s_rows)
            all_detail_rows.extend(d_rows)
            all_player_rows.extend(_extract_gw_players(game_data))
            n_played += 1
            time.sleep(SLEEP_GAME)

        _store_gw_scores(engine, all_score_rows, all_detail_rows, gw_int)
        if all_player_rows:
            _store_players_seen(engine, all_player_rows)
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
        s, d = fetch_scores_for_player(slug, headers, start_date=None)
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

def update_prices(engine, headers: dict, include_gw_players: bool = False) -> None:
    gallery_slugs = set(get_gallery_slugs(engine))
    if include_gw_players:
        ml_path = Path(__file__).parent / "data" / "ml_predictions.parquet"
        if ml_path.exists():
            gw_slugs = set(pd.read_parquet(ml_path)["player_slug"].dropna().unique())
        else:
            gw_slugs = set()
        extra = gw_slugs - gallery_slugs
        all_slugs = sorted(gallery_slugs | gw_slugs)
        print(f"  Mode étendu : {len(all_slugs)} joueurs ({len(gallery_slugs)} galerie + {len(extra)} GW hors galerie)")
    else:
        all_slugs = sorted(gallery_slugs)

    total = len(all_slugs)
    if not total:
        print("  Aucun joueur.")
        return

    print(f"  {total} joueurs ({total * 8} appels API)...")
    print("  Chargement des taux de change...")
    fx = _load_fx_rates()

    all_rows = []
    for i, slug in enumerate(all_slugs):
        remaining = total - (i + 1)
        if remaining % 20 == 0:
            print(f"    {remaining} joueurs restants...")
        all_rows.extend(fetch_prices_for_player(slug, headers, fx))

    store_prices(engine, all_rows)


# ── 6. Prix d'achat (card trades) ─────────────────────────────────────────────

def update_card_trades(engine, manager_list: list, headers: dict) -> None:
    if not manager_list:
        print("  Aucun manager configuré.")
        return
    for slug in manager_list:
        print(f"  -> {slug}")
        rows = fetch_trades(slug, headers)
        store_trades(engine, rows, slug)


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
                   g.card_display_position_2,
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

        _df(conn, """
            SELECT
                p.player_slug, p.display_name AS player_name, p.team_slug, p.agg_position_1 AS position,
                MAX(CASE WHEN cp.rarity = 'limited'    AND cp.in_season = true  THEN cp.price_eur END) AS price_limited_is,
                MAX(CASE WHEN cp.rarity = 'limited'    AND cp.in_season = false THEN cp.price_eur END) AS price_limited_oos,
                MAX(CASE WHEN cp.rarity = 'rare'       AND cp.in_season = true  THEN cp.price_eur END) AS price_rare_is,
                MAX(CASE WHEN cp.rarity = 'rare'       AND cp.in_season = false THEN cp.price_eur END) AS price_rare_oos,
                MAX(CASE WHEN cp.rarity = 'super_rare' AND cp.in_season = true  THEN cp.price_eur END) AS price_sr_is,
                MAX(CASE WHEN cp.rarity = 'super_rare' AND cp.in_season = false THEN cp.price_eur END) AS price_sr_oos,
                MAX(CASE WHEN cp.rarity = 'unique'     AND cp.in_season = true  THEN cp.price_eur END) AS price_unique_is,
                MAX(CASE WHEN cp.rarity = 'unique'     AND cp.in_season = false THEN cp.price_eur END) AS price_unique_oos
            FROM mlb.card_prices cp
            INNER JOIN mlb.players p ON cp.player_slug = p.player_slug
            GROUP BY p.player_slug, p.display_name, p.team_slug, p.agg_position_1
            ORDER BY p.display_name
        """).to_parquet(data_dir / "all_players_market.parquet", index=False)
        print("  all_players_market.parquet")

        _df(conn, "SELECT player_slug FROM mlb.player_injuries WHERE active = true").to_parquet(
            data_dir / "injuries.parquet", index=False)
        print("  injuries.parquet")

        slugs = _df(conn, "SELECT DISTINCT player_slug FROM mlb.gallery_players WHERE NOT sealed")["player_slug"].tolist()

        _df(conn, """
            SELECT player_slug, game_date, gw_int, category, score, played_in_game
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

        _df(conn, "SELECT team_slug, team_code, picture_url FROM mlb.teams WHERE team_code IS NOT NULL"
        ).to_parquet(data_dir / "teams.parquet", index=False)
        print("  teams.parquet")

        # Tous les joueurs vus dans les matchs fetchés (noms + position)
        # Alimenté par store_players_seen() à chaque fetch_gw_scores.
        # Fallback : pré-peuplé depuis gallery_players pour les données historiques.
        try:
            with engine.begin() as _txn:
                _txn.execute(text("""
                    CREATE TABLE IF NOT EXISTS mlb.players_seen (
                        player_slug  TEXT PRIMARY KEY,
                        display_name TEXT,
                        position     TEXT
                    )
                """))
                _txn.execute(text("""
                    INSERT INTO mlb.players_seen (player_slug, display_name, position)
                    SELECT DISTINCT player_slug, player_name, card_display_position
                    FROM mlb.gallery_players
                    ON CONFLICT (player_slug) DO NOTHING
                """))
        except Exception:
            pass
        _df(conn, "SELECT player_slug, display_name, position FROM mlb.players_seen"
        ).to_parquet(data_dir / "players_seen.parquet", index=False)
        print("  players_seen.parquet")

        # Stats tous joueurs (pas seulement galerie) — 20 derniers matchs joués
        # Utilisé par l'onglet Base de données pour montrer tout le roster MLB.
        _df(conn, """
            WITH ranked AS (
                SELECT player_slug, game_date,
                       ROW_NUMBER() OVER (
                           PARTITION BY player_slug ORDER BY game_date DESC
                       ) AS rk
                FROM mlb.game_scores
                WHERE played_in_game = true
            )
            SELECT gsd.player_slug, gsd.game_date, gsd.stat, gsd.stat_short_name,
                   gsd.category, gsd.stat_value, r.rk
            FROM mlb.game_score_details gsd
            JOIN ranked r ON gsd.player_slug = r.player_slug
                          AND gsd.game_date  = r.game_date
            WHERE r.rk <= 20
        """).to_parquet(data_dir / "game_score_details_db.parquet", index=False)
        print("  game_score_details_db.parquet")

        try:
            _df(conn, """
                SELECT p.player_slug, pl.display_name, pl.team_slug,
                       pl.agg_position_1 AS position,
                       p.game_date, p.mlb_game_pk,
                       p.pitches, p.strikes, p.batters_faced, p.innings_pitched_outs
                FROM mlb.pitcher_game_pitches p
                LEFT JOIN mlb.players pl ON p.player_slug = pl.player_slug
                WHERE p.game_date >= NOW() - INTERVAL '30 days'
                ORDER BY p.game_date DESC, p.pitches DESC NULLS LAST
            """).to_parquet(data_dir / "pitcher_pitches.parquet", index=False)
            print("  pitcher_pitches.parquet")
        except Exception:
            pass  # Table absente si fetch_pitch_counts n'a pas encore tourné

    print("  Export terminé.")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse as _argparse
    _parser = _argparse.ArgumentParser(description="Mise à jour incrémentale des données MLB.")
    _parser.add_argument("--prices-all", action="store_true",
        help="Fetch prices pour tous les joueurs GW (~10k appels API, lent)")
    _parser.add_argument("--from", dest="from_step", type=int, default=1, metavar="N",
        help="Démarre à partir de l'étape N (1-11)")
    _parser.add_argument("--only", dest="only_step", type=int, default=None, metavar="N",
        help="Exécute uniquement l'étape N")
    _args = _parser.parse_args()

    _s = _args.only_step or _args.from_step
    _e = _args.only_step or 11

    def _run(n: int) -> bool:
        return _s <= n <= _e

    engine, api_headers, manager_list = _load_config()

    if _run(1):
        print("\n[1/10] Players & équipes (lent)...")
        df_teams = fetch_teams(api_headers)
        store_teams(engine, df_teams)
        fetch_and_store_players(engine, df_teams["team_slug"].tolist(), api_headers)

    _gallery_refreshed = False
    if _run(2):
        print("\n[2/10] Galerie...")
        refresh_gallery(engine, manager_list, api_headers)
        _gallery_refreshed = True

    _snap_before = _score_snapshot(engine) if (_run(3) or _run(5) or _run(6)) else None

    if _run(3) or _run(5):
        print("\n  Chargement des fixtures CLASSIC disponibles...")
        all_fixtures = _all_fixtures(api_headers)
        completed    = [f for f in all_fixtures if not f["canCompose"]]
        print(f"  {len(completed)} fixtures terminees (GW{completed[0]['gameWeek']} - GW{completed[-1]['gameWeek']})")
    else:
        all_fixtures = []

    if _run(3):
        print("\n[3/10] Game infos (box scores)...")
        update_game_infos(engine, api_headers, all_fixtures)

    if _run(4):
        print("\n[4/10] Météo...")
        try:
            _weather_run(engine)
        except Exception as e:
            print(f"  Avertissement météo : {e}")

    if _run(5):
        print("\n[5/10] Game scores par GW (tous joueurs)...")
        update_gw_scores(engine, api_headers, all_fixtures)

    if _run(6):
        print("\n[6/10] Historique nouveaux joueurs galerie...")
        update_new_players(engine, api_headers)

    if _snap_before is not None:
        _snap_after = _score_snapshot(engine)
        _scores_changed = _snap_after != _snap_before
    else:
        _scores_changed = True

    if _run(7):
        if not _scores_changed and not _gallery_refreshed and _gallery_stats_exists(engine):
            print("\n[7/10] Précalcul stats galerie... (skippé — aucun nouveau score ni changement galerie)")
        else:
            print("\n[7/10] Précalcul stats galerie...")
            precompute_gallery_stats(engine)

    if _run(8):
        print("\n[8/10] Prix cartes...")
        update_prices(engine, api_headers, include_gw_players=_args.prices_all)

    if _run(9):
        print("\n[9/10] Prix d'achat (card trades)...")
        try:
            update_card_trades(engine, manager_list, api_headers)
        except Exception as e:
            print(f"  Avertissement card trades : {e}")

    if _run(10):
        print("\n[10/10] Export parquet...")
        export_to_parquet(engine)

    if _run(11):
        print("\n[11/13] Stats saison pitchers (ERA+)...")
        try:
            from fetch_pitcher_season_stats import run as era_run
            era_run(engine)
        except Exception as e:
            print(f"  Avertissement ERA+ : {e}")

        print("\n[12/13] Pitch counts (MLB Stats API)...")
        try:
            from fetch_pitch_counts import run as pc_run
            pc_run(engine)
        except Exception as e:
            print(f"  Avertissement pitch counts : {e}")

        print("\n[13/13] Predictions ML (prochaine GW)...")
        _ml_parquet = Path(__file__).parent / "data" / "ml_predictions.parquet"
        _sentinel   = Path(__file__).parent / "data" / ".ml_last_run"
        _snap_ml    = _score_snapshot(engine)
        _skip_ml    = False
        if not _scores_changed and _ml_parquet.exists():
            try:
                _stored  = _sentinel.read_text().strip() if _sentinel.exists() else ""
                _skip_ml = bool(_stored) and _stored == str(_snap_ml or "")
            except Exception:
                pass
        if _skip_ml:
            print("  Skippé — aucun nouveau score depuis le dernier calcul.")
        else:
            try:
                from ml_predict_gw import run as ml_run
                ml_run(engine)
                if _snap_ml:
                    _sentinel.write_text(str(_snap_ml))
            except Exception as e:
                print(f"  Avertissement predictions ML : {e}")

    print("\nMise a jour complete !")
