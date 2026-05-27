"""
fetch_pitch_counts.py
---------------------
Récupère le nombre de lancers (pitch count) par pitcher par match depuis
l'API officielle MLB Stats (statsapi.mlb.com) — sans scraping, sans auth.

Pipeline en 4 étapes :
  1. Build team map   : team_code → mlb_team_id  (1 appel, mis en cache)
  2. Build player map : display_name → player_slug  (depuis mlb.players)
  3. Résoudre gamePk  : pour chaque match Sorare, trouver le gamePk MLB via
                        le calendrier /schedule?date=...
  4. Fetch boxscores  : /game/{gamePk}/boxscore → numberOfPitches par pitcher

Stocke dans :
  - mlb.games              : colonne mlb_game_pk  (mapping Sorare UUID → gamePk)
  - mlb.pitcher_game_pitches : (player_slug, game_date, pitches, strikes,
                                batters_faced, innings_pitched_outs)

Usage :
    python fetch_pitch_counts.py               # saison en cours
    python fetch_pitch_counts.py --days 30     # 30 derniers jours seulement
    python fetch_pitch_counts.py --full        # tout l'historique disponible
"""

import argparse
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).parent.parent / ".env")

MLB_API   = "https://statsapi.mlb.com/api/v1"
SLEEP     = 0.15   # secondes entre appels API (respectueux du serveur)
SEASON_START_MONTH = 3   # Mars — début de spring training / saison

DB_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME')}"
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get(path: str, params: dict = None) -> dict:
    url = f"{MLB_API}{path}"
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(SLEEP)
    return r.json()


def _normalize_name(name: str) -> str:
    """'José Berríos' → 'jose berrios'  (accents supprimés, minuscules)"""
    nfkd = unicodedata.normalize("NFKD", name)
    return re.sub(r"[^a-z0-9 ]", "",
                  nfkd.encode("ascii", "ignore").decode("ascii").lower()).strip()


# ── Étape 1 : mapping team_code → mlb_team_id ───────────────────────────────

def build_team_map(engine) -> dict:
    """Retourne {team_slug: mlb_team_id} en matchant via team_code / abbrev."""
    our_teams = pd.read_sql(
        "SELECT team_slug, team_code FROM mlb.teams", engine
    )
    # Exclure les ligues (AL/NL)
    our_teams = our_teams[~our_teams["team_slug"].str.contains("league")]

    data = _get("/teams", {"sportId": 1, "season": datetime.now().year})
    mlb_teams = {
        t["abbreviation"]: t["id"]
        for t in data.get("teams", [])
    }

    mapping = {}
    unmatched = []
    for _, row in our_teams.iterrows():
        code = row["team_code"]
        mlb_id = mlb_teams.get(code)
        if mlb_id:
            mapping[row["team_slug"]] = mlb_id
        else:
            unmatched.append((row["team_slug"], code))

    print(f"  Team map : {len(mapping)} matchés, {len(unmatched)} non matchés")
    if unmatched:
        print(f"  Non matchés : {unmatched}")
        # Tentative manuelle pour les cas connus (Athletics OAK → ATH)
        fallbacks = {"ATH": "OAK", "OAK": "ATH"}
        for slug, code in unmatched:
            alt = mlb_teams.get(fallbacks.get(code, ""))
            if alt:
                mapping[slug] = alt
                print(f"    Fallback : {slug} ({code} → {fallbacks[code]}) = {alt}")

    return mapping


# ── Étape 2 : mapping display_name normalisé → player_slug ──────────────────

def build_player_map(engine) -> dict:
    """Retourne {normalized_name: player_slug} depuis mlb.players."""
    df = pd.read_sql("SELECT player_slug, display_name FROM mlb.players", engine)
    return {_normalize_name(row["display_name"]): row["player_slug"]
            for _, row in df.iterrows()}


# ── Étape 3 : résolution gamePk ──────────────────────────────────────────────

