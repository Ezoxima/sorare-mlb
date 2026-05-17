"""
fetch_leaderboard_history.py
----------------------------
Recupere les seuils de recompenses pour toutes les GW depuis mars 2026.

Etapes :
  1. Lit les fixture_slug depuis mlb.games (deja stockes)
  2. Pour chaque fixture : liste tous les leaderboards
  3. Pour chaque leaderboard : seuils de score par palier de recompense
  4. Sauvegarde dans data/leaderboard_rewards.parquet

Ajoute aussi les seuils Hot Streak hardcodes (pas d'API necessaire).

Usage :
    python fetch_leaderboard_history.py
    python fetch_leaderboard_history.py --since-gw 125   # depuis GW125 seulement
"""

import os
import sys
import time
import argparse
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).parent.parent / ".env")

SORARE_API = "https://api.sorare.com/graphql"
DATA_DIR   = Path(__file__).parent / "data"
OUT_FILE   = DATA_DIR / "leaderboard_rewards.parquet"
SLEEP      = 0.4   # secondes entre appels API


# ── Seuils Hot Streak (hardcoded, independants de l'API) ───────────────────────
HOT_STREAK_THRESHOLDS = [
    # rarity, score_threshold, shards, bonus_shards_per_extra_team
    ("limited",    175,   500, 250),
    ("limited",    200,  1500, 750),
    ("limited",    225,  3000, 1500),
    ("limited",    250,  6000, 2500),
    ("limited",    275, 10000, 5000),
    ("rare",       175,   200, 125),  # note: fichier source a une colonne mal alignee
    ("rare",       230,  1000, 500),
    ("rare",       250,  2000, 1000),
    ("rare",       270,  4000, 2000),
    ("rare",       290,  8000, 4000),
    ("super_rare", 220,   250, 125),
    ("super_rare", 245,   500, 250),
    ("super_rare", 260,  1000, 500),
    ("super_rare", 290,  2000, 1000),
    ("super_rare", 315,  5000, 2500),
]


