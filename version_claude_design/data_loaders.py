import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

# ── Constantes ─────────────────────────────────────────────────────────────────

POSITION_EXACT = {
    "baseball_starting_pitcher":  "SP",
    "baseball_relief_pitcher":    "RP",
    "baseball_outfield":          "OF",
    "baseball_first_base":        "1B",
    "baseball_second_base":       "2B",
    "baseball_third_base":        "3B",
    "baseball_shortstop":         "SS",
    "baseball_catcher":           "C",
    "baseball_designated_hitter": "DH",
}
POSITION_AGG = {
    "baseball_starting_pitcher":  "SP",
    "baseball_relief_pitcher":    "RP",
    "baseball_outfield":          "OF",
    "baseball_first_base":        "CI",
    "baseball_second_base":       "MI",
    "baseball_third_base":        "CI",
    "baseball_shortstop":         "MI",
    "baseball_catcher":           "MI",
    "baseball_designated_hitter": "CI",
}
RARITY_ORDER = {"unique": 0, "super_rare": 1, "rare": 2, "limited": 3}
RARITY_COLOR = {
    "unique":     "#ac11ff",
    "super_rare": "#179eff",
    "rare":       "#de000b",
    "limited":    "#f7b100",
}
FENETRE_OPTIONS = {"5 matchs": 5, "10 matchs": 10, "20 matchs": 20}
PARIS_TZ = ZoneInfo("Europe/Paris")

MOIS_FR = ["", "jan", "fév", "mar", "avr", "mai", "jun",
           "jul", "aoû", "sep", "oct", "nov", "déc"]

# ── Chemins ────────────────────────────────────────────────────────────────────

_DATA_DIR     = Path(__file__).parent.parent / "data"
_LINEUPS_FILE = _DATA_DIR / "saved_lineups.json"

# ── API ────────────────────────────────────────────────────────────────────────

_SORARE_API = "https://api.sorare.com/graphql"


def _api_key() -> str:
    try:
        return st.secrets["API_KEY"]
    except Exception:
        env_path = Path(__file__).parent / ".." / ".env"
        load_dotenv(dotenv_path=env_path)
        return os.getenv("API_KEY", "")