def ensure_schema(engine) -> None:
    with engine.begin() as conn:
        # Colonne gamePk sur mlb.games
        conn.execute(text("""
            ALTER TABLE mlb.games
            ADD COLUMN IF NOT EXISTS mlb_game_pk BIGINT
        """))
        # Table pitch counts
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mlb.pitcher_game_pitches (
                player_slug            TEXT        NOT NULL,
                game_date              TIMESTAMPTZ NOT NULL,
                mlb_game_pk            BIGINT      NOT NULL,
                pitches                INTEGER,
                strikes                INTEGER,
                batters_faced          INTEGER,
                innings_pitched_outs   INTEGER,
                updated_at             TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (player_slug, mlb_game_pk)
            )
        """))


def resolve_gamepks(engine, team_map: dict, since: datetime) -> int:
    """
    Pour les matchs sans mlb_game_pk depuis `since`, interroge le calendrier
    MLB par date et stocke les gamePk dans mlb.games.
    Retourne le nombre de matchs résolus.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT game_id, game_date::date AS d,
                   home_team_slug, away_team_slug
            FROM mlb.games
            WHERE mlb_game_pk IS NULL
              AND game_date >= :since
              AND game_date < NOW()
            ORDER BY game_date
        """), {"since": since}).fetchall()

    if not rows:
        print("  Aucun match à résoudre.")
        return 0

    # Grouper par date pour minimiser les appels API
    by_date: dict = {}
    for r in rows:
        by_date.setdefault(str(r.d), []).append(r)

    resolved = 0
    for date_str, games in by_date.items():
        try:
            data = _get("/schedule", {"date": date_str, "sportId": 1})
        except Exception as e:
            print(f"  Erreur schedule {date_str}: {e}")
            continue

        # index : (home_mlb_id, away_mlb_id) → gamePk
        pk_index: dict = {}
        for d in data.get("dates", []):
            for g in d.get("games", []):
                h = g["teams"]["home"]["team"]["id"]
                a = g["teams"]["away"]["team"]["id"]
                pk_index[(h, a)] = g["gamePk"]

        for row in games:
            h_id = team_map.get(row.home_team_slug)
            a_id = team_map.get(row.away_team_slug)
            pk   = pk_index.get((h_id, a_id))
            if pk:
                with engine.begin() as conn:
                    conn.execute(text(
                        "UPDATE mlb.games SET mlb_game_pk = :pk WHERE game_id = :gid"
                    ), {"pk": pk, "gid": row.game_id})
                resolved += 1

    print(f"  gamePk résolus : {resolved}/{len(rows)}")
    return resolved


# ── Étape 4 : fetch boxscores → pitch counts ─────────────────────────────────

def fetch_pitch_counts(engine, player_map: dict, since: datetime) -> int:
    """
    Pour les matchs avec mlb_game_pk mais sans données dans pitcher_game_pitches,
    récupère les boxscores et stocke les pitch counts.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT g.mlb_game_pk, g.game_date
            FROM mlb.games g
            WHERE g.mlb_game_pk IS NOT NULL
              AND g.game_date >= :since
              AND g.game_date < NOW()
              AND NOT EXISTS (
                  SELECT 1 FROM mlb.pitcher_game_pitches p
                  WHERE p.mlb_game_pk = g.mlb_game_pk
              )
            ORDER BY g.game_date
        """), {"since": since}).fetchall()

    if not rows:
        print("  Aucun boxscore à fetcher.")
        return 0

    print(f"  {len(rows)} boxscores à fetcher...")
    stored = 0

    for i, row in enumerate(rows):
        pk = row.mlb_game_pk
        try:
            data = _get(f"/game/{pk}/boxscore")
        except Exception as e:
            print(f"  Erreur boxscore {pk}: {e}")
            continue

        records = []
        for side in ("home", "away"):
            team_data = data.get("teams", {}).get(side, {})
            pitcher_ids = team_data.get("pitchers", [])
            players = team_data.get("players", {})

            for pid in pitcher_ids:
                p_data = players.get(f"ID{pid}", {})
                name   = p_data.get("person", {}).get("fullName", "")
                pstats = p_data.get("stats", {}).get("pitching", {})
                if not pstats:
                    continue

                slug = player_map.get(_normalize_name(name))
                if not slug:
                    continue

                # innings_pitched est au format "6.2" (6 manches + 2 outs)
                ip_str = str(pstats.get("inningsPitched") or "0.0")
                try:
                    whole, frac = ip_str.split(".") if "." in ip_str else (ip_str, "0")
                    ip_outs = int(whole) * 3 + int(frac)
                except (ValueError, TypeError):
                    ip_outs = 0

                records.append({
                    "player_slug":          slug,
                    "game_date":            row.game_date,
                    "mlb_game_pk":          pk,
                    "pitches":              int(pstats.get("numberOfPitches") or 0) or None,
                    "strikes":              int(pstats.get("strikes")         or 0) or None,
                    "batters_faced":        int(pstats.get("battersFaced")    or 0) or None,
                    "innings_pitched_outs": ip_outs or None,
                })

        if records:
            with engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM mlb.pitcher_game_pitches WHERE mlb_game_pk = :pk"
                ), {"pk": pk})
            df = pd.DataFrame(records)
            df.to_sql(
                "pitcher_game_pitches", engine, schema="mlb",
                if_exists="append", index=False,
                method="multi",
            )
            stored += len(records)

        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{len(rows)} boxscores traités ({stored} lanceurs)")

    print(f"  {stored} lignes → mlb.pitcher_game_pitches")
    return stored


# ── Entrée publique ───────────────────────────────────────────────────────────

def run(engine=None, since: datetime | None = None) -> None:
    if engine is None:
        engine = create_engine(DB_URL)
    if since is None:
        now = datetime.now(timezone.utc)
        since = now.replace(month=SEASON_START_MONTH, day=1,
                            hour=0, minute=0, second=0, microsecond=0)
        if since > now:
            since = since.replace(year=now.year - 1)

    print(f"  Depuis : {since.date()}")

    print("\n  [1/4] Mapping équipes...")
    team_map = build_team_map(engine)

    print("\n  [2/4] Mapping joueurs...")
    player_map = build_player_map(engine)
    print(f"  {len(player_map)} joueurs indexés")

    print("\n  [3/4] Résolution gamePk...")
    ensure_schema(engine)
    resolve_gamepks(engine, team_map, since)

    print("\n  [4/4] Fetch pitch counts (boxscores)...")
    fetch_pitch_counts(engine, player_map, since)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch pitch counts via MLB Stats API")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--days", type=int, default=None,
                     help="Récupère les N derniers jours")
    grp.add_argument("--full", action="store_true",
                     help="Tout l'historique depuis mars de l'année en cours")
    args = parser.parse_args()

    if args.days:
        _since = datetime.now(timezone.utc) - timedelta(days=args.days)
    else:
        _since = None   # défaut : depuis début de saison

    run(since=_since)