def _post(query: str, headers: dict, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            r = requests.post(SORARE_API, json={"query": query},
                              headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
                raise RuntimeError(f"GraphQL errors: {data['errors']}")
            return data
        except Exception as exc:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return {}


def fetch_leaderboards(fixture_slug: str, headers: dict) -> list[dict]:
    """Liste les leaderboards d'une fixture avec leur metadata."""
    query = """
    {
      so5 {
        so5Fixture(sport: BASEBALL, slug: "%s") {
          gameWeek
          so5Leaderboards {
            slug
            displayName
            rarityType
            so5LeaderboardType
            isArena
            rewardedLineupsCount
          }
        }
      }
    }
    """ % fixture_slug
    data    = _post(query, headers)
    fixture = (data.get("data") or {}).get("so5", {}).get("so5Fixture")
    if not fixture:
        return []
    return fixture.get("so5Leaderboards") or []


def fetch_reward_tiers(leaderboard_slug: str, headers: dict) -> list[dict]:
    """Paliers de recompenses d'un leaderboard (score seuil + reward)."""
    query = """
    {
      so5 {
        so5Leaderboard(slug: "%s") {
          rewardsConfig {
            ranking {
              fromRank
              fromSo5Ranking {
                overallScore
              }
              rewardConfigs {
                id
                ... on MonetaryRewardConfig {
                  amount { usdCents }
                }
                ... on CardShardRewardConfig {
                  configRarity
                  quantity
                }
              }
            }
          }
        }
      }
    }
    """ % leaderboard_slug
    data = _post(query, headers)
    lb   = (data.get("data") or {}).get("so5", {}).get("so5Leaderboard")
    if not lb:
        return []
    cfg = (lb.get("rewardsConfig") or {})
    return cfg.get("ranking") or []


def _parse_tiers(ranking: list) -> list[dict]:
    """Aplatit les paliers en lignes simples."""
    rows = []
    for tier_idx, tier in enumerate(ranking):
        score     = (tier.get("fromSo5Ranking") or {}).get("overallScore")
        from_rank = tier.get("fromRank")
        if score is None:
            continue
        for rc in (tier.get("rewardConfigs") or []):
            if "usdCents" in str(rc):
                rows.append({
                    "tier_rank":       tier_idx + 1,
                    "from_rank":       from_rank,
                    "score_threshold": float(score),
                    "reward_type":     "monetary",
                    "reward_rarity":   None,
                    "reward_quantity": None,
                    "reward_usd_cents":rc.get("amount", {}).get("usdCents"),
                })
            elif "configRarity" in rc:
                rows.append({
                    "tier_rank":       tier_idx + 1,
                    "from_rank":       from_rank,
                    "score_threshold": float(score),
                    "reward_type":     "card_shard",
                    "reward_rarity":   rc.get("configRarity"),
                    "reward_quantity": rc.get("quantity"),
                    "reward_usd_cents":None,
                })
    return rows


def build_hot_streak_df() -> pd.DataFrame:
    """Cree le DataFrame des seuils Hot Streak (independant de l'API)."""
    rows = []
    for rarity, score, shards, bonus in HOT_STREAK_THRESHOLDS:
        rows.append({
            "source":             "hot_streak",
            "gw_int":             None,
            "gw_start":           None,
            "fixture_slug":       None,
            "leaderboard_slug":   f"hot_streak_{rarity}",
            "leaderboard_name":   f"Hot Streak — {rarity}",
            "rarity_type":        rarity,
            "is_arena":           False,
            "leaderboard_type":   "hot_streak",
            "rewarded_lineups":   None,
            "tier_rank":          None,
            "from_rank":          None,
            "score_threshold":    float(score),
            "reward_type":        "card_shard",
            "reward_rarity":      rarity,
            "reward_quantity":    shards,
            "reward_usd_cents":   None,
            "bonus_shards":       bonus,
        })
    return pd.DataFrame(rows)


def run(since_gw: int = 119) -> pd.DataFrame:
    api_key = os.getenv("API_KEY", "")
    headers = {"Content-Type": "application/json", "APIKEY": api_key}

    DB_URL = (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME')}"
    )
    engine = create_engine(DB_URL)

    # ── 1. Fixture slugs depuis la DB ────────────────────────────────────────
    with engine.connect() as con:
        fixtures = con.execute(text("""
            SELECT DISTINCT gw_int, fixture_slug, MIN(game_date)::date AS gw_start
            FROM mlb.games
            WHERE gw_int >= :gw
            GROUP BY gw_int, fixture_slug
            ORDER BY gw_int
        """), {"gw": since_gw}).fetchall()

    fixtures = [dict(r._mapping) for r in fixtures]
    print(f"  {len(fixtures)} fixtures a traiter (GW{since_gw} -> GW{fixtures[-1]['gw_int']})")

    all_rows = []

    for fix in fixtures:
        gw_int       = fix["gw_int"]
        fixture_slug = fix["fixture_slug"]
        gw_start     = fix["gw_start"]
        print(f"\n  GW{gw_int} — {fixture_slug}")

        # ── 2. Leaderboards de la fixture ────────────────────────────────────
        try:
            leaderboards = fetch_leaderboards(fixture_slug, headers)
        except Exception as e:
            print(f"    Erreur leaderboards : {e}")
            time.sleep(1)
            continue

        # Filtrer les leaderboards PVE (hot streak → geres separement)
        leaderboards = [lb for lb in leaderboards
                        if not lb.get("slug", "").lower().endswith("_pve")
                        and "hot_streak" not in lb.get("slug", "").lower()]

        print(f"    {len(leaderboards)} leaderboards")
        time.sleep(SLEEP)

        for lb in leaderboards:
            lb_slug = lb.get("slug", "")
            lb_name = lb.get("displayName", "")
            rarity  = lb.get("rarityType", "")
            is_arena= lb.get("isArena", False)
            lb_type = lb.get("so5LeaderboardType", "")
            rew_cnt = lb.get("rewardedLineupsCount")

            # ── 3. Paliers de recompenses ─────────────────────────────────────
            try:
                ranking = fetch_reward_tiers(lb_slug, headers)
            except Exception as e:
                print(f"      Erreur {lb_slug}: {e}")
                time.sleep(1)
                continue

            tiers = _parse_tiers(ranking)
            if not tiers:
                # Leaderboard sans recompenses chiffrables → on garde quand meme une ligne
                tiers = [{"tier_rank": None, "from_rank": None, "score_threshold": None,
                           "reward_type": None, "reward_rarity": None,
                           "reward_quantity": None, "reward_usd_cents": None}]

            for t in tiers:
                all_rows.append({
                    "source":           "arena",
                    "gw_int":           gw_int,
                    "gw_start":         gw_start,
                    "fixture_slug":     fixture_slug,
                    "leaderboard_slug": lb_slug,
                    "leaderboard_name": lb_name,
                    "rarity_type":      rarity,
                    "is_arena":         is_arena,
                    "leaderboard_type": lb_type,
                    "rewarded_lineups": rew_cnt,
                    "tier_rank":        t["tier_rank"],
                    "from_rank":        t["from_rank"],
                    "score_threshold":  t["score_threshold"],
                    "reward_type":      t["reward_type"],
                    "reward_rarity":    t["reward_rarity"],
                    "reward_quantity":  t["reward_quantity"],
                    "reward_usd_cents": t["reward_usd_cents"],
                    "bonus_shards":     None,
                })

            time.sleep(SLEEP)

    if not all_rows:
        print("  Aucune donnee recuperee.")
        df_arena = pd.DataFrame()
    else:
        df_arena = pd.DataFrame(all_rows)

    # ── 4. Fusion avec Hot Streak ─────────────────────────────────────────────
    df_hs  = build_hot_streak_df()
    df_out = pd.concat([df_arena, df_hs], ignore_index=True)
    df_out.to_parquet(OUT_FILE, index=False)
    print(f"\n  {len(df_arena)} lignes arena + {len(df_hs)} seuils Hot Streak -> {OUT_FILE.name}")
    return df_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-gw", type=int, default=119,
                        help="GW de depart (defaut: 119 = mars 2026)")
    args = parser.parse_args()

    print(f"[Leaderboards] Collecte depuis GW{args.since_gw}...")
    df = run(since_gw=args.since_gw)
    if not df.empty:
        print("\nApercu des seuils arena :")
        arena = df[df["source"] == "arena"].dropna(subset=["score_threshold"])
        print(arena[["gw_int","leaderboard_name","rarity_type",
                      "tier_rank","score_threshold","reward_type","reward_quantity"]]
              .sort_values(["gw_int","leaderboard_name","tier_rank"])
              .head(30)
              .to_string(index=False))