# ── Loaders ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    df = pd.read_parquet(_DATA_DIR / "gallery_stats.parquet")
    df["position_exact"] = df["card_display_position"].map(POSITION_EXACT)
    df["position_agg"]   = df["card_display_position"].map(POSITION_AGG)
    df["next_game_date"] = pd.to_datetime(df["next_game_date"], utc=True, errors="coerce")
    df["moyenne"]        = pd.to_numeric(df["moyenne"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_calendar() -> pd.DataFrame:
    df = pd.read_parquet(_DATA_DIR / "calendar.parquet")
    df["next_game_date"] = pd.to_datetime(df["next_game_date"], utc=True, errors="coerce")
    df["position_exact"] = df["card_display_position"].map(POSITION_EXACT)
    df["position_agg"]   = df["card_display_position"].map(POSITION_AGG)
    df["pct_played"]     = pd.to_numeric(df["pct_played"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_card_prices() -> pd.DataFrame:
    df = pd.read_parquet(_DATA_DIR / "card_prices.parquet")
    df["position_exact"]   = df["card_display_position"].map(POSITION_EXACT)
    df["position_agg"]     = df["card_display_position"].map(POSITION_AGG)
    df["position_agg_2"]   = df["card_display_position_2"].map(POSITION_AGG) if "card_display_position_2" in df.columns else None
    df["price_in_season"]  = pd.to_numeric(df["price_in_season"],  errors="coerce")
    df["price_out_season"] = pd.to_numeric(df["price_out_season"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_leaderboard_rewards() -> pd.DataFrame:
    p = _DATA_DIR / "leaderboard_rewards.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    for col in ("score_threshold", "reward_quantity", "reward_usd_cents"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "gw_int" in df.columns:
        df["gw_int"] = pd.to_numeric(df["gw_int"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_ml_predictions() -> pd.DataFrame:
    p = _DATA_DIR / "ml_predictions.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["pred_median"] = pd.to_numeric(df["pred_median"], errors="coerce")
    df["pred_lo"]     = pd.to_numeric(df["pred_lo"],     errors="coerce")
    df["pred_hi"]     = pd.to_numeric(df["pred_hi"],     errors="coerce")
    if "n_games_gw" not in df.columns:
        df["n_games_gw"] = None
    else:
        df["n_games_gw"] = pd.to_numeric(df["n_games_gw"], errors="coerce")
    for _col in ("pred_A", "pred_B", "pred_C",
                 "platoon_factor_A", "platoon_factor_B", "platoon_factor_C"):
        if _col not in df.columns:
            df[_col] = None
        else:
            df[_col] = pd.to_numeric(df[_col], errors="coerce")
    for _col in ("pred_contextual", "park_factor", "weather_factor",
                 "opp_quality_factor", "day_night_factor", "rest_factor", "home_away_factor"):
        if _col not in df.columns:
            df[_col] = None
        else:
            df[_col] = pd.to_numeric(df[_col], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_all_players_market() -> pd.DataFrame:
    p = _DATA_DIR / "all_players_market.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    for col in ["price_limited_is", "price_limited_oos", "price_rare_is", "price_rare_oos",
                "price_sr_is", "price_sr_oos", "price_unique_is", "price_unique_oos"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_upcoming_pitchers() -> tuple[pd.DataFrame, int]:
    """Retourne (df_games, gw_int) pour le prochain fixture CLASSIC composable."""
    headers = {
        "Content-Type": "application/json",
        "APIKEY": _api_key(),
    }

    r1 = requests.post(_SORARE_API, json={"query": """{
      so5 {
        featuredSo5Fixtures(sport: BASEBALL, first: 20, eventType: CLASSIC) {
          slug gameWeek canCompose
        }
      }
    }"""}, headers=headers, timeout=30)
    r1.raise_for_status()
    fixtures = r1.json()["data"]["so5"]["featuredSo5Fixtures"]
    composable = [f for f in fixtures if f["canCompose"]]
    if not composable:
        return pd.DataFrame(), 0

    target = composable[0]
    gw_int = target["gameWeek"]

    r2 = requests.post(_SORARE_API, json={"query": """{
      so5 {
        so5Fixture(sport: BASEBALL, slug: "%s", eventType: CLASSIC) {
          anyGames {
            ... on GameOfBaseball {
              id date statusTyped
              homeTeam { slug name }
              awayTeam { slug name }
              homeProbablePitcher { slug displayName }
              awayProbablePitcher  { slug displayName }
            }
          }
        }
      }
    }""" % target["slug"]}, headers=headers, timeout=30)
    r2.raise_for_status()
    games = r2.json()["data"]["so5"]["so5Fixture"]["anyGames"]

    rows = []
    for g in games:
        if not g:
            continue
        hp = g.get("homeProbablePitcher") or {}
        ap = g.get("awayProbablePitcher")  or {}
        rows.append({
            "game_date":          g.get("date"),
            "status":             g.get("statusTyped"),
            "home_team_slug":     (g.get("homeTeam") or {}).get("slug"),
            "home_team_name":     (g.get("homeTeam") or {}).get("name"),
            "away_team_slug":     (g.get("awayTeam") or {}).get("slug"),
            "away_team_name":     (g.get("awayTeam") or {}).get("name"),
            "home_pitcher_slug":  hp.get("slug"),
            "home_pitcher_name":  hp.get("displayName"),
            "away_pitcher_slug":  ap.get("slug"),
            "away_pitcher_name":  ap.get("displayName"),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df, gw_int
    df["game_date"] = pd.to_datetime(df["game_date"], utc=True, errors="coerce")
    df = df.sort_values("game_date").reset_index(drop=True)
    return df, gw_int


@st.cache_data(ttl=3600)
def load_pitcher_stats(slugs: tuple, fenetre: int) -> pd.DataFrame:
    if not slugs:
        return pd.DataFrame()
    gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    gs  = gs[gs["player_slug"].isin(slugs) & gs["played_in_game"]].copy()
    gs["game_date"] = pd.to_datetime(gs["game_date"], utc=True, errors="coerce")
    gs["rk"] = gs.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gs = gs[gs["rk"] <= fenetre][["player_slug", "game_date"]]
    gsd = gsd[gsd["category"] == "PITCHING"].copy()
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")
    merged = gs.merge(gsd, on=["player_slug", "game_date"])
    if merged.empty:
        return pd.DataFrame(columns=["player_slug", "stat", "stat_short_name", "avg_val", "nb_matchs"])
    agg = (merged.groupby(["player_slug", "stat", "stat_short_name"])
           .agg(avg_val=("stat_value", "mean"), nb_matchs=("game_date", "nunique"))
           .reset_index())
    agg["avg_val"] = agg["avg_val"].round(2)
    return agg


@st.cache_data(ttl=3600)
def load_injured_players() -> tuple:
    df = pd.read_parquet(_DATA_DIR / "injuries.parquet")
    return tuple(df["player_slug"].tolist())


def load_saved_lineups() -> list:
    if not _LINEUPS_FILE.exists():
        return []
    with open(_LINEUPS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _persist_lineup(entry: dict) -> None:
    lineups = load_saved_lineups()
    lineups.append(entry)
    with open(_LINEUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(lineups, f, ensure_ascii=False, indent=2)


def _delete_lineup(lineup_id: str) -> None:
    lineups = [l for l in load_saved_lineups() if l.get("lineup_id") != lineup_id]
    with open(_LINEUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(lineups, f, ensure_ascii=False, indent=2)


@st.cache_data(ttl=3600)
def load_game_scores_all() -> pd.DataFrame:
    p = _DATA_DIR / "game_scores.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["gw_int"] = pd.to_numeric(df["gw_int"], errors="coerce")
    df["score"]  = pd.to_numeric(df["score"],   errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_pitcher_stats_vv(pitcher_slugs: tuple, pit_hit_pairs: tuple) -> tuple:
    if not pitcher_slugs:
        return pd.DataFrame(), pd.DataFrame()
    _cols = ["player_slug", "stat_short_name", "avg_val", "nb_matchs", "avg_sorare_score"]
    gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    gs["game_date"]  = pd.to_datetime(gs["game_date"],  utc=True, errors="coerce")
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")

    gs_p = gs[gs["player_slug"].isin(pitcher_slugs) & gs["played_in_game"]].copy()
    gs_p["rk"] = gs_p.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gs5 = gs_p[gs_p["rk"] <= 5][["player_slug", "game_date", "score"]]
    gsd_p = gsd[gsd["player_slug"].isin(pitcher_slugs) & (gsd["category"] == "PITCHING")]
    m5 = gs5.merge(gsd_p, on=["player_slug", "game_date"])
    if m5.empty:
        df_last5 = pd.DataFrame(columns=_cols)
    else:
        df_last5 = (m5.groupby(["player_slug", "stat_short_name"])
                    .agg(avg_val=("stat_value", "mean"), nb_matchs=("game_date", "nunique"), avg_sorare_score=("score", "mean"))
                    .reset_index())
        df_last5[["avg_val", "avg_sorare_score"]] = df_last5[["avg_val", "avg_sorare_score"]].round(2)

    if pit_hit_pairs:
        pairs = pd.DataFrame(pit_hit_pairs, columns=["pitcher_slug", "hitter_slug"])
        hit_slugs = set(pairs["hitter_slug"])
        gs_h = gs[gs["player_slug"].isin(hit_slugs) & gs["played_in_game"]][["player_slug", "game_date"]].rename(columns={"player_slug": "hitter_slug"})
        gs_pit = gs_p[["player_slug", "game_date", "score"]].rename(columns={"player_slug": "pitcher_slug"})
        valid = gs_pit.merge(pairs, on="pitcher_slug").merge(gs_h, on=["hitter_slug", "game_date"])
        valid = valid[["pitcher_slug", "game_date", "score"]].drop_duplicates().rename(columns={"pitcher_slug": "player_slug"})
        mvs = valid.merge(gsd_p[["player_slug", "game_date", "stat_short_name", "stat_value"]], on=["player_slug", "game_date"])
        if mvs.empty:
            df_vs = pd.DataFrame(columns=_cols)
        else:
            df_vs = (mvs.groupby(["player_slug", "stat_short_name"])
                     .agg(avg_val=("stat_value", "mean"), nb_matchs=("game_date", "nunique"), avg_sorare_score=("score", "mean"))
                     .reset_index())
            df_vs[["avg_val", "avg_sorare_score"]] = df_vs[["avg_val", "avg_sorare_score"]].round(2)
    else:
        df_vs = pd.DataFrame(columns=_cols)

    return df_last5, df_vs


@st.cache_data(ttl=3600)
def load_all_hitters_for_gw(team_slugs: tuple) -> pd.DataFrame:
    if not team_slugs:
        return pd.DataFrame(columns=["player_slug", "player_name", "team_slug", "position_exact", "agg_position"])
    pl = pd.read_parquet(_DATA_DIR / "players.parquet")
    df = pl[pl["team_slug"].isin(team_slugs) & ~pl["agg_position_1"].isin(["SP", "RP"])].copy()
    return df.rename(columns={"display_name": "player_name", "position_1": "position_exact", "agg_position_1": "agg_position"})[
        ["player_slug", "player_name", "team_slug", "position_exact", "agg_position"]
    ]


@st.cache_data(ttl=3600)
def load_matchup_stats(hitter_slugs: tuple, pitcher_slugs: tuple) -> pd.DataFrame:
    if not hitter_slugs or not pitcher_slugs:
        return pd.DataFrame()
    gs    = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd   = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    games = pd.read_parquet(_DATA_DIR / "games.parquet")
    pl    = pd.read_parquet(_DATA_DIR / "players.parquet")
    gs["game_date"]    = pd.to_datetime(gs["game_date"],    utc=True, errors="coerce")
    gsd["game_date"]   = pd.to_datetime(gsd["game_date"],   utc=True, errors="coerce")
    games["game_date"] = pd.to_datetime(games["game_date"], utc=True, errors="coerce")
    teams = pl[pl["player_slug"].isin(hitter_slugs)][["player_slug", "team_slug"]].rename(columns={"team_slug": "active_club_slug"})
    gs_h = gs[gs["player_slug"].isin(hitter_slugs) & gs["played_in_game"]][["player_slug", "game_date", "score"]].merge(teams, on="player_slug")
    m = gs_h.merge(games[["game_date", "home_team_slug", "away_team_slug", "home_probable_pitcher", "away_probable_pitcher"]], on="game_date")
    m["pitcher_slug"] = m.apply(
        lambda r: r["home_probable_pitcher"] if r["away_team_slug"] == r["active_club_slug"]
                  else (r["away_probable_pitcher"] if r["home_team_slug"] == r["active_club_slug"] else None), axis=1)
    m = m[m["pitcher_slug"].isin(pitcher_slugs)]
    gsd_h = gsd[gsd["player_slug"].isin(hitter_slugs) & (gsd["category"] == "HITTING")]
    final = m[["player_slug", "game_date", "score", "pitcher_slug"]].merge(gsd_h[["player_slug", "game_date", "stat_short_name", "stat_value"]], on=["player_slug", "game_date"])
    if final.empty:
        return pd.DataFrame(columns=["hitter_slug", "pitcher_slug", "stat_short_name", "avg_val", "nb_matchs", "avg_sorare_score"])
    result = (final.groupby(["player_slug", "pitcher_slug", "stat_short_name"])
              .agg(avg_val=("stat_value", "mean"), nb_matchs=("game_date", "nunique"), avg_sorare_score=("score", "mean"))
              .reset_index().rename(columns={"player_slug": "hitter_slug"}))
    result[["avg_val", "avg_sorare_score"]] = result[["avg_val", "avg_sorare_score"]].round(2)
    return result


@st.cache_data(ttl=3600)
def load_player_avg_scores(slugs: tuple, fenetre: int = 10) -> pd.DataFrame:
    if not slugs:
        return pd.DataFrame(columns=["player_slug", "avg_score", "nb_matchs"])
    gs = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gs = gs[gs["player_slug"].isin(slugs) & gs["played_in_game"]].copy()
    gs["game_date"] = pd.to_datetime(gs["game_date"], utc=True, errors="coerce")
    gs["rk"] = gs.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gs = gs[gs["rk"] <= fenetre]
    result = (gs.groupby("player_slug")
              .agg(avg_score=("score", "mean"), nb_matchs=("game_date", "nunique"))
              .reset_index())
    result["avg_score"] = result["avg_score"].round(1)
    return result


@st.cache_data(ttl=3600)
def load_player_history(player_slug: str, stat: str) -> pd.DataFrame:
    gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    gs_p = gs[gs["player_slug"] == player_slug][["game_date", "gw_int", "played_in_game"]].copy()
    gsd_p = gsd[(gsd["player_slug"] == player_slug) & (gsd["stat"] == stat)][["game_date", "stat_value"]]
    df = gs_p.merge(gsd_p, on="game_date", how="left")
    df["stat_value"] = df["stat_value"].fillna(0)
    df["game_date"] = pd.to_datetime(df["game_date"], utc=True, errors="coerce")
    df = df.sort_values("game_date", ascending=False).head(20)
    return df.iloc[::-1].reset_index(drop=True)


@st.cache_data(ttl=3600)
def load_db_stats(stat: str, fenetre: int, target: float = 0.0) -> pd.DataFrame:
    # Préférer le parquet tous-joueurs (20 derniers matchs joués, colonne rk incluse)
    p_db = _DATA_DIR / "game_score_details_db.parquet"
    p_gal = _DATA_DIR / "game_score_details.parquet"
    if p_db.exists():
        gsd = pd.read_parquet(p_db)
        recently_active = set(gsd[gsd["rk"] <= 10]["player_slug"])
        gsd_f = gsd[(gsd["stat"] == stat) & (gsd["rk"] <= fenetre)][
            ["player_slug", "game_date", "stat_value"]
        ]
    else:
        gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
        gsd = pd.read_parquet(p_gal)
        gs["game_date"]  = pd.to_datetime(gs["game_date"],  utc=True, errors="coerce")
        gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")
        gs_played = gs[gs["played_in_game"]].copy()
        gs_played["rk"] = gs_played.groupby("player_slug")["game_date"].rank(
            ascending=False, method="first").astype(int)
        gs_f  = gs_played[gs_played["rk"] <= fenetre][["player_slug", "game_date"]]
        gsd_f = gsd[gsd["stat"] == stat][["player_slug", "game_date", "stat_value"]]
        gsd_f = gs_f.merge(gsd_f, on=["player_slug", "game_date"])

    if gsd_f.empty:
        return pd.DataFrame(columns=["player_slug", "display_name", "position_exact",
                                     "agg_position", "team_slug", "moyenne", "nb_matchs",
                                     "nb_success"])

    _t = target if target > 0 else None
    agg = (gsd_f.groupby("player_slug")
           .agg(
               moyenne=("stat_value", "mean"),
               nb_matchs=("game_date", "nunique"),
               nb_success=("stat_value", lambda x: (x >= _t).sum() if _t else 0),
           )
           .reset_index())

    # Exclure les joueurs sans activité récente (aucun match dans les 10 derniers)
    if p_db.exists():
        agg = agg[agg["player_slug"].isin(recently_active)]

    # Métadonnées joueurs : players_seen (tous) enrichi par players (galerie, a team_slug)
    # Les joueurs galerie absents de players_seen sont ajoutés explicitement.
    pl = pd.read_parquet(_DATA_DIR / "players.parquet")
    p_seen = _DATA_DIR / "players_seen.parquet"
    if p_seen.exists():
        seen = pd.read_parquet(p_seen)
        seen_e = seen.merge(
            pl[["player_slug", "team_slug", "position_1", "agg_position_1"]],
            on="player_slug", how="left"
        )
        seen_e["position_1"]     = seen_e["position_1"].fillna(seen_e["position"])
        seen_e["agg_position_1"] = seen_e["agg_position_1"].fillna(seen_e["position"])
        seen_slugs = set(seen["player_slug"])
        gal_extra  = pl[~pl["player_slug"].isin(seen_slugs)]
        meta = pd.concat([
            seen_e[["player_slug", "display_name", "team_slug", "position_1", "agg_position_1"]],
            gal_extra[["player_slug", "display_name", "team_slug", "position_1", "agg_position_1"]],
        ], ignore_index=True)
    else:
        meta = pl[["player_slug", "display_name", "team_slug", "position_1", "agg_position_1"]].copy()

    agg = agg.merge(meta[["player_slug", "display_name", "team_slug",
                           "position_1", "agg_position_1"]],
                    on="player_slug", how="left")
    agg["display_name"]   = agg["display_name"].fillna(agg["player_slug"])
    agg["position_exact"] = agg["position_1"].map(lambda x: POSITION_EXACT.get(x, x) if x else x)
    agg["agg_position"]   = agg["agg_position_1"].map(lambda x: POSITION_AGG.get(x, x) if x else x)
    agg["moyenne"] = agg["moyenne"].round(3)
    if target > 0:
        agg["_ratio"] = agg["nb_success"] / agg["nb_matchs"].clip(lower=1)
        agg = agg.sort_values(["_ratio", "nb_success", "moyenne"], ascending=False).drop(columns="_ratio")
    else:
        agg = agg.sort_values("moyenne", ascending=False)
    return agg[["player_slug", "display_name", "position_exact", "agg_position",
                "team_slug", "moyenne", "nb_matchs", "nb_success"]]


@st.cache_data(ttl=3600)
def load_today_games(today_date: str) -> pd.DataFrame:
    games = pd.read_parquet(_DATA_DIR / "games.parquet")
    games["game_date"] = pd.to_datetime(games["game_date"], utc=True, errors="coerce")
    today = pd.Timestamp(today_date).date()
    g = games[games["game_date"].dt.date == today].copy()
    g = g.sort_values("game_date").reset_index(drop=True)
    return g


@st.cache_data(ttl=3600)
def load_top_db_players(stat_short: str, stat_long: str, fenetre: int,
                        team_slugs_today: tuple, n: int = 5,
                        target: float = 0.0, min_matchs: int = 3) -> pd.DataFrame:
    """Top N joueurs (tous joueurs DB) pour la stat donnée, parmi les équipes qui jouent aujourd'hui."""
    p_db  = _DATA_DIR / "game_score_details_db.parquet"
    p_seen = _DATA_DIR / "players_seen.parquet"
    if not p_db.exists():
        return pd.DataFrame()

    gsd = pd.read_parquet(p_db, columns=["player_slug", "game_date", "stat", "stat_short_name",
                                          "stat_value", "rk"])
    recently_active = set(gsd[gsd["rk"] <= 10]["player_slug"])
    gsd = gsd[(gsd["stat"] == stat_long) & (gsd["rk"] <= fenetre)]
    if gsd.empty:
        return pd.DataFrame()

    _t = target if target > 0 else None
    agg = (gsd.groupby("player_slug")
           .agg(moyenne=("stat_value", "mean"), nb_matchs=("game_date", "nunique"),
                nb_success=("stat_value", lambda x: (x >= _t).sum() if _t else 0))
           .reset_index())
    agg = agg[agg["nb_matchs"] >= min_matchs]

    # Filtrer sur les équipes qui jouent aujourd'hui si fourni
    if team_slugs_today:
        pl_path = _DATA_DIR / "players.parquet"
        if pl_path.exists():
            pl = pd.read_parquet(pl_path, columns=["player_slug", "team_slug"])
            if p_seen.exists():
                seen = pd.read_parquet(p_seen, columns=["player_slug"])
                # Garder tous les slugs connus (gallery + seen), filtrer par équipe uniquement pour gallery
                agg_gallery = agg.merge(pl[pl["team_slug"].isin(team_slugs_today)], on="player_slug")
                agg = agg_gallery  # hors galerie : pas de team_slug connu, on ne peut pas filtrer
            else:
                agg = agg.merge(pl[pl["team_slug"].isin(team_slugs_today)], on="player_slug")

    agg = agg[agg["player_slug"].isin(recently_active)]

    if agg.empty:
        return pd.DataFrame()

    agg["moyenne"] = agg["moyenne"].round(2)
    if target > 0:
        agg["_ratio"] = agg["nb_success"] / agg["nb_matchs"].clip(lower=1)
        agg = agg.sort_values(["_ratio", "nb_success", "moyenne"], ascending=False).drop(columns="_ratio")
    else:
        agg = agg.sort_values("moyenne", ascending=False)
    agg = agg.head(n).reset_index(drop=True)

    # Ajouter les noms
    if p_seen.exists():
        seen = pd.read_parquet(p_seen, columns=["player_slug", "display_name"])
        agg = agg.merge(seen, on="player_slug", how="left")
    pl_path = _DATA_DIR / "players.parquet"
    if pl_path.exists():
        pl = pd.read_parquet(pl_path, columns=["player_slug", "display_name"])
        agg = agg.merge(pl.rename(columns={"display_name": "_dn_gal"}), on="player_slug", how="left")
        agg["display_name"] = agg.get("display_name", pd.Series(dtype=str)).fillna(
            agg.get("_dn_gal", pd.Series(dtype=str))
        ).fillna(agg["player_slug"])
        if "_dn_gal" in agg.columns:
            agg = agg.drop(columns=["_dn_gal"])
    else:
        agg["display_name"] = agg.get("display_name", agg["player_slug"])

    return agg[["player_slug", "display_name", "moyenne", "nb_matchs", "nb_success"]]


@st.cache_data(ttl=3600)
def load_db_sparklines(player_slugs: tuple, stat_short: str, n_games: int = 10) -> dict:
    """Sparklines depuis game_score_details_db.parquet (tous joueurs). Fallback vers gallery."""
    p = _DATA_DIR / "game_score_details_db.parquet"
    if not p.exists():
        return load_stat_sparklines(player_slugs, stat_short, n_games)
    if not player_slugs:
        return {}
    gsd = pd.read_parquet(p, columns=["player_slug", "game_date", "stat_short_name", "stat_value", "rk"])
    gsd = gsd[
        gsd["player_slug"].isin(player_slugs) &
        (gsd["stat_short_name"] == stat_short) &
        (gsd["rk"] <= n_games)
    ]
    if gsd.empty:
        return {}
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")
    gsd = gsd.sort_values(["player_slug", "game_date"])
    return {
        slug: [max(0.0, float(v)) for v in grp["stat_value"].fillna(0).tolist()]
        for slug, grp in gsd.groupby("player_slug")
    }


@st.cache_data(ttl=3600)
def load_stat_sparklines(player_slugs: tuple, stat_short: str, n_games: int = 10) -> dict:
    p = _DATA_DIR / "game_score_details.parquet"
    if not p.exists() or not player_slugs:
        return {}
    gsd = pd.read_parquet(p, columns=["player_slug", "game_date", "stat_short_name", "stat_value"])
    gsd = gsd[gsd["player_slug"].isin(player_slugs) & (gsd["stat_short_name"] == stat_short)]
    if gsd.empty:
        return {}
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")
    gsd["rk"] = gsd.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gsd = gsd[gsd["rk"] <= n_games].sort_values(["player_slug", "game_date"])
    return {
        slug: [max(0.0, float(v)) for v in grp["stat_value"].fillna(0).tolist()]
        for slug, grp in gsd.groupby("player_slug")
    }


@st.cache_data(ttl=3600)
def load_pitcher_pitches() -> pd.DataFrame:
    p = _DATA_DIR / "pitcher_pitches.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["game_date"] = pd.to_datetime(df["game_date"], utc=True)
    return df


@st.cache_data(ttl=86400)
def load_team_codes() -> dict:
    p = _DATA_DIR / "teams.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p, columns=["team_slug", "team_code"])
    return dict(zip(df["team_slug"], df["team_code"].fillna("")))


def load_team_logos() -> dict:
    p = _DATA_DIR / "teams.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p, columns=["team_slug", "picture_url"])
    return dict(zip(df["team_slug"], df["picture_url"].fillna("")))


@st.cache_data(ttl=3600)
def _load_pp_today(today_date: str) -> frozenset:
    games = pd.read_parquet(_DATA_DIR / "games.parquet")
    games["game_date"] = pd.to_datetime(games["game_date"], utc=True, errors="coerce")
    today = pd.Timestamp(today_date).date()
    g = games[games["game_date"].dt.date == today]
    slugs = set()
    slugs.update(g["home_probable_pitcher"].dropna())
    slugs.update(g["away_probable_pitcher"].dropna())
    return frozenset(slugs)


# ── Helpers internes ───────────────────────────────────────────────────────────

def _team_abbr(slug: str, codes: dict) -> str:
    code = codes.get(slug, "")
    if code:
        return code
    words = (slug or "").replace("-", " ").split()
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(w[0] for w in words[:3]).upper()


def _matchup(row) -> str:
    if pd.isna(row["next_game_date"]):
        return "—"
    if row["home_away"] == "home":
        return f"vs {row['away_team_name'] or '?'}"
    if row["home_away"] == "away":
        return f"@ {row['home_team_name'] or '?'}"
    return row["home_team_name"] or row["away_team_name"] or "—"


def _game_date_str(row) -> str:
    if pd.isna(row["next_game_date"]):
        return "—"
    return row["next_game_date"].strftime("%d/%m %H:%M")


def _fmt_date_header(dt: datetime) -> str:
    now_utc = datetime.now(timezone.utc)
    delta   = (dt.date() - now_utc.date()).days
    label   = dt.strftime(f"%d {MOIS_FR[dt.month]}")
    if delta == 0:
        return f"Aujourd'hui — {label}"
    if delta == 1:
        return f"Demain — {label}"
    return label


# ── Composants sidebar ─────────────────────────────────────────────────────────

def compact_multiselect(label: str, options: list, key: str) -> list:
    opts_key = f"{key}__opts"
    prev_options = st.session_state.get(opts_key)
    st.session_state[opts_key] = options

    if key not in st.session_state:
        st.session_state[key] = list(options)
    elif prev_options != options:
        valid = [o for o in options if o in st.session_state[key]]
        st.session_state[key] = valid if valid else list(options)

    current = st.session_state[key]
    n, nc = len(options), len(current)
    if nc == 0:
        summary = "Aucune"
    elif nc >= 2 and nc < n:
        summary = f"Valeurs multiples ({nc})"
    elif nc == n:
        summary = "Toutes" if n > 1 else (current[0] if current else "—")
    else:
        summary = current[0] if current else "—"

    with st.expander(f"{label} · {summary}"):
        if st.button("Sélectionner tout", key=f"{key}__all"):
            st.session_state[key] = list(options)
            st.rerun()
        selected = st.multiselect(label, options, key=key, label_visibility="collapsed")
    return selected


# ── Composants UI ──────────────────────────────────────────────────────────────

def gen_bar_sparkline_svg(values, w=88, h=20, target=0.0) -> str:
    if not values:
        return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}"></svg>'
    n = len(values)
    effective_max = max(max(values), target) if target > 0 else max(values)
    mx = effective_max if effective_max > 0 else 1
    bar_w = max(3, (w - n + 1) // n)
    bars = ""
    for i, v in enumerate(values):
        bh = max(2, round((max(0, v) / mx) * (h - 2)))
        x  = i * (bar_w + 1)
        y  = h - bh
        alpha = round(0.35 + 0.65 * (i / max(1, n - 1)), 2)
        color = "var(--accent)" if (target <= 0 or v >= target) else "#ef4444"
        bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{color}" opacity="{alpha}" rx="1"/>'
    target_line = ""
    if target > 0:
        ty = max(1, min(h - 1, round(h - (target / mx) * (h - 2))))
        target_line = (
            f'<line x1="0" y1="{ty}" x2="{w}" y2="{ty}"'
            f' stroke="#fbbf24" stroke-width="1" stroke-dasharray="3,2" opacity="0.55"/>'
        )
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">{bars}{target_line}</svg>'


def gen_sparkline_svg(values, w=160, h=24, color="var(--accent)") -> str:
    if not values:
        return ""
    mn, mx = min(values), max(values)
    span = max(0.001, mx - mn)
    pts = [(i / max(1, len(values) - 1) * w, h - ((v - mn) / span) * (h - 2) - 1) for i, v in enumerate(values)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    fill = f"{path} L{pts[-1][0]:.1f},{h} L{pts[0][0]:.1f},{h} Z"
    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" preserveAspectRatio="none">'
        f'<path d="{fill}" fill="{color}" opacity="0.1"/>'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.2"/>'
        f"</svg>"
    )


def _team_logo_html(slug: str, logos: dict, codes: dict, height: int = 15) -> str:
    url = logos.get(slug, "")
    if url:
        style = (f"height:{height}px;width:auto;vertical-align:middle;"
                 f"display:inline-block;object-fit:contain;flex-shrink:0")
        return f'<img src="{url}" style="{style}">'
    code = codes.get(slug) or _team_abbr(slug, codes)
    return f'<span class="sym">{code}</span>'


def render_ticker(df_all, sel_manager, day) -> None:
    df_games = load_today_games(str(day))
    team_codes = load_team_codes()
    team_logos = load_team_logos()

    def _team_card(slug: str) -> str:
        code = team_codes.get(slug) or _team_abbr(slug, team_codes)
        url  = team_logos.get(slug, "")
        logo = (f'<img src="{url}" style="height:20px;width:20px;object-fit:contain;display:block">'
                if url else f'<span style="font-size:11px;font-weight:700;color:var(--fg-1)">{code}</span>')
        return (f'<span class="ticker__team">{logo}'
                f'<span class="ticker__abbr">{code}</span></span>')

    if df_games.empty:
        game_items = ('<span class="ticker__item">'
                      '<span style="font-size:10px;color:var(--fg-3)">Aucun match aujourd\'hui</span>'
                      '</span>')
    else:
        parts = []
        for _, g in df_games.iterrows():
            home_slug = g.get("home_team_slug", "")
            away_slug = g.get("away_team_slug", "")
            t = g["game_date"].astimezone(PARIS_TZ).strftime("%H:%M")
            parts.append(
                f'<span class="ticker__item">'
                f'{_team_card(home_slug)}'
                f'<span class="ticker__score">'
                f'<span class="ticker__vs">VS</span>'
                f'<span class="ticker__time">{t}</span>'
                f'</span>'
                f'{_team_card(away_slug)}'
                f'</span>'
            )
        sep     = '<span class="ticker__sep"></span>'
        day_sep = '<span class="ticker__sep--day"><span></span></span>'
        if len(parts) >= 2:
            times = df_games["game_date"].tolist()
            n = len(times)
            gaps = [
                (times[i + 1] - times[i]).total_seconds() if i + 1 < n
                else (times[0] + pd.Timedelta(days=1) - times[i]).total_seconds()
                for i in range(n)
            ]
            start = (gaps.index(max(gaps)) + 1) % n
            parts = parts[start:] + parts[:start]
            game_items = sep.join(parts) + day_sep
        else:
            game_items = "".join(parts)

    st.markdown(
        f'<div class="ticker">'
        f'<div class="ticker__brand"><span class="ticker__brand-dot"></span>{day.strftime("%a %d %b").upper()}</div>'
        f'<div class="ticker__feed"><div class="ticker__feed-inner">{game_items}{game_items}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_statusbar(last_upd: str, filters_summary: str) -> None:
    st.markdown(
        f'<div class="statusbar">'
        f'<span class="statusbar__cell"><span class="dot live"></span><span class="k">CONN</span><span class="v">api.sorare.com</span></span>'
        f'<span class="statusbar__cell"><span class="k">CACHE</span><span class="v">ttl 3600s</span></span>'
        f'<span class="statusbar__cell"><span class="k">FILTERS</span><span class="v">{filters_summary}</span></span>'
        f'<span class="statusbar__spacer"></span>'
        f'<span class="statusbar__cell"><span class="k">LAST.UPD</span><span class="v">{last_upd}</span></span>'
        f'<span class="statusbar__cell"><span class="k">v</span><span class="v">2.4.0-mlb</span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_terminal_card(rank: int, row, stat_label: str, spark_values: list | None = None, picture_url: str | None = None, target: float = 0.0, show_pred: bool = True, card_suffix: str = "") -> str:
    rar_raw  = (row["card_display_rarity"] or "").lower()
    rar_css  = {"limited": "r-limited", "rare": "r-rare", "super_rare": "r-superrare", "unique": "r-unique"}.get(rar_raw, "")
    rank_css = ["r1", "r2", "r3"][rank] if rank < 3 else ""
    card_cls = f"pcard rank-{rank + 1}" if rank < 3 else "pcard"
    rank_lbl = ["#1", "#2", "#3"][rank] if rank < 3 else f"#{rank + 1}"
    pos      = row.get("position_agg") or row.get("position_exact") or "?"
    matchup  = row.get("matchup", "—")
    coup     = row.get("coup_envoi", "—")
    rar_lbl  = (row["card_display_rarity"] or "").upper()
    is_elig  = row.get("in_season_eligible")
    is_tag   = '<span class="tag is">IS</span>' if is_elig is True else ('<span class="tag classic">CLASSIC</span>' if is_elig is False else "")
    pp_tag   = '<span class="tag pp">PP</span>' if row.get("is_pp") else ""
    rar_tag  = f'<span class="tag rarity-{rar_raw}">{rar_lbl}</span>' if rar_lbl else ""
    monogram = row["player_name"].split()[-1][:3].upper()
    pred     = row.get("pred_median")
    pred_str = f"{pred:.1f}" if pred and not pd.isna(pred) else "—"

    if target > 0 and spark_values:
        n_reached = sum(1 for v in spark_values if v >= target)
        n_total   = len(spark_values)
        stat_val_html = (
            f'<div class="v pos">{n_reached}'
            f'<span style="font-size:10px;color:var(--fg-2);font-weight:400">/{n_total}</span></div>'
        )
        stat_key = "Objectif"
    else:
        stat_val_html = f'<div class="v pos">{row["moyenne"]:.2f}</div>'
        stat_key = stat_label

    art_spark = ""
    if spark_values:
        art_spark = (
            f'<div class="pcard__art-spark-wrap">'
            + gen_bar_sparkline_svg(spark_values, w=96, h=82, target=target)
            + f'</div>'
        )

    img_or_mono = (
        f'<img src="{picture_url}" class="pcard__card-img" alt="{monogram}"/>'
        if picture_url else
        f'<div class="pcard__monogram">{monogram}</div>'
    )
    _ml_cell = (
        f'<div class="cell"><div class="k">ML Pred</div><div class="v">{pred_str}</div></div>'
        if show_pred else ''
    )

    return (
        f'<div class="{card_cls}">'
        f'<div class="pcard__hd">'
        f'<span class="pcard__rank {rank_css}">{rank_lbl}</span>'
        f'<div class="pcard__head-info">'
        f'<div class="pcard__name">{row["player_name"]}{card_suffix}</div>'
        f'<div class="pcard__sub">{pos} · {matchup}</div>'
        f'</div>'
        f'<span class="pcard__rarity-dot" style="background:var(--{rar_css},#888)"></span>'
        f'</div>'
        f'<div class="pcard__art">'
        f'<div class="pcard__art-body">{img_or_mono}{art_spark}</div>'
        f'<span class="pcard__art-tag">{rar_lbl}</span>'
        f'</div>'
        f'<div class="pcard__row">'
        f'<div class="cell"><div class="k">{stat_key}</div>{stat_val_html}</div>'
        f'{_ml_cell}'
        f'<div class="cell"><div class="k">Matchs</div><div class="v dim">{int(row["nb_matchs"])}</div></div>'
        f'</div>'
        f'<div class="pcard__meta">{rar_tag}{is_tag}{pp_tag}'
        f'<span style="margin-left:auto;font-size:9px;color:var(--fg-3)">{coup}</span></div>'
        f'</div>'
    )


def render_player_card(rank: int, row, stat_label: str) -> str:
    return render_terminal_card(rank, row, stat_label)


@st.dialog("📊 Historique joueur", width="large")
def show_player_chart(player_slug: str, player_name: str, stat: str, stat_label: str, target: float):
    st.subheader(f"{player_name} — {stat_label}")

    df_hist = load_player_history(player_slug, stat)
    if df_hist.empty:
        st.warning("Aucun historique disponible pour ce joueur.")
        return

    is_dnp = (~df_hist["played_in_game"]).tolist()
    values = [float(v) for v in df_hist["stat_value"]]
    x_labels = df_hist["game_date"].dt.strftime("%d/%m").tolist()

    played_values = [v for v, d in zip(values, is_dnp) if not d]
    ymax = max(
        (max(played_values) * 1.30 if played_values else 0),
        (target * 1.15 if target > 0 else 0),
    ) or 5
    zero_h    = ymax * 0.12
    min_bar_h = zero_h * 1.25

    bar_colors = []
    for v, dnp in zip(values, is_dnp):
        if dnp:
            bar_colors.append("#4b5563")
        elif target > 0:
            bar_colors.append("#22c55e" if v >= target else "#ef4444")
        else:
            bar_colors.append("#3b82f6")

    display_y = []
    for v, dnp in zip(values, is_dnp):
        if dnp:
            display_y.append(zero_h)
        elif v == 0:
            display_y.append(0)
        else:
            display_y.append(max(v, min_bar_h))

    _N_GRAD = 25
    _ALPHA  = 0.052
    _PLOT_H = 480
    _SKIP   = 30 * ymax / _PLOT_H
    _FONT     = dict(size=16, color="rgba(0,0,0,0.88)",
                     family="Arial Black, Impact, Arial Narrow, sans-serif")
    _FONT_DNP = dict(size=12, color="rgba(255,255,255,0.90)",
                     family="Arial Black, Impact, Arial Narrow, sans-serif")

    fig = go.Figure()
    hover_labels = [
        "DNP" if d else (str(int(v)) if v == int(v) else f"{v:.2f}")
        for v, d in zip(values, is_dnp)
    ]
    fig.add_trace(go.Bar(
        x=x_labels, y=display_y,
        marker=dict(color=bar_colors, cornerradius=8, opacity=0.95,
                    line=dict(color="rgba(255,255,255,0.06)", width=1)),
        hovertemplate="%{x} · <b>%{customdata}</b><extra></extra>",
        customdata=hover_labels,
    ))

    if any(not d and v == 0 for v, d in zip(values, is_dnp)):
        fig.add_trace(go.Bar(
            x=x_labels,
            y=[zero_h if (not d and v == 0) else 0 for v, d in zip(values, is_dnp)],
            marker=dict(color="#ef4444", cornerradius=5, opacity=0.92, line_width=0),
            hoverinfo="skip", showlegend=False,
        ))

    for step in range(_N_GRAD):
        frac = (step + 1) / _N_GRAD
        fig.add_trace(go.Bar(
            x=x_labels,
            y=[max(0.0, h - _SKIP) * frac for h in display_y],
            marker=dict(color=f"rgba(10,13,24,{_ALPHA})", cornerradius=0, line_width=0),
            hoverinfo="skip", showlegend=False,
        ))

    for x, value, display_h, dnp in zip(x_labels, values, display_y, is_dnp):
        label = str(int(value)) if value == int(value) else f"{value:.2f}"
        if dnp:
            fig.add_annotation(x=x, y=display_h / 2, text="<b>DNP</b>",
                showarrow=False, yanchor="middle", xanchor="center", font=_FONT_DNP)
        elif value > 0:
            fig.add_annotation(x=x, y=display_h, text=f"<b>{label}</b>",
                showarrow=False, yanchor="top", xanchor="center", font=_FONT)
        else:
            fig.add_annotation(x=x, y=zero_h / 2, text="<b>0</b>",
                showarrow=False, yanchor="middle", xanchor="center", font=_FONT)

    n_bars = len(x_labels)
    if target > 0:
        st.markdown(
            f'<div style="text-align:right;color:#fbbf24;font-size:0.9rem;margin-bottom:4px">'
            f'Objectif : <strong>{target:g}</strong></div>',
            unsafe_allow_html=True,
        )
        fig.add_hline(y=target, line_dash="dash", line_color="#fbbf24", line_width=2)

    fig.update_layout(
        barmode="overlay",
        paper_bgcolor="#0c1014",
        plot_bgcolor="#0c1014",
        font=dict(family="JetBrains Mono, monospace", color="#aab4c2", size=10),
        xaxis=dict(
            tickfont=dict(size=max(9, 13 - max(0, n_bars - 12)), color="#6b7585", family="JetBrains Mono"),
            tickangle=-45 if n_bars > 12 else 0,
            showgrid=False, zeroline=False, showline=False,
            gridcolor="#1f2935",
        ),
        yaxis=dict(
            tickformat=".2g", gridcolor="#1f2935",
            zeroline=False, showline=False,
            tickfont=dict(size=10, color="#4a5260", family="JetBrains Mono"),
            range=[-ymax * 0.16, ymax],
        ),
        showlegend=False,
        margin=dict(t=12, b=48, l=36, r=12),
        bargap=0.28,
        height=max(380, 560 - max(0, n_bars - 10) * 8),
    )
    st.plotly_chart(fig, use_container_width=True)
    n_played = sum(1 for d in is_dnp if not d)
    st.caption(f"{n_played} matchs joués · {sum(is_dnp)} DNP sur les {len(df_hist)} derniers matchs")
