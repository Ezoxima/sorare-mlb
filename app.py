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

st.set_page_config(layout="wide", page_title="Sorare MLB", page_icon="⚾")

# ── CSS ────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@media (max-width: 768px) {
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-top: 1.5rem !important;
    }
    div[data-testid="stModal"] > div > div {
        width: 100vw !important; max-width: 100vw !important;
        min-width: 100vw !important; margin: 0 !important;
        border-radius: 0 !important;
    }
}
.player-card {
    border: 1px solid rgba(128,128,128,0.25);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 12px;
    background: rgba(255,255,255,0.03);
}
.card-header { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.card-rank   { font-size:1.6rem; line-height:1; }
.card-name   { font-size:1rem; font-weight:600; line-height:1.3; }
.card-meta   { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }
.badge {
    font-size:0.75rem; padding:2px 8px; border-radius:20px;
    background:rgba(128,128,128,0.2); white-space:nowrap;
}
.card-stats {
    display:flex; justify-content:space-between; align-items:center;
    margin-top:8px; flex-wrap:wrap; gap:4px;
}
.stat-value { font-size:1.1rem; font-weight:700; color:#4CAF50; }
.kickoff    { font-size:0.85rem; opacity:0.7; }
.game-block {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    background: rgba(255,255,255,0.02);
}
.game-title { font-size:0.95rem; font-weight:600; margin-bottom:6px; }
.game-time  { font-size:0.8rem; opacity:0.55; margin-bottom:8px; }
.player-line { display:flex; align-items:center; gap:8px; margin:4px 0; font-size:0.85rem; }
.today-chip {
    display:inline-block; font-size:0.7rem; padding:1px 7px;
    border-radius:10px; background:#22c55e22; color:#22c55e;
    border:1px solid #22c55e44; margin-left:8px;
}
</style>
""", unsafe_allow_html=True)

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
    "unique":     "#ffd700",
    "super_rare": "#ff4444",
    "rare":       "#4488ff",
    "limited":    "#cc88ff",
}
FENETRE_OPTIONS = {"5 matchs": 5, "10 matchs": 10, "20 matchs": 20}
PARIS_TZ = ZoneInfo("Europe/Paris")

MOIS_FR = ["", "jan", "fév", "mar", "avr", "mai", "jun",
           "jul", "aoû", "sep", "oct", "nov", "déc"]


# ── Data ───────────────────────────────────────────────────────────────────────

_DATA_DIR      = Path(__file__).parent / "data"
_LINEUPS_FILE  = _DATA_DIR / "saved_lineups.json"


def _api_key() -> str:
    """Retourne l'API key Sorare — st.secrets en cloud, .env en local."""
    try:
        return st.secrets["API_KEY"]
    except Exception:
        env_path = Path(__file__).parent / ".." / ".env"
        load_dotenv(dotenv_path=env_path)
        return os.getenv("API_KEY", "")


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


_SORARE_API = "https://api.sorare.com/graphql"


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

    # Last 5 outings
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

    # Vs active hitters (works if hitters are gallery players too)
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
def load_db_stats(stat: str, fenetre: int) -> pd.DataFrame:
    gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    pl  = pd.read_parquet(_DATA_DIR / "players.parquet")
    gs["game_date"]  = pd.to_datetime(gs["game_date"],  utc=True, errors="coerce")
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")
    gs_played = gs[gs["played_in_game"]].copy()
    gs_played["rk"] = gs_played.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gs_f = gs_played[gs_played["rk"] <= fenetre][["player_slug", "game_date", "position"]]
    gsd_f = gsd[gsd["stat"] == stat][["player_slug", "game_date", "stat_value"]]
    merged = gs_f.merge(gsd_f, on=["player_slug", "game_date"])
    if merged.empty:
        return pd.DataFrame(columns=["player_slug", "display_name", "position_exact", "agg_position", "team_slug", "moyenne", "nb_matchs"])
    agg = (merged.groupby("player_slug")
           .agg(position=("position", lambda x: x.mode().iloc[0] if not x.mode().empty else None),
                moyenne=("stat_value", "mean"), nb_matchs=("game_date", "nunique"))
           .reset_index())
    agg = agg.merge(pl[["player_slug", "display_name", "team_slug", "position_1", "agg_position_1"]], on="player_slug", how="left")
    agg["display_name"]    = agg["display_name"].fillna(agg["player_slug"])
    agg["position_exact"]  = agg["position_1"].map(lambda x: POSITION_EXACT.get(x, x) if x else x)
    agg["agg_position"]    = agg["agg_position_1"].map(lambda x: POSITION_AGG.get(x, x) if x else x)
    agg["moyenne"]         = agg["moyenne"].round(3)
    return agg[["player_slug", "display_name", "position_exact", "agg_position", "team_slug", "moyenne", "nb_matchs"]].sort_values("moyenne", ascending=False)


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


def render_player_card(rank: int, row, stat_label: str) -> str:
    medals = ["🥇", "🥈", "🥉"]
    medal  = medals[rank] if rank < 3 else f"#{rank + 1}"
    color  = RARITY_COLOR.get(row["card_display_rarity"].lower() if row["card_display_rarity"] else "", "#888")
    pos    = row["position_exact"] or row["position_agg"] or "?"
    matchup    = row["matchup"]
    game_date  = row["coup_envoi"]
    match_line = f"⏰ {game_date} UTC · {matchup}" if matchup != "—" else "Pas de match programmé"
    is_eligible = row.get("in_season_eligible")
    if is_eligible is True:
        is_badge = '<span class="badge" style="color:#22c55e;border:1px solid #22c55e44">IS</span>'
    elif is_eligible is False:
        is_badge = '<span class="badge" style="color:#94a3b8;border:1px solid #94a3b844">OOS</span>'
    else:
        is_badge = ""
    pp_badge = '<span class="badge" style="color:#f59e0b;border:1px solid #f59e0b44">PP</span>' if row.get("is_pp") else ""
    extra_badges = is_badge + pp_badge
    return f"""
    <div class="player-card" style="border-color:{color}55;">
        <div class="card-header">
            <div class="card-rank">{medal}</div>
            <div class="card-name">{row['player_name']}</div>
        </div>
        <div class="card-meta">
            <span class="badge" style="color:{color};border:1px solid {color}44;">{pos}</span>
            <span class="badge">{row['card_display_rarity']}</span>
            {extra_badges}
            <span class="badge">{row['gallery_manager']}</span>
        </div>
        <div style="font-size:0.78rem;opacity:0.55;margin-bottom:8px;">{match_line}</div>
        <div class="card-stats">
            <div class="stat-value">
                {row['moyenne']:.3f}
                <small style="font-size:0.7rem;font-weight:400;opacity:0.7">{stat_label}</small>
            </div>
            <div class="kickoff">📊 {int(row['nb_matchs'])} matchs</div>
        </div>
    </div>"""


# ── Graphique historique ───────────────────────────────────────────────────────

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
        xaxis=dict(
            tickfont=dict(size=max(10, 15 - max(0, n_bars - 12)),
                          color="rgba(255,255,255,0.55)"),
            tickangle=-45 if n_bars > 12 else 0,
            showgrid=False, zeroline=False, showline=False,
        ),
        yaxis=dict(
            tickformat=".2g", gridcolor="rgba(255,255,255,0.06)",
            zeroline=False, showline=False,
            tickfont=dict(size=11, color="rgba(255,255,255,0.35)"),
            range=[-ymax * 0.16, ymax],
        ),
        showlegend=False,
        margin=dict(t=15, b=50, l=40, r=15),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        bargap=0.28,
        height=max(420, 600 - max(0, n_bars - 10) * 8),
    )
    st.plotly_chart(fig, use_container_width=True)
    n_played = sum(1 for d in is_dnp if not d)
    st.caption(f"{n_played} matchs joués · {sum(is_dnp)} DNP sur les {len(df_hist)} derniers matchs")


# ── Authentification ───────────────────────────────────────────────────────────

def _check_password() -> bool:
    try:
        pwd = st.secrets["APP_PASSWORD"]
    except Exception:
        return True  # pas de secrets configurés → accès libre en local
    if st.session_state.get("_authenticated"):
        return True
    with st.form("login"):
        st.markdown("### ⚾ Sorare MLB")
        entered = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Connexion")
    if submitted:
        if entered == pwd:
            st.session_state["_authenticated"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    return False

if not _check_password():
    st.stop()

# ── Chargement ─────────────────────────────────────────────────────────────────

df_all      = load_data()
df_calendar = load_calendar()
df_prices   = load_card_prices()
df_ml       = load_ml_predictions()
df_lb       = load_leaderboard_rewards()
df_market   = load_all_players_market()

_slug_name_map: dict = (
    df_all.drop_duplicates("player_slug")
    .set_index("player_slug")["player_name"]
    .to_dict()
)

now_utc    = pd.Timestamp.now(tz="UTC")
now_paris  = now_utc.astimezone(PARIS_TZ)
today_paris = now_paris.date()

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚾ Sorare MLB")

    managers = sorted(df_all["gallery_manager"].dropna().unique())
    if len(managers) > 1:
        sel_manager = st.selectbox("Manager", managers)
    else:
        sel_manager = managers[0] if managers else None
        st.caption(f"👤 {sel_manager}")

    st.divider()
    st.caption("Filtres galerie")

    categorie = st.radio("Catégorie", ["HITTING", "PITCHING"], horizontal=True)

    stats_dispo   = (
        df_all[df_all["category"] == categorie][["stat_short_name", "stat"]]
        .drop_duplicates()
        .sort_values("stat_short_name")
    )
    stat_labels_list = stats_dispo["stat_short_name"].tolist()
    stat_keys_list   = stats_dispo["stat"].tolist()
    sel_stat_label   = st.selectbox("Statistique", stat_labels_list)
    sel_stat         = stat_keys_list[stat_labels_list.index(sel_stat_label)]

    fenetre = st.radio("Fenêtre", list(FENETRE_OPTIONS.keys()), index=1, horizontal=True)

    target = st.number_input(
        "🎯 Objectif", min_value=0.0, value=0.0, step=0.5,
        help="Seuil visuel dans le graphique historique",
    )

    st.divider()

    df_manager = df_all[df_all["gallery_manager"] == sel_manager]
    positions_dispo = sorted(df_manager["position_agg"].dropna().unique())
    sel_positions   = compact_multiselect("Positions", positions_dispo, key="filter_pos")
    raretés_dispo   = sorted(
        df_manager["card_display_rarity"].dropna().unique(),
        key=lambda r: RARITY_ORDER.get(r.lower() if r else "", 99),
    )
    sel_raretés = compact_multiselect("Raretés", raretés_dispo, key="filter_rar")

    st.divider()
    st.caption("Filtre calendrier")
    _avail_days = sorted(
        df_calendar[
            (df_calendar["gallery_manager"] == sel_manager) &
            (df_calendar["next_game_date"] >= now_utc)
        ]["next_game_date"].dt.date.unique()
    )
    _day_labels    = ["Tous les jours"] + [d.strftime("%a %d %b") for d in _avail_days]
    _sel_day_label = st.selectbox("Jour de match", _day_labels, key="sel_day")
    sel_day = (
        _avail_days[_day_labels.index(_sel_day_label) - 1]
        if _sel_day_label != "Tous les jours" else None
    )

# ── Filtrage galerie ────────────────────────────────────────────────────────────

df = df_all[
    (df_all["gallery_manager"] == sel_manager) &
    (df_all["fenetre"] == fenetre) &
    (df_all["stat"] == sel_stat) &
    (df_all["position_agg"].isin(sel_positions)) &
    (df_all["card_display_rarity"].str.lower().isin([r.lower() for r in sel_raretés]))
].copy()

df = (
    df.sort_values("moyenne", ascending=False)
    .drop_duplicates(subset=["player_name", "card_display_rarity"])
    .reset_index(drop=True)
)
df["matchup"]    = df.apply(_matchup, axis=1)
df["coup_envoi"] = df.apply(_game_date_str, axis=1)

# Stat avg par joueur pour le calendrier
stat_avg_map = (
    df_all[(df_all["fenetre"] == fenetre) & (df_all["stat"] == sel_stat)]
    .groupby("player_slug")["moyenne"]
    .first()
    .to_dict()
)

# Tab 1 : matchs pas encore commencés, jusqu'à demain 09:00 Paris
_cutoff_paris = datetime(
    today_paris.year, today_paris.month, today_paris.day, 9, 0, tzinfo=PARIS_TZ
) + pd.Timedelta(days=1)
_cutoff_utc = pd.Timestamp(_cutoff_paris).tz_convert("UTC")

_cal_today = df_calendar[
    (df_calendar["gallery_manager"] == sel_manager) &
    (df_calendar["next_game_date"] > now_utc) &
    (df_calendar["next_game_date"] < _cutoff_utc)
]
_slugs_today   = set(_cal_today["player_slug"])
_injured_slugs = set(load_injured_players())
df_today = (
    df[df["player_slug"].isin(_slugs_today) & ~df["player_slug"].isin(_injured_slugs)]
    .reset_index(drop=True)
)

# Enrichir df_today avec in_season_eligible depuis df_calendar
_is_map = (
    df_calendar[df_calendar["gallery_manager"] == sel_manager]
    .drop_duplicates("player_slug")
    .set_index("player_slug")["in_season_eligible"]
)
df_today["in_season_eligible"] = df_today["player_slug"].map(_is_map)

# PP — probable pitcher pour les matchs d'aujourd'hui
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

_pp_slugs = set(_load_pp_today(str(today_paris)))

# Source 2 : API Sorare (matchs à venir de la GW, filtrés sur aujourd'hui)
try:
    _df_pp, _ = load_upcoming_pitchers()
    if not _df_pp.empty:
        _df_pp_today = _df_pp[_df_pp["game_date"].dt.date == today_paris]
        _pp_slugs.update(_df_pp_today["home_pitcher_slug"].dropna())
        _pp_slugs.update(_df_pp_today["away_pitcher_slug"].dropna())
except Exception:
    pass

df_today["is_pp"] = df_today["player_slug"].isin(_pp_slugs)

# Predictions ML
if not df_ml.empty:
    _ml_mgr = df_ml[df_ml["gallery_manager"] == sel_manager].drop_duplicates("player_slug")
    _ml_map = _ml_mgr.set_index("player_slug")[["pred_median","pred_lo","pred_hi"]]
    df_today["pred_median"] = df_today["player_slug"].map(_ml_map["pred_median"])
    df_today["pred_lo"]     = df_today["player_slug"].map(_ml_map["pred_lo"])
    df_today["pred_hi"]     = df_today["player_slug"].map(_ml_map["pred_hi"])
else:
    df_today["pred_median"] = float("nan")
    df_today["pred_lo"]     = float("nan")
    df_today["pred_hi"]     = float("nan")

# ── Tabs ────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
    "🏆 Défis journaliers",
    "📅 Calendrier",
    "💰 Mes cartes",
    "🔍 Base de données",
    "⚾ Pitchers GW",
    "⚔️ Vis-à-vis",
    "📈 Projections GW",
    "🏗️ Équipe",
    "🎖️ Compétitions",
    "📋 Mes lineups",
    "🛒 Marché",
    "🔬 Platoon (temp)",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — MA GALERIE
# ═══════════════════════════════════════════════════════════════════════════════

with tab1:
    date_label = now_paris.strftime("%A %d %B").capitalize()
    st.caption(f"📅 {date_label} — matchs pas encore commencés")

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.markdown(
            f"<div style='font-size:0.875rem;color:rgba(49,51,63,.6);margin-bottom:4px'>Stat</div>"
            f"<div style='font-size:2rem;font-weight:700;line-height:1.2'>{sel_stat_label}"
            f"<span style='font-size:1.2rem;font-weight:400'> — {sel_stat.replace('_', ' ').title()}</span></div>",
            unsafe_allow_html=True
        )
    col_m2.metric("Fenêtre", fenetre)
    col_m3.metric("Joueurs aujourd'hui", len(df_today))

    if df_today.empty:
        st.info(
            "Aucun joueur de ta galerie ne joue aujourd'hui, "
            "ou tous les matchs du jour ont déjà commencé."
        )
    else:
        st.subheader("🥇 Suggestion d'alignement")
        top3      = df_today.head(3)
        top3_cols = st.columns(len(top3))
        for i, ((_, row), col) in enumerate(zip(top3.iterrows(), top3_cols)):
            with col:
                st.markdown(render_player_card(i, row, sel_stat_label), unsafe_allow_html=True)
                if st.button("📊 Historique", key=f"hist_top_{i}", use_container_width=True):
                    show_player_chart(row["player_slug"], row["player_name"],
                                      sel_stat, sel_stat_label, target)

        st.divider()
        st.subheader(f"📊 Classement du jour — {len(df_today)} joueur(s)")
        st.caption("Clique sur une ligne pour voir l'historique du joueur.")

        df_today["_is_lbl"] = df_today["in_season_eligible"].map(
            lambda v: "IS" if v is True else ("OOS" if v is False else "—")
        )
        df_today["_pp_lbl"] = df_today["is_pp"].map(lambda v: "PP" if v else "")

        table = df_today[[
            "player_name", "position_exact", "card_display_rarity",
            "_is_lbl", "_pp_lbl", "moyenne", "nb_matchs", "coup_envoi", "matchup",
        ]].rename(columns={
            "player_name":         "Joueur",
            "position_exact":      "Poste",
            "card_display_rarity": "Rareté",
            "_is_lbl":             "Saison",
            "_pp_lbl":             "PP",
            "moyenne":             sel_stat_label,
            "nb_matchs":           "Matchs",
            "coup_envoi":          "Heure (UTC)",
            "matchup":             "Adversaire",
        })

        event = st.dataframe(table, use_container_width=True, hide_index=True,
                             on_select="rerun", selection_mode="single-row")
        sel_rows = event.selection.rows
        if sel_rows:
            idx = sel_rows[0]
            if st.session_state.get("_tab1_sel") != idx:
                st.session_state["_tab1_sel"] = idx
                row = df_today.iloc[idx]
                show_player_chart(row["player_slug"], row["player_name"],
                                  sel_stat, sel_stat_label, target)
        else:
            st.session_state.pop("_tab1_sel", None)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CALENDRIER
# ═══════════════════════════════════════════════════════════════════════════════

with tab2:
    df_cal = df_calendar[df_calendar["gallery_manager"] == sel_manager].copy()
    df_cal = df_cal[df_cal["next_game_date"] >= now_utc].sort_values("next_game_date")
    df_cal["game_day"] = df_cal["next_game_date"].dt.date

    if df_cal.empty:
        st.info("Aucun match à venir pour ce manager.")
    else:
        all_days = sorted(df_cal["game_day"].unique())
        nb_games_today = (df_cal["game_day"] == now_utc.date()).sum()

        col_c1, col_c2, col_c3 = st.columns(3)
        col_c1.metric("Matchs à venir", len(df_cal))
        col_c2.metric("Aujourd'hui", int(nb_games_today))
        col_c3.metric("Jours de match", len(all_days))

        days_view = [sel_day] if sel_day is not None else all_days

        for day in days_view:
            day_df = df_cal[df_cal["game_day"] == day]
            if day_df.empty:
                continue
            day_dt   = pd.Timestamp(day, tz="UTC")
            is_today = (day == now_utc.date())
            today_chip = '<span class="today-chip">Aujourd\'hui</span>' if is_today else ""

            st.markdown(
                f"### {_fmt_date_header(day_dt)}{today_chip}",
                unsafe_allow_html=True,
            )

            game_groups = (
                day_df.groupby(["next_game_date", "home_team_name", "away_team_name"], sort=True)
            )

            cols_per_row = 2
            games_list   = list(game_groups)
            for row_start in range(0, len(games_list), cols_per_row):
                batch = games_list[row_start:row_start + cols_per_row]
                cols  = st.columns(len(batch))
                for col, ((gdt, home, away), gdf) in zip(cols, batch):
                    with col:
                        time_str = pd.Timestamp(gdt).strftime("%H:%M") + " UTC"
                        st.markdown(
                            f'<div class="game-block">'
                            f'<div class="game-time">⏰ {time_str}</div>'
                            f'<div class="game-title">🏠 {home}<br>✈️ {away}</div>',
                            unsafe_allow_html=True,
                        )
                        gdf_s = gdf.copy()
                        gdf_s["_avg"] = gdf_s["player_slug"].map(stat_avg_map)
                        gdf_s = gdf_s.sort_values(
                            ["in_season_eligible", "_avg"], ascending=[False, False]
                        )
                        for _, p in gdf_s.iterrows():
                            color  = RARITY_COLOR.get(
                                p["card_display_rarity"].lower() if p["card_display_rarity"] else "", "#888"
                            )
                            pos    = p["position_exact"] or p["position_agg"] or "?"
                            ha     = "🏠" if p["home_away"] == "home" else "✈️" if p["home_away"] == "away" else ""
                            pct_s  = f"{int(p['pct_played'])}%" if pd.notna(p["pct_played"]) else "—"
                            is_lbl = "IS" if p["in_season_eligible"] else "OOS"
                            is_clr = "#22c55e" if p["in_season_eligible"] else "#94a3b8"
                            avg    = stat_avg_map.get(p["player_slug"])
                            avg_s  = f" · {avg:.1f}" if avg is not None else ""
                            st.markdown(
                                f'<div class="player-line">'
                                f'<span class="badge" style="color:{color};border:1px solid {color}44;">{pos}</span>'
                                f'<span>{p["player_name"]}</span>'
                                f'<span style="opacity:0.5;font-size:0.75rem;margin-left:2px">{ha}</span>'
                                f'<span style="margin-left:auto;font-size:0.72rem;opacity:0.8;white-space:nowrap">'
                                f'{pct_s} · <span style="color:{is_clr}">{is_lbl}</span>{avg_s}'
                                f'</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — MES CARTES
# ═══════════════════════════════════════════════════════════════════════════════

with tab3:
    df_p = df_prices[df_prices["gallery_manager"] == sel_manager].copy()

    if df_p.empty:
        st.info("Aucune carte trouvée.")
    else:
        # Métriques portefeuille
        val_is  = df_p["price_in_season"].sum()
        val_oos = df_p["price_out_season"].sum()
        n_priced = df_p["price_in_season"].notna().sum()

        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        col_p1.metric("Cartes", len(df_p))
        col_p2.metric("Avec prix", int(n_priced))
        col_p3.metric("Valeur IS (EUR)", f"{val_is:.0f} €" if val_is > 0 else "—")
        col_p4.metric("Valeur OOS (EUR)", f"{val_oos:.0f} €" if val_oos > 0 else "—")

        st.divider()

        # Filtres inline
        col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
        with col_f1:
            raretés_filtre = sorted(df_p["card_display_rarity"].dropna().unique(),
                                    key=lambda r: RARITY_ORDER.get(r.lower() if r else "", 99))
            sel_rar_p = st.multiselect("Rareté", raretés_filtre, default=raretés_filtre, key="rar_prices")
        with col_f2:
            positions_filtre = sorted(df_p["position_exact"].dropna().unique())
            sel_pos_p = st.multiselect("Poste", positions_filtre, default=positions_filtre, key="pos_prices")
        with col_f3:
            tri_options = {
                "Prix IS desc":  ("price_in_season",  False),
                "Prix OOS desc": ("price_out_season", False),
                "Power desc":    ("card_power",       False),
                "Carte A-Z":     ("card_name",        True),
            }
            tri_label = st.selectbox("Trier par", list(tri_options.keys()), key="sort_prices")
            tri_col, tri_asc = tri_options[tri_label]

        df_p_f = df_p[
            df_p["card_display_rarity"].isin(sel_rar_p) &
            df_p["position_exact"].isin(sel_pos_p)
        ].sort_values(tri_col, ascending=tri_asc).reset_index(drop=True)

        table_p = df_p_f[[
            "picture_url", "card_name", "position_exact", "card_display_rarity",
            "card_power", "card_grade", "card_xp", "card_xp_needed_next_grade",
            "in_season_eligible", "price_in_season", "price_out_season", "sealable_for",
        ]].rename(columns={
            "picture_url":             "Image",
            "card_name":               "Carte",
            "position_exact":          "Poste",
            "card_display_rarity":     "Rareté",
            "card_power":              "Power",
            "card_grade":              "Grade",
            "card_xp":                 "XP",
            "card_xp_needed_next_grade": "XP prochain",
            "in_season_eligible":      "In Season",
            "price_in_season":         "Prix IS (€)",
            "price_out_season":        "Prix OOS (€)",
            "sealable_for":            "Sealable (j)",
        })

        st.dataframe(
            table_p,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Image":         st.column_config.ImageColumn(width="small"),
                "Prix IS (€)":   st.column_config.NumberColumn(format="%.2f €"),
                "Prix OOS (€)":  st.column_config.NumberColumn(format="%.2f €"),
                "Power":         st.column_config.NumberColumn(format="%.2f"),
                "In Season":     st.column_config.CheckboxColumn(),
            },
        )
        st.caption(f"{len(df_p_f)} cartes affichées")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — BASE DE DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

with tab4:
    fenetre_int = FENETRE_OPTIONS[fenetre]
    df_db = load_db_stats(sel_stat, fenetre_int)

    col_f1, col_f2 = st.columns([3, 2])
    with col_f1:
        positions_db = sorted(df_db["agg_position"].dropna().unique())
        sel_pos_db   = st.multiselect("Position", positions_db, default=positions_db, key="pos_db")
    with col_f2:
        top_n      = st.number_input("Top N", min_value=5, max_value=200, value=50, step=5)
        max_m      = int(df_db["nb_matchs"].max()) if not df_db.empty else fenetre_int
        min_matchs = st.slider("Matchs minimum", 1, max_m, min(3, max_m), key="min_m_db")

    df_db_f = (
        df_db[
            (df_db["agg_position"].isin(sel_pos_db)) &
            (df_db["nb_matchs"] >= min_matchs)
        ]
        .head(int(top_n))
        .reset_index(drop=True)
    )

    st.subheader(f"Top {int(top_n)} — {sel_stat_label} ({fenetre})")
    st.caption(f"{len(df_db_f)} joueurs affichés sur {len(df_db)} avec données.")

    if df_db_f.empty:
        st.info("Aucun joueur ne correspond aux filtres.")
    else:
        table_db = df_db_f[[
            "display_name", "position_exact", "agg_position", "team_slug", "moyenne", "nb_matchs",
        ]].rename(columns={
            "display_name":  "Joueur",
            "position_exact": "Poste",
            "agg_position":  "Position",
            "team_slug":     "Equipe",
            "moyenne":       sel_stat_label,
            "nb_matchs":     "Matchs",
        })

        event_db = st.dataframe(
            table_db, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row",
        )
        sel_db = event_db.selection.rows
        if sel_db:
            idx_db = sel_db[0]
            if st.session_state.get("_tab2_sel") != idx_db:
                st.session_state["_tab2_sel"] = idx_db
                row_db = df_db_f.iloc[idx_db]
                show_player_chart(row_db["player_slug"], row_db["display_name"],
                                  sel_stat, sel_stat_label, target)
        else:
            st.session_state.pop("_tab2_sel", None)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — PITCHERS GW
# ═══════════════════════════════════════════════════════════════════════════════

with tab5:
    try:
        df_pit, pit_gw = load_upcoming_pitchers()
    except Exception as e:
        st.error(f"Impossible de charger les pitchers : {e}")
        df_pit, pit_gw = pd.DataFrame(), 0

    if df_pit.empty:
        st.info("Aucun match programmé pour le prochain fixture CLASSIC.")
    else:
        fenetre_pit = FENETRE_OPTIONS[fenetre]

        # Tous les slugs pitchers connus
        all_pitcher_slugs = tuple(
            s for s in (
                df_pit["home_pitcher_slug"].tolist() + df_pit["away_pitcher_slug"].tolist()
            ) if s
        )

        df_pit_stats = load_pitcher_stats(all_pitcher_slugs, fenetre_pit)

        # Index de stats par joueur : {slug: {stat_short_name: avg_val}}
        pit_stat_index: dict[str, dict] = {}
        for _, r in df_pit_stats.iterrows():
            pit_stat_index.setdefault(r["player_slug"], {})[r["stat_short_name"]] = r["avg_val"]

        # Index galerie : {player_slug: {card info}}
        gallery_index = (
            df_calendar[df_calendar["gallery_manager"] == sel_manager]
            .drop_duplicates("player_slug")
            .set_index("player_slug")
            [["player_name", "card_display_rarity", "in_season_eligible"]]
            .to_dict("index")
        )

        st.subheader(f"GW{pit_gw} — Probable starters")

        n_with_pitcher = df_pit[df_pit["home_pitcher_slug"].notna() | df_pit["away_pitcher_slug"].notna()].shape[0]
        col_h1, col_h2, col_h3 = st.columns(3)
        col_h1.metric("Matchs programmés", len(df_pit))
        col_h2.metric("Avec pitcher annoncé", int(n_with_pitcher))
        col_h3.metric("Dans ma galerie", int(sum(
            1 for s in all_pitcher_slugs if s in gallery_index
        )))

        st.divider()

        # Filtres rapides
        col_flt1, col_flt2 = st.columns([2, 3])
        with col_flt1:
            show_only_gallery = st.checkbox("Galerie uniquement", value=False, key="pit_gallery_only")
        with col_flt2:
            stat_keys_pit = sorted(df_pit_stats["stat_short_name"].dropna().unique())
            if stat_keys_pit:
                sel_pit_stats = st.multiselect(
                    "Stats à afficher", stat_keys_pit,
                    default=[s for s in ["K", "IP", "ERA", "H", "BB", "ER"] if s in stat_keys_pit],
                    key="pit_stats",
                )
            else:
                sel_pit_stats = []

        st.divider()

        def _render_pitcher(slug: str | None, name: str | None, team_name: str, is_home: bool):
            if not slug and not name:
                st.markdown(
                    f'<div style="font-size:0.8rem;opacity:0.4;padding:8px 0">Pitcher non annoncé</div>',
                    unsafe_allow_html=True,
                )
                return

            card = gallery_index.get(slug or "")
            rarity = (card or {}).get("card_display_rarity", "")
            color  = RARITY_COLOR.get(rarity.lower() if rarity else "", "#555")
            is_eligible = (card or {}).get("in_season_eligible")
            display_name = (card or {}).get("player_name") or name or slug or "?"

            border = f"border-left: 3px solid {color};" if card else "border-left: 3px solid #333;"
            ha_icon = "🏠" if is_home else "✈️"

            is_badge = ""
            if card:
                is_lbl = "IS" if is_eligible else "OOS"
                is_clr = "#22c55e" if is_eligible else "#94a3b8"
                is_badge = f'<span style="font-size:0.72rem;color:{is_clr};margin-left:6px">{is_lbl}</span>'

            stats_html = ""
            if sel_pit_stats and slug and slug in pit_stat_index:
                parts = []
                for s in sel_pit_stats:
                    val = pit_stat_index[slug].get(s)
                    if val is not None:
                        parts.append(f'<span style="margin-right:10px"><b>{val:.2f}</b><span style="opacity:0.55;font-size:0.72rem"> {s}</span></span>')
                if parts:
                    stats_html = f'<div style="font-size:0.8rem;margin-top:4px;padding-left:2px">{"".join(parts)}</div>'

            st.markdown(
                f'<div style="{border}padding:8px 12px;margin:4px 0;background:rgba(255,255,255,0.02);border-radius:0 8px 8px 0;">'
                f'<div style="font-size:0.75rem;opacity:0.45;margin-bottom:2px">{ha_icon} {team_name}</div>'
                f'<div style="font-size:0.9rem;font-weight:600">{display_name}{is_badge}</div>'
                f'{stats_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Grouper par jour
        df_pit["game_day"] = df_pit["game_date"].dt.date
        pit_days = sorted(df_pit["game_day"].unique())

        for day in pit_days:
            day_df = df_pit[df_pit["game_day"] == day]

            if show_only_gallery:
                day_df = day_df[
                    day_df["home_pitcher_slug"].isin(gallery_index) |
                    day_df["away_pitcher_slug"].isin(gallery_index)
                ]
            if day_df.empty:
                continue

            day_dt = pd.Timestamp(day, tz="UTC")
            is_today = (day == now_utc.date())
            today_chip = '<span class="today-chip">Aujourd\'hui</span>' if is_today else ""
            st.markdown(f"### {_fmt_date_header(day_dt)}{today_chip}", unsafe_allow_html=True)

            cols_per_row = 2
            game_list = list(day_df.iterrows())
            for row_start in range(0, len(game_list), cols_per_row):
                batch = game_list[row_start:row_start + cols_per_row]
                cols  = st.columns(len(batch))
                for col, (_, g) in zip(cols, batch):
                    with col:
                        time_str = g["game_date"].strftime("%H:%M") + " UTC"
                        st.markdown(
                            f'<div class="game-block">'
                            f'<div class="game-time">⏰ {time_str}</div>'
                            f'<div class="game-title">🏠 {g["home_team_name"]}<br>✈️ {g["away_team_name"]}</div>',
                            unsafe_allow_html=True,
                        )
                        _render_pitcher(g["home_pitcher_slug"], g["home_pitcher_name"], g["home_team_name"], is_home=True)
                        _render_pitcher(g["away_pitcher_slug"], g["away_pitcher_name"], g["away_team_name"], is_home=False)
                        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — VIS-A-VIS
# ═══════════════════════════════════════════════════════════════════════════════

with tab6:
    try:
        df_vv, vv_gw = load_upcoming_pitchers()
    except Exception as e:
        st.error(f"Impossible de charger les matchs : {e}")
        df_vv, vv_gw = pd.DataFrame(), 0

    if df_vv.empty:
        st.info("Aucun match programmé pour le prochain fixture CLASSIC.")
    else:
        # Galerie hitters (hitters uniquement, sans SP/RP)
        gal_hitters = (
            df_calendar[
                (df_calendar["gallery_manager"] == sel_manager) &
                df_calendar["active_club_slug"].notna() &
                ~df_calendar["position_agg"].isin(["SP", "RP"])
            ]
            .drop_duplicates("player_slug")
        )
        gal_set    = set(gal_hitters["player_slug"])
        gal_is_map = gal_hitters.set_index("player_slug")["in_season_eligible"].to_dict()
        gal_rar_map = gal_hitters.set_index("player_slug")["card_display_rarity"].to_dict()

        # Toutes les équipes de la GW
        _gw_teams = tuple(set(
            df_vv["home_team_slug"].dropna().tolist() +
            df_vv["away_team_slug"].dropna().tolist()
        ))

        # Bouton pour charger tous les joueurs (galerie par défaut)
        if "vv_all_loaded" not in st.session_state:
            st.session_state["vv_all_loaded"] = False

        _col_b, _col_reset = st.columns([4, 1])
        with _col_b:
            if not st.session_state["vv_all_loaded"]:
                if st.button("⬇️ Charger tous les joueurs", key="vv_load_all"):
                    st.session_state["vv_all_loaded"] = True
                    st.rerun()
            else:
                st.caption("✅ Tous les joueurs chargés")
        with _col_reset:
            if st.session_state["vv_all_loaded"]:
                if st.button("Ma galerie", key="vv_gal_only"):
                    st.session_state["vv_all_loaded"] = False
                    st.rerun()

        show_gallery_only = not st.session_state["vv_all_loaded"]

        # Hitters à afficher
        if show_gallery_only:
            _hitters_df = (
                gal_hitters[["player_slug", "player_name", "active_club_slug",
                              "position_exact", "position_agg"]]
                .rename(columns={"active_club_slug": "team_slug", "position_agg": "agg_position"})
                .copy()
            )
            _hitters_df["in_gallery"]          = True
            _hitters_df["in_season_eligible"]  = _hitters_df["player_slug"].map(gal_is_map)
            _hitters_df["card_display_rarity"] = _hitters_df["player_slug"].map(gal_rar_map)
        else:
            _hitters_df = load_all_hitters_for_gw(_gw_teams)
            _hitters_df["in_gallery"]          = _hitters_df["player_slug"].isin(gal_set)
            _hitters_df["in_season_eligible"]  = _hitters_df["player_slug"].map(gal_is_map)
            _hitters_df["card_display_rarity"] = _hitters_df["player_slug"].map(gal_rar_map)

        # Index équipe → liste de hitters
        team_to_hitters: dict[str, list] = {}
        for _, h in _hitters_df.iterrows():
            team_to_hitters.setdefault(h["team_slug"], []).append(h)

        # Construire les paires (hitter_slug, pitcher_slug) pour la GW
        matchup_list = []  # [(hitter_row, pitcher_slug, pitcher_name, game_row)]
        for _, g in df_vv.iterrows():
            for side, pitcher_slug, pitcher_name, hitter_team in [
                ("home", g["home_pitcher_slug"], g["home_pitcher_name"], g["away_team_slug"]),
                ("away", g["away_pitcher_slug"], g["away_pitcher_name"], g["home_team_slug"]),
            ]:
                if not pitcher_slug:
                    continue
                for h in team_to_hitters.get(hitter_team, []):
                    matchup_list.append((h, pitcher_slug, pitcher_name, g))

        # Joueurs blessés (actifs) — _injured_slugs défini au niveau global
        injured_slugs = _injured_slugs

        # Stats historiques — galerie seule en mode rapide, tous en mode étendu
        if matchup_list:
            p_slugs     = tuple({m[1] for m in matchup_list})
            gal_h_slugs = tuple({m[0]["player_slug"] for m in matchup_list
                                  if m[0].get("in_gallery", False)})
            all_h_slugs = tuple({m[0]["player_slug"] for m in matchup_list})
            h_slugs     = all_h_slugs if not show_gallery_only else gal_h_slugs
            df_mu = load_matchup_stats(h_slugs, p_slugs)
            # Index hitter×pitcher: {(hitter_slug, pitcher_slug): {stat: avg, _nb, _score}}
            mu_idx: dict = {}
            for _, r in df_mu.iterrows():
                key = (r["hitter_slug"], r["pitcher_slug"])
                mu_idx.setdefault(key, {"_nb": 0, "_score": None})[r["stat_short_name"]] = r["avg_val"]
                mu_idx[key]["_nb"] = int(r["nb_matchs"])
                if pd.notna(r["avg_sorare_score"]):
                    mu_idx[key]["_score"] = float(r["avg_sorare_score"])

            # Paires (pitcher, hitter actif) pour les stats vs lineup actif
            _pitcher_active: dict[str, set] = {}
            for h, pitcher_slug, _, _ in matchup_list:
                h_slug = h["player_slug"]
                if h_slug not in injured_slugs:
                    _pitcher_active.setdefault(pitcher_slug, set()).add(h_slug)
            pit_hit_pairs = tuple(
                (ps, hs)
                for ps, hset in _pitcher_active.items()
                for hs in hset
            )

            # Stats pitcher : 5 derniers matchs + vs lineup actif (hors blessés)
            df_pit_gen, df_pit_vs = load_pitcher_stats_vv(p_slugs, pit_hit_pairs)

            def _build_pit_idx(df: pd.DataFrame) -> dict:
                idx: dict = {}
                for _, r in df.iterrows():
                    slug = r["player_slug"]
                    idx.setdefault(slug, {"_nb": 0, "_score": None})[r["stat_short_name"]] = r["avg_val"]
                    idx[slug]["_nb"] = int(r["nb_matchs"])
                    if pd.notna(r["avg_sorare_score"]):
                        idx[slug]["_score"] = float(r["avg_sorare_score"])
                return idx

            pit_gen_idx: dict = _build_pit_idx(df_pit_gen)
            pit_vs_idx:  dict = _build_pit_idx(df_pit_vs)
        else:
            df_mu, mu_idx = pd.DataFrame(), {}
            pit_gen_idx, pit_vs_idx = {}, {}

        SHOW_HIT_STATS = ["H", "HR", "K", "BB", "RBI", "SB"]
        SHOW_PIT_STATS = ["IP", "SO", "HA", "ER", "BB"]

        def _pit_stats_line(stats_dict: dict, label: str) -> str:
            nb = stats_dict.get("_nb", 0)
            if nb == 0:
                return ""
            score_val  = stats_dict.get("_score")
            score_html = (
                f'<b style="color:#4CAF50">{score_val:.1f} pts</b>'
                f'<span style="opacity:0.4;font-size:0.68rem"> moy</span>'
                f'<span style="opacity:0.2;margin:0 5px">|</span>'
                if score_val is not None else ""
            )
            parts = []
            for s in SHOW_PIT_STATS:
                v = stats_dict.get(s)
                if v is not None:
                    parts.append(
                        f'<b>{v:.1f}</b>'
                        f'<span style="opacity:0.5;font-size:0.68rem"> {s}</span>'
                    )
            return (
                f'<div style="font-size:0.75rem;padding:3px 0 3px 10px;opacity:0.8;'
                f'border-left:2px solid rgba(128,128,128,0.25);margin:3px 0 2px 0">'
                f'<span style="opacity:0.45;font-size:0.68rem">{label} '
                f'({nb} sortie{"s" if nb > 1 else ""})</span>'
                f'<span style="opacity:0.2;margin:0 5px">|</span>'
                f'{score_html}'
                f'<span style="letter-spacing:0.5px">{"  ·  ".join(parts)}</span>'
                f'</div>'
            )

        st.subheader(f"GW{vv_gw} — Hitters vs. Probable Starters")

        n_matchups = len({(m[0]["player_slug"], m[1]) for m in matchup_list})
        n_with_history = sum(1 for m in matchup_list
                             if (m[0]["player_slug"], m[1]) in mu_idx)
        col_v1, col_v2, col_v3 = st.columns(3)
        col_v1.metric("Paires hitter/pitcher", n_matchups)
        col_v2.metric("Avec historique", n_with_history)
        col_v3.metric("Matchs dans la GW", len(df_vv))

        st.divider()

        # Filtre : afficher uniquement les paires avec historique
        show_hist_only = st.checkbox("Afficher uniquement les matchups avec historique", value=False, key="vv_hist")

        # Grouper par match (pitcher = pivot de la vue)
        df_vv["game_day"] = df_vv["game_date"].dt.date
        vv_days = sorted(df_vv["game_day"].unique())

        for day in vv_days:
            day_df = df_vv[df_vv["game_day"] == day]
            day_dt = pd.Timestamp(day, tz="UTC")
            is_today = (day == now_utc.date())
            chip = '<span class="today-chip">Aujourd\'hui</span>' if is_today else ""
            st.markdown(f"### {_fmt_date_header(day_dt)}{chip}", unsafe_allow_html=True)

            for _, g in day_df.iterrows():
                time_str = g["game_date"].strftime("%H:%M") + " UTC"

                for side, pitcher_slug, pitcher_name, hitter_team_slug, opp_team_name in [
                    ("home", g["home_pitcher_slug"], g["home_pitcher_name"],
                     g["away_team_slug"], g["away_team_name"]),
                    ("away", g["away_pitcher_slug"], g["away_pitcher_name"],
                     g["home_team_slug"], g["home_team_name"]),
                ]:
                    hitters_facing = team_to_hitters.get(hitter_team_slug, [])
                    if not pitcher_slug or not hitters_facing:
                        continue

                    visible = [
                        h for h in hitters_facing
                        if not show_hist_only or (h["player_slug"], pitcher_slug) in mu_idx
                    ]
                    if not visible:
                        continue

                    ha_icon = "🏠" if side == "home" else "✈️"
                    pitcher_display = pitcher_name or pitcher_slug or "?"

                    gen_stats = pit_gen_idx.get(pitcher_slug, {})
                    vs_stats  = pit_vs_idx.get(pitcher_slug, {})
                    gen_line  = _pit_stats_line(gen_stats, "5 derniers matchs")
                    vs_line   = _pit_stats_line(vs_stats,  "Vs lineup actif")

                    # Construire le HTML de tous les hitters en une seule passe
                    hitters_html_parts = []
                    for h in sorted(
                        visible,
                        key=lambda x: (not x.get("in_gallery", False), x["player_name"]),
                    ):
                        h_slug     = h["player_slug"]
                        in_gallery = h.get("in_gallery", False)
                        color      = RARITY_COLOR.get(
                            (h.get("card_display_rarity") or "").lower(), "#888"
                        ) if in_gallery else "#555"
                        pos        = h.get("position_exact") or h.get("agg_position") or "?"
                        is_eligible = h.get("in_season_eligible")
                        if in_gallery and is_eligible is True:
                            is_html = '<span style="font-size:0.72rem;color:#22c55e;margin-left:4px">IS</span>'
                        elif in_gallery and is_eligible is False:
                            is_html = '<span style="font-size:0.72rem;color:#94a3b8;margin-left:4px">OOS</span>'
                        else:
                            is_html = ""
                        gal_star = '<span style="font-size:0.65rem;color:#f59e0b;margin-left:3px">★</span>' if in_gallery else ""

                        hist = mu_idx.get((h_slug, pitcher_slug), {})
                        nb   = hist.get("_nb", 0)

                        if nb > 0:
                            score_val  = hist.get("_score")
                            score_html = (
                                f'<b style="color:#4CAF50;font-size:0.9rem">{score_val:.1f} pts</b>'
                                f'<span style="opacity:0.4;font-size:0.7rem"> moy Sorare</span>'
                                f'<span style="opacity:0.25;margin:0 6px">|</span>'
                                if score_val is not None else ""
                            )
                            stat_parts = "".join(
                                f'<span style="margin-right:8px"><b>{hist[s]:.2f}</b>'
                                f'<span style="opacity:0.5;font-size:0.7rem"> {s}</span></span>'
                                for s in SHOW_HIT_STATS if s in hist
                            )
                            stats_line = (
                                f'<div style="font-size:0.78rem;margin-top:2px;padding-left:28px;opacity:0.85">'
                                f'<span style="opacity:0.5;font-size:0.7rem">{nb} match{"s" if nb > 1 else ""}</span>'
                                f'<span style="margin:0 6px;opacity:0.25">|</span>'
                                f'{score_html}{stat_parts}</div>'
                            )
                        else:
                            stats_line = (
                                '<div style="font-size:0.72rem;opacity:0.35;padding-left:28px">'
                                'Pas d\'historique vs ce pitcher</div>'
                            ) if in_gallery else ""

                        hitters_html_parts.append(
                            f'<div class="player-line" style="flex-wrap:wrap">'
                            f'<span class="badge" style="color:{color};border:1px solid {color}44">{pos}</span>'
                            f'<span style="font-weight:{"600" if in_gallery else "400"}'
                            f';opacity:{"1" if in_gallery else "0.65"}">{h["player_name"]}</span>'
                            f'{gal_star}{is_html}</div>'
                            f'{stats_line}'
                        )

                    # Un seul appel st.markdown pour tout le bloc pitcher
                    st.markdown(
                        f'<div class="game-block">'
                        f'<div class="game-time">⏰ {time_str} — {g["home_team_name"]} vs {g["away_team_name"]}</div>'
                        f'<div class="game-title">{ha_icon} SP : <b>{pitcher_display}</b>'
                        f'<span style="opacity:0.45;font-weight:400;font-size:0.8rem"> · face aux hitters de {opp_team_name}</span>'
                        f'</div>'
                        f'{gen_line}{vs_line}'
                        f'{"".join(hitters_html_parts)}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7 — PROJECTIONS GW
# ═══════════════════════════════════════════════════════════════════════════════

with tab7:
    try:
        df_p7, gw7 = load_upcoming_pitchers()
    except Exception as e:
        st.error(f"Impossible de charger les matchs : {e}")
        df_p7, gw7 = pd.DataFrame(), 0

    if df_p7.empty:
        st.info("Aucun match programmé pour le prochain fixture CLASSIC.")
    else:
        _gw_teams7 = set(df_p7["home_team_slug"].dropna()) | set(df_p7["away_team_slug"].dropna())
        _gw_pit_slugs7 = set(df_p7["home_pitcher_slug"].dropna()) | set(df_p7["away_pitcher_slug"].dropna())

        # Galerie hitters & SP dans cette GW
        _gal_h7 = (
            df_calendar[
                (df_calendar["gallery_manager"] == sel_manager) &
                df_calendar["active_club_slug"].isin(_gw_teams7) &
                ~df_calendar["position_agg"].isin(["SP", "RP"])
            ]
            .drop_duplicates("player_slug")
        )
        _gal_sp7 = (
            df_calendar[
                (df_calendar["gallery_manager"] == sel_manager) &
                df_calendar["player_slug"].isin(_gw_pit_slugs7)
            ]
            .drop_duplicates("player_slug")
        )

        _h_slugs7    = tuple(_gal_h7["player_slug"])
        _p_slugs7    = tuple(_gal_sp7["player_slug"])
        _all_p7      = tuple(_gw_pit_slugs7)

        # Matchup stats : hitters galerie vs tous les pitchers de la GW
        df_mu7 = load_matchup_stats(_h_slugs7, _all_p7)
        mu7: dict = {}
        for _, r in df_mu7.iterrows():
            if pd.notna(r["avg_sorare_score"]):
                mu7[(r["hitter_slug"], r["pitcher_slug"])] = float(r["avg_sorare_score"])

        # Score moyen général des hitters (fallback si pas d'historique vs pitcher)
        _fen7      = FENETRE_OPTIONS[fenetre]
        df_havg7   = load_player_avg_scores(_h_slugs7, _fen7)
        havg7      = df_havg7.set_index("player_slug")["avg_score"].to_dict()

        # Score moyen des SP galerie (5 derniers matchs)
        df_pgen7, _ = load_pitcher_stats_vv(_p_slugs7, ())
        pavg7: dict = (
            df_pgen7.drop_duplicates("player_slug")
            .set_index("player_slug")["avg_sorare_score"]
            .dropna()
            .to_dict()
        ) if not df_pgen7.empty else {}

        # Calendrier par équipe : team_slug → [(pitcher_slug|None, opp_name, game_date)]
        # On inclut TOUS les matchs, même sans pitcher annoncé (fallback sur avg général)
        team_sched7: dict = {}
        for _, g in df_p7.iterrows():
            hts, ats = g["home_team_slug"], g["away_team_slug"]
            gdt = g["game_date"]
            if hts:
                team_sched7.setdefault(hts, []).append({
                    "pitcher_slug": g["away_pitcher_slug"] or None,
                    "opp_name":     g["away_team_name"],
                    "game_date":    gdt,
                })
            if ats:
                team_sched7.setdefault(ats, []).append({
                    "pitcher_slug": g["home_pitcher_slug"] or None,
                    "opp_name":     g["home_team_name"],
                    "game_date":    gdt,
                })

        # Map ML predictions pour cette GW
        _ml7: dict = {}
        if not df_ml.empty:
            _ml7 = (
                df_ml[df_ml["gallery_manager"] == sel_manager]
                .drop_duplicates("player_slug")
                .set_index("player_slug")[["pred_median","pred_lo","pred_hi"]]
                .to_dict("index")
            )

        # Calcul des projections
        proj7 = []

        for _, row in _gal_h7.iterrows():
            h_slug  = row["player_slug"]
            h_team  = row["active_club_slug"]
            games   = sorted(team_sched7.get(h_team, []), key=lambda x: x["game_date"])
            total   = 0.0
            nb_g    = 0
            parts   = []
            for gm in games:
                ps    = gm["pitcher_slug"]
                score = (mu7.get((h_slug, ps)) if ps else None) or havg7.get(h_slug)
                src   = "🎯" if ps and (h_slug, ps) in mu7 else "~"
                if score is not None:
                    total += score
                    nb_g  += 1
                    parts.append(f"{src}{score:.1f} vs {gm['opp_name']}")

            ml_d   = _ml7.get(h_slug)
            ml_med = round(ml_d["pred_median"] * nb_g, 1) if ml_d and nb_g > 0 else None
            import math as _math
            hw     = ((ml_d["pred_hi"] - ml_d["pred_lo"]) / 2 * _math.sqrt(nb_g)
                      if ml_d and nb_g > 0 else None)
            ml_lo  = round(ml_med - hw, 1) if ml_med is not None else None
            ml_hi  = round(ml_med + hw, 1) if ml_med is not None else None

            proj7.append({
                "player_slug":        h_slug,
                "player_name":        row["player_name"],
                "rarity":             row["card_display_rarity"] or "",
                "position":           row["position_exact"] or row["position_agg"] or "?",
                "in_season_eligible": row["in_season_eligible"],
                "category":           "Hitter",
                "nb_games":           nb_g,
                "projected_score":    round(total, 1) if nb_g > 0 else None,
                "breakdown":          "  ·  ".join(parts) if parts else "—",
                "ml_pred":            ml_med,
                "ml_lo":              ml_lo,
                "ml_hi":              ml_hi,
            })

        for _, row in _gal_sp7.iterrows():
            ps    = row["player_slug"]
            score = pavg7.get(ps)
            ml_d  = _ml7.get(ps)
            proj7.append({
                "player_slug":        ps,
                "player_name":        row["player_name"],
                "rarity":             row["card_display_rarity"] or "",
                "position":           "SP",
                "in_season_eligible": row["in_season_eligible"],
                "category":           "SP",
                "nb_games":           1 if score is not None else 0,
                "projected_score":    round(float(score), 1) if score is not None else None,
                "breakdown":          f"~{score:.1f} moy 5 derniers" if score else "—",
                "ml_pred":            ml_d["pred_median"] if ml_d else None,
                "ml_lo":              ml_d["pred_lo"]     if ml_d else None,
                "ml_hi":              ml_d["pred_hi"]     if ml_d else None,
            })

        df7 = pd.DataFrame(proj7)

        # ── Extension : tous les joueurs de la GW (via ML) ───────────────────
        import math as _math7
        _show_all7 = st.checkbox(
            "Charger les données de tous les joueurs", value=False, key="proj7_all"
        )
        if _show_all7 and not df_ml.empty:
            _already7 = set(df7["player_slug"]) if not df7.empty else set()
            _extra7   = []
            for _, _mr7 in df_ml.iterrows():   # TOUS les joueurs, pas seulement la galerie
                _s7 = _mr7["player_slug"]
                if _s7 in _already7:
                    continue
                _pos7  = str(_mr7.get("position", ""))
                _isp7  = _pos7 in ("SP", "RP",
                                   "baseball_starting_pitcher",
                                   "baseball_relief_pitcher")
                _ng7   = int(_mr7.get("n_games_gw") or 0)
                _mu7_  = float(_mr7["pred_median"] or 0)
                _mm7   = round(_mu7_ * _ng7, 1) if _ng7 > 0 else None
                _hw7   = (float(_mr7["pred_hi"]) - float(_mr7["pred_lo"])) / 2
                _hw7g  = _hw7 * _math7.sqrt(_ng7) if _ng7 > 0 else _hw7
                _in_gal7 = pd.notna(_mr7.get("gallery_manager"))
                _extra7.append({
                    "player_slug":        _s7,
                    "player_name":        _mr7["player_name"],
                    "rarity":             "" if not _in_gal7 else str(_mr7.get("position", "")),
                    "position":           _pos7,
                    "in_season_eligible": None,
                    "category":           "SP" if _isp7 else "Hitter",
                    "nb_games":           _ng7,
                    "projected_score":    None,
                    "breakdown":          "— MLB (hors galerie)" if not _in_gal7 else "— galerie / hors GW",
                    "ml_pred":            _mm7,
                    "ml_lo":              round(_mm7 - _hw7g, 1) if _mm7 else None,
                    "ml_hi":              round(_mm7 + _hw7g, 1) if _mm7 else None,
                })
            if _extra7:
                df7 = pd.concat([df7, pd.DataFrame(_extra7)], ignore_index=True)

        # ── Métriques ────────────────────────────────────────────────────────
        st.subheader(f"GW{gw7} — Projections de score")
        st.caption(
            "🎯 = score basé sur l'historique vs ce pitcher spécifique  ·  "
            f"~ = moyenne générale ({fenetre})"
        )

        col71, col72, col73 = st.columns(3)
        col71.metric("Hitters en galerie",  len(_gal_h7))
        col72.metric("SP en galerie",       len(_gal_sp7))
        if not df7.empty:
            # Priorité ML ; fallback score historique si pas de données ML
            _best_col7 = "ml_pred" if df7["ml_pred"].notna().any() else "projected_score"
            _df7_best  = df7[df7[_best_col7].notna()]
            if not _df7_best.empty:
                best7  = _df7_best.loc[_df7_best[_best_col7].idxmax()]
                _bsrc7 = "ML" if _best_col7 == "ml_pred" else "hist."
                col73.metric(
                    "Meilleure projection",
                    f"{best7[_best_col7]:.1f} pts {_bsrc7}",
                    best7["player_name"],
                )

        st.divider()

        # Filtres + tri
        col7f1, col7f2, col7f3 = st.columns([2, 2, 2])
        with col7f1:
            show_cat7 = st.multiselect(
                "Catégorie", ["Hitter", "SP"],
                default=["Hitter", "SP"], key="proj7_cat",
            )
        with col7f2:
            show_is7 = st.checkbox("In Season uniquement", value=False, key="proj7_is")
        with col7f3:
            sort_by7 = st.radio(
                "Trier par", ["Prédiction ML", "Score historique"],
                horizontal=True, key="proj7_sort",
            )

        df7_f = df7[df7["category"].isin(show_cat7)].copy()
        if show_is7:
            df7_f = df7_f[df7_f["in_season_eligible"] == True]
        if sort_by7 == "Prédiction ML":
            df7_f = df7_f.sort_values("ml_pred", ascending=False, na_position="last")
        else:
            df7_f = df7_f.sort_values("projected_score", ascending=False, na_position="last")

        # ── Affichage ────────────────────────────────────────────────────────
        for _, row7 in df7_f.iterrows():
            _has_hist7 = pd.notna(row7.get("projected_score"))
            _has_ml7   = pd.notna(row7.get("ml_pred"))
            if not _has_hist7 and not _has_ml7:
                continue
            rarity7 = row7["rarity"]
            color7  = RARITY_COLOR.get(rarity7.lower(), "#888")
            is_elig7 = row7["in_season_eligible"]
            is_html7 = (
                '<span style="font-size:0.72rem;color:#22c55e;margin-left:4px">IS</span>'
                if is_elig7 is True else
                '<span style="font-size:0.72rem;color:#94a3b8;margin-left:4px">OOS</span>'
                if is_elig7 is False else ""
            )
            cat_icon7 = "⚾" if row7["category"] == "SP" else "🏏"
            nb_g7 = int(row7["nb_games"])
            games_lbl7 = f"{nb_g7} match{'s' if nb_g7 > 1 else ''}"

            ml7_val  = row7.get("ml_pred")
            ml7_lo   = row7.get("ml_lo")
            ml7_hi   = row7.get("ml_hi")
            ml7_html = (
                f'<div style="font-size:0.78rem;margin-top:4px;opacity:0.85">'
                f'<span style="color:#818cf8;font-weight:600">ML</span>'
                f' {ml7_val:.1f} pts'
                f'<span style="opacity:0.6"> IC80% [{ml7_lo:.1f}, {ml7_hi:.1f}]</span>'
                f'</div>'
                if pd.notna(ml7_val) else ""
            )
            _hist_score7 = row7.get("projected_score")
            if pd.notna(_hist_score7):
                _hist_html7 = (
                    f'<div class="stat-value">{_hist_score7:.1f}'
                    f'<small style="font-size:0.7rem;font-weight:400;opacity:0.7"> pts GW hist.</small>'
                    f'</div>'
                )
            elif nb_g7 > 0:
                _hist_html7 = (
                    f'<div class="stat-value" style="opacity:0.35">—'
                    f'<small style="font-size:0.7rem;font-weight:400"> pas d\'historique vs</small>'
                    f'</div>'
                )
            else:
                _hist_html7 = (
                    f'<div class="stat-value" style="opacity:0.35">—'
                    f'<small style="font-size:0.7rem;font-weight:400"> hors GW</small>'
                    f'</div>'
                )
            st.markdown(
                f'<div class="player-card" style="border-color:{color7}55;">'
                f'<div class="card-header">'
                f'<div class="card-rank">{cat_icon7}</div>'
                f'<div class="card-name">{row7["player_name"]}{is_html7}</div>'
                f'</div>'
                f'<div class="card-meta">'
                f'<span class="badge" style="color:{color7};border:1px solid {color7}44">'
                f'{row7["position"]}</span>'
                f'<span class="badge">{rarity7}</span>'
                f'<span class="badge">{games_lbl7}</span>'
                f'</div>'
                f'<div class="card-stats">'
                f'{_hist_html7}'
                f'<div class="kickoff" style="font-size:0.72rem;opacity:0.55">'
                f'{row7["breakdown"]}</div>'
                f'</div>'
                f'{ml7_html}'
                f'</div>',
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 8 — CONSTRUCTION D'ÉQUIPE
# ═══════════════════════════════════════════════════════════════════════════════

with tab8:
    _t8_comp, _t8_arena = st.tabs(["🏗️ Compétitions", "🏟️ Arena"])


with _t8_comp:
    from collections import Counter as _Counter

    _EMPTY_TEAM = lambda: {s: None for s in ["SP", "RP", "CI", "MI", "OF", "Flex", "Libre"]}
    _SLOT_POS   = {
        "SP":    ["SP"],
        "RP":    ["RP"],
        "CI":    ["CI"],
        "MI":    ["MI"],
        "OF":    ["OF"],
        "Flex":  ["CI", "MI", "OF"],
        "Libre": ["CI", "MI", "OF"],
    }
    _MAX_TEAMS  = {"Champions": 3, "Hot Streak": 10, "Challenger": 4}

    # ── Contrôles ─────────────────────────────────────────────────────────────
    col_m8, col_r8 = st.columns([3, 4])
    with col_m8:
        tb_mode = st.radio(
            "Mode", ["Champions", "Hot Streak", "Challenger"],
            horizontal=True, key="tb_mode",
        )
    with col_r8:
        tb_rar = st.radio(
            "Rareté", ["limited", "rare", "super_rare", "unique"],
            horizontal=True, key="tb_rar",
        )

    tb_score_src = st.radio(
        "Indicateur de score",
        ["Auto (ML → Hist.)", "Sorare GW+"],
        horizontal=True,
        key="tb_score_src",
        help="Auto : prédiction ML si dispo, sinon moyenne historique ajustée matchup.\n"
             "Sorare GW+ : score projeté par Sorare pour la prochaine GW Classic.",
    )

    _require_is = tb_mode in ("Champions", "Hot Streak")
    _max_t      = _MAX_TEAMS[tb_mode]

    # ── State par mode × rareté ────────────────────────────────────────────────
    _tb_sk = f"tb_teams_{tb_mode}_{tb_rar}"
    _DEFAULT_N_TEAMS_INIT = {"Champions": 3, "Hot Streak": 4, "Challenger": 4}
    if _tb_sk not in st.session_state:
        _n_init = _DEFAULT_N_TEAMS_INIT.get(tb_mode, 1)
        st.session_state[_tb_sk] = [_EMPTY_TEAM() for _ in range(_n_init)]
    tb_teams = st.session_state[_tb_sk]

    # ── Joueurs disponibles (hors blessés) ────────────────────────────────────
    df_tb = (
        df_prices[
            (df_prices["gallery_manager"] == sel_manager) &
            (df_prices["card_display_rarity"].str.lower() == tb_rar.lower()) &
            ~df_prices["player_slug"].isin(_injured_slugs)
        ]
        .drop_duplicates("card_name")
        .copy()
    )
    df_tb["position_agg"] = df_tb["card_display_position"].map(POSITION_AGG)
    df_tb["is_eligible"]  = df_tb["in_season_eligible"] == True

    # Scores GW projetés — on utilise TOUTE la galerie du manager comme clé de cache
    # (pas juste la rareté sélectionnée) pour que le cache reste chaud quand on change de rareté
    _all_gal_prices = df_prices[df_prices["gallery_manager"] == sel_manager]
    _all_gal_slugs  = tuple(_all_gal_prices["player_slug"].unique())
    _all_gal_h_slugs = tuple(
        _all_gal_prices[
            ~_all_gal_prices["card_display_position"].map(POSITION_AGG).isin(["SP", "RP"])
        ]["player_slug"].unique()
    )
    _avg_tb  = load_player_avg_scores(_all_gal_slugs, FENETRE_OPTIONS[fenetre])
    _smap_tb = _avg_tb.set_index("player_slug")["avg_score"].to_dict()

    try:
        _df_p8, _tb_gw8 = load_upcoming_pitchers()
    except Exception:
        _df_p8, _tb_gw8 = pd.DataFrame(), 0

    _tsched8: dict = {}
    if not _df_p8.empty:
        _tsched8 = {}
        for _, _g8 in _df_p8.iterrows():
            if _g8["home_team_slug"]:
                _tsched8.setdefault(_g8["home_team_slug"], []).append(
                    {"pitcher_slug": _g8["away_pitcher_slug"] or None}
                )
            if _g8["away_team_slug"]:
                _tsched8.setdefault(_g8["away_team_slug"], []).append(
                    {"pitcher_slug": _g8["home_pitcher_slug"] or None}
                )
        _all_p8 = tuple({
            s for col in ("home_pitcher_slug", "away_pitcher_slug")
            for s in _df_p8[col].dropna()
        })
        _df_mu8 = (
            load_matchup_stats(_all_gal_h_slugs, _all_p8)
            if _all_gal_h_slugs and _all_p8 else pd.DataFrame()
        )
        _mu8: dict = {}
        for _, _r8 in _df_mu8.iterrows():
            if pd.notna(_r8["avg_sorare_score"]):
                _mu8[(_r8["hitter_slug"], _r8["pitcher_slug"])] = float(_r8["avg_sorare_score"])

        def _gw_score8(player_slug, team_slug, position_agg) -> float:
            if position_agg in ("SP", "RP"):
                return _smap_tb.get(player_slug, 0.0)
            games8 = _tsched8.get(team_slug, [])
            total8 = 0.0
            for _gm in games8:
                ps = _gm["pitcher_slug"]
                sc = (_mu8.get((player_slug, ps)) if ps else None) or _smap_tb.get(player_slug)
                if sc:
                    total8 += sc
            return round(total8, 1) if games8 else _smap_tb.get(player_slug, 0.0)

        df_tb["proj_score_hist"] = df_tb.apply(
            lambda r: _gw_score8(r["player_slug"], r["active_club_slug"], r["position_agg"]),
            axis=1,
        )
    else:
        df_tb["proj_score_hist"] = df_tb["player_slug"].map(_smap_tb).fillna(0.0)

    # Prediction ML GW : pred_median * nb_matchs_dans_la_GW
    if not df_ml.empty:
        _ml8 = (
            df_ml[df_ml["gallery_manager"] == sel_manager]
            .drop_duplicates("player_slug")
            .set_index("player_slug")["pred_median"]
        )
        _tsched8_len = {t: len(g) for t, g in _tsched8.items()} if not _df_p8.empty else {}

        def _ml_gw_score8(player_slug, team_slug, position_agg):
            ml = _ml8.get(player_slug)
            if ml is None:
                return None
            if position_agg in ("SP", "RP"):
                return round(float(ml), 1)
            nb = _tsched8_len.get(team_slug, 1)
            return round(float(ml) * nb, 1)

        df_tb["proj_score_ml"] = df_tb.apply(
            lambda r: _ml_gw_score8(r["player_slug"], r["active_club_slug"], r["position_agg"]),
            axis=1,
        )
        # proj_score = ML si dispo, sinon historique
        df_tb["proj_score"] = df_tb["proj_score_ml"].combine_first(df_tb["proj_score_hist"])
    else:
        df_tb["proj_score_ml"] = None
        df_tb["proj_score"]    = df_tb["proj_score_hist"]

    # Indicateur Sorare GW+ : nextClassicFixtureProjectedScore brut
    _sorare_gw = pd.to_numeric(df_tb.get("next_gw_projected_score", pd.Series(dtype=float)), errors="coerce")
    df_tb["proj_score_sorare"] = _sorare_gw

    # Score de référence selon l'indicateur choisi
    if tb_score_src == "Sorare GW+":
        _base_score = _sorare_gw.fillna(0.0)
    else:
        _base_score = pd.to_numeric(df_tb["proj_score"], errors="coerce").fillna(0.0)

    # Score effectif = score de référence × power de la carte (bonus Sorare)
    _power_num = pd.to_numeric(df_tb["card_power"], errors="coerce").fillna(1.0)
    df_tb["proj_score_eff"] = (_base_score * _power_num).round(1)
    # Score effectif figé pour chaque source (pour sauvegarder les 2 suggestions au save)
    df_tb["proj_score_eff_auto"]   = (pd.to_numeric(df_tb["proj_score"],        errors="coerce").fillna(0.0) * _power_num).round(1)
    df_tb["proj_score_eff_sorare"] = (pd.to_numeric(df_tb["proj_score_sorare"], errors="coerce").fillna(0.0) * _power_num).round(1)

    # Exclure les SP non-probables quand les données de calendrier sont disponibles
    if _tsched8:
        _probable_sp_slugs = {
            g["pitcher_slug"]
            for games in _tsched8.values()
            for g in games
            if g["pitcher_slug"]
        }
        _is_sp = df_tb["position_agg"] == "SP"
        df_tb = df_tb[~_is_sp | df_tb["player_slug"].isin(_probable_sp_slugs)].reset_index(drop=True)

    # Index card_name → row
    _cl = df_tb.set_index("card_name").to_dict("index")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _fmt_opt(x: str) -> str:
        if x == "—":
            return "—"
        r    = _cl.get(x, {})
        pos  = r.get("position_exact") or "?"
        is_  = "IS" if r.get("is_eligible") else "OOS"
        try:
            sc = float(r.get("proj_score_eff") or r.get("proj_score") or 0.0)
        except (TypeError, ValueError):
            sc = 0.0
        try:
            pwr = float(r.get("card_power") or 1.0)
        except (TypeError, ValueError):
            pwr = 1.0
        if tb_score_src == "Sorare GW+":
            src = "SOR" if r.get("proj_score_sorare") is not None else "—"
        else:
            src = "ML" if r.get("proj_score_ml") is not None else "~"
        return f"{x}  [{pos} · {is_} · {sc:.0f} pts eff. · ×{pwr:.3f} · {src}]"

    def _tb_suggest(other_used: set, other_used_slugs: set, require_is: bool,
                    score_col: str = "proj_score_eff",
                    slot_pos: dict | None = None,
                    df_pool: pd.DataFrame | None = None) -> dict:
        """Greedy team builder : maximise score_col, force ≥6 IS si requis."""
        _df   = df_pool if df_pool is not None else df_tb
        _spos = slot_pos if slot_pos is not None else _SLOT_POS
        result:      dict = {}
        used:        set  = set()
        used_slugs:  set  = set()
        is_map   = _df.set_index("card_name")["is_eligible"].to_dict()
        slug_map = _df.set_index("card_name")["player_slug"].to_dict()
        slots = list(_spos.items())
        n     = len(slots)
        for i, (slot_name, valid_pos) in enumerate(slots):
            is_so_far  = sum(1 for c in used if is_map.get(c, False))
            remaining  = n - i
            must_be_is = max(0, 6 - is_so_far - (remaining - 1)) if require_is else 0

            _eff_col = score_col if score_col in _df.columns else "proj_score_eff"
            cands_all = (
                _df[
                    _df["position_agg"].isin(valid_pos) &
                    ~_df["card_name"].isin(other_used | used) &
                    ~_df["player_slug"].isin(other_used_slugs | used_slugs)
                ]
                .sort_values(_eff_col, ascending=False)
            )
            if cands_all.empty:
                result[slot_name] = None
                continue
            if must_be_is > 0:
                cands_is = cands_all[cands_all["is_eligible"]]
                cands    = cands_is if not cands_is.empty else cands_all
            else:
                cands = cands_all
            result[slot_name] = cands.iloc[0]["card_name"]
            used.add(result[slot_name])
            used_slugs.add(slug_map.get(result[slot_name], ""))
        return result

    def _team_validation(team: dict) -> tuple:
        """Retourne (is_count, max_club_count, total_score_eff, n_filled)."""
        cards = [v for v in team.values() if v]
        if not cards:
            return 0, 0, 0.0, 0
        is_c   = sum(1 for c in cards if _cl.get(c, {}).get("is_eligible", False))
        clubs  = [_cl.get(c, {}).get("active_club_slug", "") for c in cards]
        max_cl = max(_Counter(clubs).values()) if clubs else 0
        score  = sum(float(_cl.get(c, {}).get("proj_score_eff") or 0.0) for c in cards)
        return is_c, max_cl, score, len(cards)

    # ── Ajout / suppression d'équipe ──────────────────────────────────────────
    col_a8, col_d8 = st.columns([2, 3])
    with col_a8:
        if len(tb_teams) < _max_t:
            if st.button("➕ Ajouter une équipe", key="tb_add"):
                tb_teams.append(_EMPTY_TEAM())
                st.rerun()
    with col_d8:
        if len(tb_teams) > 1:
            _del_opts = [f"Équipe {i+1}" for i in range(len(tb_teams))]
            _del_sel  = st.selectbox(
                "Supprimer", _del_opts, key="tb_del_sel",
                label_visibility="collapsed",
            )
            if st.button("🗑️ Supprimer cette équipe", key="tb_del"):
                tb_teams.pop(int(_del_sel.split()[-1]) - 1)
                st.rerun()

    st.divider()

    # Map global card_name → player_slug (toutes raretés, pour détecter doublons joueur)
    _global_card_slug = (
        df_prices[df_prices["gallery_manager"] == sel_manager]
        .drop_duplicates("card_name")
        .set_index("card_name")["player_slug"]
        .to_dict()
    )

    # ── Éditeur de chaque équipe ───────────────────────────────────────────────
    for _ti, _team in enumerate(tb_teams):
        # Cartes utilisées dans les AUTRES équipes (tous modes × raretés confondus)
        _all_used_cards = {
            c
            for key, teams in st.session_state.items()
            if key.startswith("tb_teams_") and isinstance(teams, list)
            for t in teams
            for c in t.values()
            if c
        }
        # Cartes déjà utilisées dans d'autres équipes (même carte interdite cross-team)
        _other_used = _all_used_cards - {v for v in tb_teams[_ti].values() if v}

        with st.expander(f"Équipe {_ti + 1}", expanded=True):
            # Boutons suggérer / vider
            _cs, _cc = st.columns([2, 2])
            with _cs:
                if st.button("✨ Suggérer l'équipe", key=f"tb_sug_{_ti}"):
                    _sug = _tb_suggest(_other_used, set(), _require_is)
                    tb_teams[_ti] = _sug
                    for _sl, _cn in _sug.items():
                        st.session_state[f"tb_{_ti}_{_sl}"] = _cn if _cn is not None else "—"
                    st.rerun()
            with _cc:
                if st.button("🗑️ Vider", key=f"tb_clr_{_ti}"):
                    tb_teams[_ti] = _EMPTY_TEAM()
                    for _sl in _SLOT_POS:
                        st.session_state[f"tb_{_ti}_{_sl}"] = "—"
                    st.rerun()

            # Slots en deux colonnes
            _col_l, _col_r = st.columns(2)
            for _si, (_sname, _vpos) in enumerate(_SLOT_POS.items()):
                _col = _col_l if _si < 4 else _col_r
                with _col:
                    # Options disponibles pour ce slot
                    _in_team_used  = {v for k, v in _team.items() if v and k != _sname}
                    _in_team_slugs = {_global_card_slug[c] for c in _in_team_used if c in _global_card_slug}
                    _blocked_slugs = _in_team_slugs  # unicité joueur intra-équipe seulement
                    _cands = (
                        df_tb[
                            df_tb["position_agg"].isin(_vpos) &
                            ~df_tb["card_name"].isin(_other_used | _in_team_used) &
                            ~df_tb["player_slug"].isin(_blocked_slugs)
                        ]
                        .sort_values("proj_score_eff", ascending=False)
                    )
                    _opts    = ["—"] + _cands["card_name"].tolist()
                    _current = _team.get(_sname)
                    # Si la carte courante n'est plus disponible, la garder visible
                    if _current and _current not in _opts:
                        _opts.insert(1, _current)
                    # Initialise l'état widget depuis le dict équipe (évite le conflit index= vs session_state)
                    _wkey = f"tb_{_ti}_{_sname}"
                    if _wkey not in st.session_state:
                        st.session_state[_wkey] = _current if (_current and _current in _opts) else "—"

                    _chosen = st.selectbox(
                        f"**{_sname}**"
                        + (" *(CI/MI/OF)*" if _sname == "Flex" else "")
                        + (" *(CI/MI/OF)*" if _sname == "Libre" else ""),
                        _opts,
                        key=_wkey,
                        format_func=_fmt_opt,
                    )
                    tb_teams[_ti][_sname] = _chosen if _chosen != "—" else None

            # Barre de validation
            _is_c, _max_cl, _sc, _nf = _team_validation(tb_teams[_ti])
            if _nf > 0:
                _is_ok  = not _require_is or _is_c >= 6
                _cl_ok  = _max_cl <= 6
                _is_clr = "#22c55e" if _is_ok  else "#ef4444"
                _cl_clr = "#22c55e" if _cl_ok  else "#ef4444"
                _is_ico = "✅" if _is_ok  else "⚠️"
                _cl_ico = "✅" if _cl_ok  else "⚠️"
                _is_req = " (min 6 requis)" if _require_is else ""
                st.markdown(
                    f'<div style="display:flex;gap:16px;flex-wrap:wrap;'
                    f'margin-top:10px;padding:8px 12px;'
                    f'background:rgba(255,255,255,0.03);border-radius:8px;'
                    f'font-size:0.82rem">'
                    f'<span style="color:{_is_clr}">{_is_ico} IS : {_is_c}/7{_is_req}</span>'
                    f'<span style="color:{_cl_clr}">{_cl_ico} Club max : {_max_cl}/6</span>'
                    f'<span style="color:#4CAF50">⚾ Score eff. (×power) : <b>{_sc:.1f}</b> pts</span>'
                    f'<span style="opacity:0.45">{_nf}/7 slots remplis</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Résumé visuel — images des cartes sélectionnées
            _img_cols = st.columns(7)
            for (_sn, _), _icol in zip(_SLOT_POS.items(), _img_cols):
                _cn = tb_teams[_ti].get(_sn)
                _img_url = _cl.get(_cn or "", {}).get("picture_url")
                with _icol:
                    if _img_url:
                        st.image(_img_url, caption=_sn, use_container_width=True)
                    else:
                        _rarity_c = RARITY_COLOR.get(
                            (_cl.get(_cn or "", {}).get("card_display_rarity") or "").lower(), "#555"
                        )
                        st.markdown(
                            f'<div style="height:90px;border:1px dashed rgba(128,128,128,0.3);'
                            f'border-radius:8px;display:flex;align-items:center;'
                            f'justify-content:center;font-size:0.7rem;opacity:0.4">'
                            f'{_sn}</div>',
                            unsafe_allow_html=True,
                        )

            # Bouton sauvegarder
            st.divider()
            _sv_col1, _sv_col2 = st.columns([2, 3])
            with _sv_col1:
                _sv_disabled = _nf == 0
                if st.button(
                    f"💾 Sauvegarder (GW{_tb_gw8})" if _tb_gw8 else "💾 Sauvegarder",
                    key=f"tb_save_{_ti}",
                    disabled=_sv_disabled,
                    help="Aucun joueur dans l'équipe." if _sv_disabled else "Sauvegarde l'équipe pour comparer avec les résultats réels.",
                ):
                    def _slot_data(card, eff_col="proj_score_eff"):
                        if not card:
                            return None
                        r = _cl.get(card, {})
                        return {
                            "card_name":      card,
                            "player_slug":    r.get("player_slug"),
                            "player_name":    _slug_name_map.get(r.get("player_slug", ""), card),
                            "proj_score_eff": r.get(eff_col),
                            "proj_score":     r.get("proj_score"),
                            "card_power":     r.get("card_power"),
                        }

                    _sug_auto   = _tb_suggest(_other_used, set(), _require_is, score_col="proj_score_eff_auto")
                    _sug_sorare = _tb_suggest(_other_used, set(), _require_is, score_col="proj_score_eff_sorare")

                    _entry = {
                        "lineup_id":              str(uuid.uuid4()),
                        "saved_at":               datetime.now(timezone.utc).isoformat(),
                        "gw_int":                 int(_tb_gw8),
                        "manager":                sel_manager,
                        "mode":                   tb_mode,
                        "rarity":                 tb_rar,
                        "score_src":              tb_score_src,
                        "slots":                  {s: _slot_data(c) for s, c in tb_teams[_ti].items()},
                        "suggested_slots_auto":   {s: _slot_data(c, "proj_score_eff_auto")   for s, c in _sug_auto.items()},
                        "suggested_slots_sorare": {s: _slot_data(c, "proj_score_eff_sorare") for s, c in _sug_sorare.items()},
                    }
                    _persist_lineup(_entry)
                    st.success(f"Équipe sauvegardée pour la GW{_tb_gw8} !")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 9 — COMPÉTITIONS & RÉCOMPENSES
# ═══════════════════════════════════════════════════════════════════════════════

with tab9:
    pass


# ── Construction d'équipes Arena ──────────────────────────────────────────────

with _t8_arena:
    _AL_SLUGS9 = frozenset({
        "oakland-athletics", "baltimore-orioles", "boston-red-sox",
        "chicago-white-sox", "cleveland-guardians", "detroit-tigers",
        "houston-astros", "kansas-city-royals", "los-angeles-angels",
        "minnesota-twins", "new-york-yankees", "seattle-mariners",
        "tampa-bay-rays", "texas-rangers",
    })
    _NL_SLUGS9 = frozenset({
        "arizona-diamondbacks", "atlanta-braves", "chicago-cubs",
        "cincinnati-reds", "colorado-rockies", "los-angeles-dodgers",
        "miami-marlins", "milwaukee-brewers", "new-york-mets",
        "philadelphia-phillies", "pittsburgh-pirates", "san-diego-padres",
        "san-francisco-giants", "st-louis-cardinals",
    })
    _SLOTS_7_AR9 = {
        "SP": ["SP"], "RP": ["RP"], "CI": ["CI"], "MI": ["MI"], "OF": ["OF"],
        "Hitter": ["CI", "MI", "OF"],
        "Libre":  ["SP", "RP", "CI", "MI", "OF"],
    }
    _SLOTS_S2_AR9 = {
        "SP1": ["SP"], "SP2": ["SP"],
        "H1": ["CI", "MI", "OF"], "H2": ["CI", "MI", "OF"], "H3": ["CI", "MI", "OF"],
    }
    _SLOTS_S5_AR9 = {f"H{i}": ["CI", "MI", "OF"] for i in range(1, 6)}
    _ARENA_DEFS9 = {
        "Standard":         {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": None,     "n": 7},
        "Beginner":         {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": None,     "n": 7},
        "Elite":            {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": None,     "n": 7},
        "American (AL)":    {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": "AL",     "n": 7},
        "National (NL)":    {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": "NL",     "n": 7},
        "OG (2022)":        {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": "OG",     "n": 7},
        "Legacy (2023-24)": {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": "Legacy", "n": 7},
        "Sandlot 2SP+3H":   {"slots": _SLOTS_S2_AR9, "max_club": 4, "filter": None,     "n": 5},
        "Sandlot 5H":       {"slots": _SLOTS_S5_AR9, "max_club": 4, "filter": None,     "n": 5},
    }

    _ar9c1, _ar9c2, _ar9c3 = st.columns([3, 2, 2])
    with _ar9c1:
        _ar9_type = st.selectbox("Type d'Arena", list(_ARENA_DEFS9.keys()), key="ar9_type")
    with _ar9c2:
        _ar9_rar = st.radio("Rareté", ["limited", "rare", "super_rare", "unique"],
                            horizontal=True, key="ar9_rar")
    with _ar9c3:
        _ar9_ssrc = st.radio("Score", ["Auto (ML → Hist.)", "Sorare GW+"],
                             horizontal=True, key="ar9_ssrc")

    _ar9d    = _ARENA_DEFS9[_ar9_type]
    _ar9_sl  = _ar9d["slots"]
    _ar9_mc  = _ar9d["max_club"]
    _ar9_flt = _ar9d["filter"]
    _ar9_n   = _ar9d["n"]

    _df_ar9 = (
        df_prices[
            (df_prices["gallery_manager"] == sel_manager) &
            (df_prices["card_display_rarity"].str.lower() == _ar9_rar.lower()) &
            ~df_prices["player_slug"].isin(_injured_slugs)
        ]
        .drop_duplicates("card_name")
        .copy()
    )
    _df_ar9["position_agg"] = _df_ar9["card_display_position"].map(POSITION_AGG)
    _df_ar9["is_eligible"]  = _df_ar9["in_season_eligible"] == True

    if _ar9_flt == "AL":
        _df_ar9 = _df_ar9[_df_ar9["active_club_slug"].isin(_AL_SLUGS9)]
    elif _ar9_flt == "NL":
        _df_ar9 = _df_ar9[_df_ar9["active_club_slug"].isin(_NL_SLUGS9)]
    elif _ar9_flt == "OG":
        _df_ar9 = _df_ar9[_df_ar9["card_name"].str.contains("2022-23", na=False, regex=False)]
    elif _ar9_flt == "Legacy":
        _df_ar9 = _df_ar9[
            _df_ar9["card_name"].str.contains("2023-24", na=False, regex=False) |
            _df_ar9["card_name"].str.contains("2024-25", na=False, regex=False)
        ]

    _ar9_pwr = pd.to_numeric(_df_ar9["card_power"], errors="coerce").fillna(1.0)
    if not df_ml.empty:
        _ml_ar9 = (
            df_ml[df_ml["gallery_manager"] == sel_manager]
            .drop_duplicates("player_slug")
            .set_index("player_slug")["pred_median"]
        )
        _df_ar9["_ml_val"] = _df_ar9["player_slug"].map(_ml_ar9)
    else:
        _df_ar9["_ml_val"] = None

    _ar9_slugs = tuple(_df_ar9["player_slug"].unique())
    _ar9_avg   = load_player_avg_scores(_ar9_slugs, FENETRE_OPTIONS[fenetre]) if _ar9_slugs else pd.DataFrame()
    _ar9_smap  = _ar9_avg.set_index("player_slug")["avg_score"].to_dict() if not _ar9_avg.empty else {}
    _df_ar9["proj_score_hist"]   = _df_ar9["player_slug"].map(_ar9_smap).fillna(0.0)
    _df_ar9["proj_score_auto"]   = (
        pd.to_numeric(_df_ar9["_ml_val"], errors="coerce")
        .combine_first(_df_ar9["proj_score_hist"])
    )
    _df_ar9["proj_score_sorare"] = pd.to_numeric(
        _df_ar9.get("next_gw_projected_score", pd.Series(dtype=float)), errors="coerce"
    )
    _ar9_base = (
        _df_ar9["proj_score_sorare"].fillna(0.0) if _ar9_ssrc == "Sorare GW+"
        else _df_ar9["proj_score_auto"].fillna(0.0)
    )
    _df_ar9["proj_score_eff"] = (_ar9_base * _ar9_pwr).round(1)
    _cl_ar9 = _df_ar9.set_index("card_name").to_dict("index")

    def _fmt_opt_ar9(x: str) -> str:
        if x == "—":
            return "—"
        r = _cl_ar9.get(x, {})
        pos = POSITION_EXACT.get(r.get("card_display_position", ""), "?")
        try:
            sc = float(r.get("proj_score_eff") or 0.0)
        except (TypeError, ValueError):
            sc = 0.0
        try:
            pwr = float(r.get("card_power") or 1.0)
        except (TypeError, ValueError):
            pwr = 1.0
        return f"{x}  [{pos} · {sc:.0f} pts eff. · ×{pwr:.3f}]"

    _ar9_sk  = f"arena_{_ar9_type}_{_ar9_rar}"
    _EMPTY_AR9 = lambda: {s: None for s in _ar9_sl}
    if _ar9_sk not in st.session_state or set(st.session_state[_ar9_sk].keys()) != set(_ar9_sl.keys()):
        st.session_state[_ar9_sk] = _EMPTY_AR9()
    _ar9_team = st.session_state[_ar9_sk]

    if _df_ar9.empty:
        st.warning(f"Aucune carte {_ar9_rar} disponible pour cette arena.")
    else:
        _ar9_global_slug = (
            df_prices[df_prices["gallery_manager"] == sel_manager]
            .drop_duplicates("card_name")
            .set_index("card_name")["player_slug"]
            .to_dict()
        )

        _ar9_btn1, _ar9_btn2 = st.columns([2, 2])
        with _ar9_btn1:
            if st.button("✨ Suggérer l'équipe", key="ar9_sug"):
                _sug_ar9 = _tb_suggest(set(), set(), False,
                                       score_col="proj_score_eff",
                                       slot_pos=_ar9_sl,
                                       df_pool=_df_ar9)
                st.session_state[_ar9_sk] = _sug_ar9
                for sl, cn in _sug_ar9.items():
                    st.session_state[f"ar9s_{_ar9_type}_{_ar9_rar}_{sl}"] = cn if cn else "—"
                st.rerun()
        with _ar9_btn2:
            if st.button("🗑️ Vider", key="ar9_clr"):
                st.session_state[_ar9_sk] = _EMPTY_AR9()
                for sl in _ar9_sl:
                    st.session_state[f"ar9s_{_ar9_type}_{_ar9_rar}_{sl}"] = "—"
                st.rerun()

        _half_ar9 = (len(_ar9_sl) + 1) // 2
        _col_la9, _col_ra9 = st.columns(2)
        for _si9, (_sn9, _vp9) in enumerate(_ar9_sl.items()):
            _col9 = _col_la9 if _si9 < _half_ar9 else _col_ra9
            with _col9:
                _in_used9  = {v for k, v in _ar9_team.items() if v and k != _sn9}
                _in_slugs9 = {_ar9_global_slug[c] for c in _in_used9 if c in _ar9_global_slug}
                _cands9 = (
                    _df_ar9[
                        _df_ar9["position_agg"].isin(_vp9) &
                        ~_df_ar9["card_name"].isin(_in_used9) &
                        ~_df_ar9["player_slug"].isin(_in_slugs9)
                    ]
                    .sort_values("proj_score_eff", ascending=False)
                )
                _opts9 = ["—"] + _cands9["card_name"].tolist()
                _cur9  = _ar9_team.get(_sn9)
                if _cur9 and _cur9 not in _opts9:
                    _opts9.insert(1, _cur9)
                _wkey9 = f"ar9s_{_ar9_type}_{_ar9_rar}_{_sn9}"
                if _wkey9 not in st.session_state:
                    st.session_state[_wkey9] = _cur9 if (_cur9 and _cur9 in _opts9) else "—"
                _chosen9 = st.selectbox(
                    f"**{_sn9}**",
                    _opts9,
                    key=_wkey9,
                    format_func=_fmt_opt_ar9,
                )
                _ar9_team[_sn9] = _chosen9 if _chosen9 != "—" else None

        _cards9 = [v for v in _ar9_team.values() if v]
        _nf9    = len(_cards9)
        if _nf9 > 0:
            from collections import Counter as _Ctr9
            _clubs9 = [_cl_ar9.get(c, {}).get("active_club_slug", "") for c in _cards9]
            _mc9    = max(_Ctr9(_clubs9).values()) if _clubs9 else 0
            _sc9    = sum(float(_cl_ar9.get(c, {}).get("proj_score_eff") or 0.0) for c in _cards9)
            _mc_ok9 = _mc9 <= _ar9_mc
            _mc_clr = "#22c55e" if _mc_ok9 else "#ef4444"
            _mc_ico = "✅" if _mc_ok9 else "⚠️"
            st.markdown(
                f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;padding:8px 12px;'
                f'background:rgba(255,255,255,0.03);border-radius:8px;font-size:0.82rem">'
                f'<span style="color:{_mc_clr}">{_mc_ico} Club max : {_mc9}/{_ar9_mc}</span>'
                f'<span style="color:#4CAF50">⚾ Score eff. : <b>{_sc9:.1f}</b> pts</span>'
                f'<span style="opacity:0.45">{_nf9}/{_ar9_n} slots remplis</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        _img9_cols = st.columns(_ar9_n)
        for (_sna9, _), _icl9 in zip(_ar9_sl.items(), _img9_cols):
            _cn9  = _ar9_team.get(_sna9)
            _img9 = _cl_ar9.get(_cn9 or "", {}).get("picture_url")
            with _icl9:
                if _img9:
                    st.image(_img9, caption=_sna9, use_container_width=True)
                else:
                    st.markdown(
                        f'<div style="height:90px;border:1px dashed rgba(128,128,128,0.3);'
                        f'border-radius:8px;display:flex;align-items:center;'
                        f'justify-content:center;font-size:0.7rem;opacity:0.4">{_sna9}</div>',
                        unsafe_allow_html=True,
                    )

        st.divider()
        _sv9_dis = _nf9 == 0
        try:
            _, _ar9_gw = load_upcoming_pitchers()
        except Exception:
            _ar9_gw = 0
        if st.button(
            f"💾 Sauvegarder (GW{_ar9_gw})" if _ar9_gw else "💾 Sauvegarder",
            key="ar9_save",
            disabled=_sv9_dis,
            help="Aucun joueur dans l'équipe." if _sv9_dis else None,
        ):
            def _sd9(card):
                if not card:
                    return None
                r = _cl_ar9.get(card, {})
                return {
                    "card_name":      card,
                    "player_slug":    r.get("player_slug"),
                    "player_name":    _slug_name_map.get(r.get("player_slug", ""), card),
                    "proj_score_eff": r.get("proj_score_eff"),
                    "proj_score":     None,
                    "card_power":     r.get("card_power"),
                }
            _persist_lineup({
                "lineup_id":              str(uuid.uuid4()),
                "saved_at":               datetime.now(timezone.utc).isoformat(),
                "gw_int":                 int(_ar9_gw),
                "manager":                sel_manager,
                "mode":                   f"Arena {_ar9_type}",
                "rarity":                 _ar9_rar,
                "score_src":              _ar9_ssrc,
                "slots":                  {s: _sd9(c) for s, c in _ar9_team.items()},
                "suggested_slots_auto":   None,
                "suggested_slots_sorare": None,
            })
            st.success(f"Équipe Arena {_ar9_type} sauvegardée pour la GW{_ar9_gw} !")


# ── Leaderboards & récompenses ────────────────────────────────────────────────

with tab9:
    import math as _math9
    import plotly.graph_objects as go

    if df_lb.empty:
        st.info("Aucune donnée de compétition. Lance `python fetch_leaderboard_history.py` pour collecter.")
        st.stop()

    _arena9 = df_lb[
        (df_lb["source"] == "arena") &
        ~df_lb["leaderboard_slug"].str.lower().str.endswith("_pve", na=False)
    ].copy()
    _hs9    = df_lb[df_lb["source"] == "hot_streak"].copy()

    # ── Filtres ───────────────────────────────────────────────────────────────
    _col9a, _col9b, _col9c_filt = st.columns([2, 2, 3])
    with _col9a:
        _rar9 = st.radio(
            "Rareté", ["limited", "rare", "super_rare"],
            horizontal=True, key="lb9_rar",
        )
    with _col9b:
        _arena_filter9 = st.radio(
            "Type", ["Toutes", "Arena", "Classiques"],
            horizontal=True, key="lb9_arena_filter",
        )

    # Mapping nom affiché → nom réel (pour garder le filtre sur leaderboard_name)
    _rar_df9 = _arena9[_arena9["rarity_type"] == _rar9].copy()
    if _arena_filter9 == "Arena":
        _rar_df9 = _rar_df9[_rar_df9["is_arena"] == True]
    elif _arena_filter9 == "Classiques":
        _rar_df9 = _rar_df9[_rar_df9["is_arena"] == False]

    # Table de correspondance : nom_affiché → nom_réel
    _name_map9 = {
        (f"ARENA — {n}" if bool(
            _rar_df9[_rar_df9["leaderboard_name"] == n]["is_arena"].any()
        ) else n): n
        for n in sorted(_rar_df9["leaderboard_name"].dropna().unique())
    }
    _all_comps9_disp = list(_name_map9.keys())
    _default_real9   = ["Champion", "Challenger", "Standard", "American"]
    _default_disp9   = [d for d, r in _name_map9.items() if r in _default_real9]

    with _col9c_filt:
        _sel_comps9_disp = st.multiselect(
            "Compétitions", _all_comps9_disp,
            default=_default_disp9,
            key="lb9_comps",
        )

    # Noms réels sélectionnés
    _sel_comps9 = [_name_map9[d] for d in _sel_comps9_disp if d in _name_map9]

    st.divider()

    # Sous-ensemble filtré
    _df9 = _arena9[
        (_arena9["rarity_type"] == _rar9) &
        (_arena9["leaderboard_name"].isin(_sel_comps9)) &
        _arena9["score_threshold"].notna() &
        _arena9["gw_int"].notna()
    ].copy()
    _df9["gw_int"] = _df9["gw_int"].astype(int)
    # Nom affiché : préfixe "ARENA — " pour les compétitions arena
    _rev_map9 = {v: k for k, v in _name_map9.items()}
    _df9["leaderboard_display"] = _df9["leaderboard_name"].map(_rev_map9).fillna(_df9["leaderboard_name"])

    # ── Section 1 : seuils d'entrée et de victoire par GW ────────────────────
    st.subheader("Évolution des seuils par compétition")
    st.caption("Seuil d'entrée = score minimum pour toute récompense · Seuil top = score le plus haut")

    _entry9 = (
        _df9.groupby(["gw_int", "leaderboard_display"], as_index=False)
        .agg(
            entry=("score_threshold", "min"),
            top=("score_threshold", "max"),
            median=("score_threshold", "median"),
            nb_div=("leaderboard_slug", "nunique"),
        )
        .sort_values("gw_int")
    )

    _COMP_COLORS = {
        "Champion":   "#f59e0b",
        "Challenger": "#ef4444",
        "Standard":   "#3b82f6",
        "American":   "#10b981",
        "National":   "#8b5cf6",
        "Beginner":   "#94a3b8",
        "Elite":      "#ec4899",
        "Hitters":    "#06b6d4",
        "Legacy":     "#a16207",
        "OG":         "#7c3aed",
        "Sandlot":    "#059669",
    }

    fig_entry = go.Figure()
    for comp_disp in _sel_comps9_disp:
        comp_real = _name_map9.get(comp_disp, comp_disp)
        sub = _entry9[_entry9["leaderboard_display"] == comp_disp]
        if sub.empty:
            continue
        color = _COMP_COLORS.get(comp_real, "#888")
        # Bande min-max (si plusieurs divisions)
        if (sub["top"] - sub["entry"]).max() > 1:
            fig_entry.add_trace(go.Scatter(
                x=list(sub["gw_int"]) + list(sub["gw_int"])[::-1],
                y=list(sub["top"]) + list(sub["entry"])[::-1],
                fill="toself",
                fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.10)",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ))
        # Ligne seuil d'entrée
        fig_entry.add_trace(go.Scatter(
            x=sub["gw_int"], y=sub["entry"],
            mode="lines+markers",
            name=f"{comp_disp} — entrée",
            line=dict(color=color, width=2, dash="dot"),
            marker=dict(size=6),
            customdata=sub[["nb_div"]].values,
            hovertemplate="%{y:.1f} pts · %{customdata[0]} division(s)<extra>%{fullData.name}</extra>",
        ))
        # Ligne top score
        fig_entry.add_trace(go.Scatter(
            x=sub["gw_int"], y=sub["top"],
            mode="lines+markers",
            name=f"{comp_disp} — top",
            line=dict(color=color, width=2),
            marker=dict(size=6),
            customdata=sub[["nb_div"]].values,
            hovertemplate="%{y:.1f} pts · %{customdata[0]} division(s)<extra>%{fullData.name}</extra>",
        ))

    # Ligne "entrée $" pour Champion : seuil minimum des paliers monétaires
    _champ_real9 = "Champion"
    _champ_disp9 = _rev_map9.get(_champ_real9, _champ_real9)
    if _champ_disp9 in _sel_comps9_disp:
        _champ_mon9 = (
            _df9[
                (_df9["leaderboard_name"] == _champ_real9) &
                (_df9["reward_type"] == "monetary") &
                _df9["score_threshold"].notna()
            ]
            .groupby("gw_int", as_index=False)
            .agg(entree_dollar=("score_threshold", "min"))
            .sort_values("gw_int")
        )
        if not _champ_mon9.empty:
            fig_entry.add_trace(go.Scatter(
                x=_champ_mon9["gw_int"], y=_champ_mon9["entree_dollar"],
                mode="lines+markers",
                name=f"{_champ_disp9} — entrée $",
                line=dict(color="#22c55e", width=2, dash="dashdot"),
                marker=dict(size=7, symbol="diamond"),
                hovertemplate="%{y:.1f} pts<extra>%{fullData.name}</extra>",
            ))

    _gw_min9 = int(_df9["gw_int"].min()) if not _df9.empty else 119
    _gw_max9 = int(_df9["gw_int"].max()) if not _df9.empty else 133
    fig_entry.update_layout(
        xaxis=dict(title="GW", tickmode="linear", dtick=1,
                   range=[_gw_min9 - 0.5, _gw_max9 + 0.5]),
        yaxis=dict(title="Score"),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        margin=dict(r=200),
    )
    st.plotly_chart(fig_entry, use_container_width=True)

    # ── Section 2 : paliers complets pour une compétition choisie ────────────
    st.divider()
    st.subheader("Structure des paliers — détail")

    _gws_sorted9 = sorted(_arena9["gw_int"].dropna().unique())

    _col9c, _col9d, _col9e = st.columns([2, 2, 2])
    with _col9c:
        _comp_detail9_disp = st.selectbox(
            "Compétition", _sel_comps9_disp if _sel_comps9_disp else _all_comps9_disp,
            key="lb9_comp_detail",
        )
    with _col9d:
        _detail_mode9 = st.radio(
            "Période", ["GW spécifique", "Moyenne 5 dernières GW"],
            horizontal=True, key="lb9_detail_mode",
        )
    _comp_detail9_real = _name_map9.get(_comp_detail9_disp, _comp_detail9_disp) if _comp_detail9_disp else None

    _gw_detail9 = None
    if _detail_mode9 == "GW spécifique":
        with _col9e:
            _gws_avail9 = sorted(
                _df9[_df9["leaderboard_name"] == _comp_detail9_real]["gw_int"].unique(), reverse=True
            ) if _comp_detail9_real else []
            _gw_detail9 = st.selectbox(
                "GW", _gws_avail9, index=min(1, len(_gws_avail9) - 1), key="lb9_gw_detail"
            ) if _gws_avail9 else None

    if _comp_detail9_real and (_gw_detail9 is not None or _detail_mode9 == "Moyenne 5 dernières GW"):
        _has_from_rank9 = "from_rank" in _df9.columns

        if _detail_mode9 == "GW spécifique":
            _detail9 = _df9[
                (_df9["leaderboard_name"] == _comp_detail9_real) &
                (_df9["gw_int"] == _gw_detail9) &
                _df9["score_threshold"].notna()
            ]
            _title_base9 = f"{_comp_detail9_disp} {_rar9} — GW{_gw_detail9}"
        else:
            # 5 GWs les plus récentes en excluant la dernière (encore en cours)
            _gws_comp9 = sorted(_df9[_df9["leaderboard_name"] == _comp_detail9_real]["gw_int"].unique())
            _gws_comp_excl9 = _gws_comp9[:-1] if len(_gws_comp9) > 1 else _gws_comp9
            _last5_detail9  = _gws_comp_excl9[-5:]
            _detail9 = _df9[
                (_df9["leaderboard_name"] == _comp_detail9_real) &
                _df9["gw_int"].isin(_last5_detail9) &
                _df9["score_threshold"].notna()
            ]
            _gw_range9   = f"GW{int(_last5_detail9[0])}–GW{int(_last5_detail9[-1])}"
            _title_base9 = f"{_comp_detail9_disp} {_rar9} — moy. {_gw_range9}"

        def _build_tiers(df_sub: pd.DataFrame) -> pd.DataFrame:
            if df_sub.empty:
                return pd.DataFrame()
            agg = dict(
                score_min=("score_threshold", "min"),
                score_median=("score_threshold", "median"),
                score_max=("score_threshold", "max"),
                reward_quantity=("reward_quantity", "median"),
                reward_usd_cents=("reward_usd_cents", "median"),
            )
            if _has_from_rank9:
                agg["from_rank"] = ("from_rank", "first")
            t = df_sub.groupby("tier_rank", as_index=False).agg(**agg).sort_values("tier_rank")
            if "from_rank" not in t.columns:
                t["from_rank"] = None
            return t

        _tiers_mon9 = _build_tiers(_detail9[_detail9["reward_type"] == "monetary"])
        _tiers_ess9 = _build_tiers(_detail9[_detail9["reward_type"] == "card_shard"])

        def _fig_paliers(tiers: pd.DataFrame, title: str, bar_color: str, reward_type: str = "card_shard") -> go.Figure:
            fig = go.Figure()
            for _, row in tiers.iterrows():
                tier  = int(row["tier_rank"])
                score = row["score_median"]
                x_label = (
                    f"Top {int(row['from_rank'])}"
                    if pd.notna(row.get("from_rank"))
                    else f"Palier {tier}"
                )
                if reward_type == "monetary" and pd.notna(row.get("reward_usd_cents")):
                    reward_text = f"${row['reward_usd_cents'] / 100:.0f}"
                elif pd.notna(row.get("reward_quantity")):
                    reward_text = f"{int(row['reward_quantity'])}"
                else:
                    reward_text = ""
                err_y = dict(
                    type="data", symmetric=False,
                    array=[row["score_max"] - score],
                    arrayminus=[score - row["score_min"]],
                    visible=True, color=bar_color,
                ) if (row["score_max"] - row["score_min"]) > 0.5 else None
                fig.add_trace(go.Bar(
                    x=[x_label], y=[score],
                    error_y=err_y,
                    marker_color=bar_color,
                    text=[reward_text],
                    textposition="inside",
                    insidetextanchor="middle",
                    textangle=0,
                    textfont=dict(color="white", size=13),
                    showlegend=False,
                    hovertemplate=f"Score seuil : %{{y:.1f}}<br>Récompense : {reward_text}<extra></extra>",
                ))
            y_max = float(tiers["score_max"].max()) if not tiers.empty else 300
            fig.update_layout(
                title=title,
                yaxis=dict(title="Score requis", range=[0, y_max * 1.18]),
                xaxis=dict(title="Classement"),
                height=360,
                bargap=0.35,
                margin=dict(t=50, b=40),
            )
            return fig

        _fcols9 = st.columns(2)
        with _fcols9[0]:
            if not _tiers_mon9.empty:
                st.plotly_chart(
                    _fig_paliers(_tiers_mon9, f"Récompenses en Cash — {_title_base9}", "#22c55e", reward_type="monetary"),
                    use_container_width=True,
                )
            else:
                st.caption("Pas de récompenses monétaires pour cette compétition.")
        with _fcols9[1]:
            if not _tiers_ess9.empty:
                st.plotly_chart(
                    _fig_paliers(_tiers_ess9, f"Essences — {_title_base9}", "#a78bfa"),
                    use_container_width=True,
                )
            else:
                st.caption("Pas de récompenses en essences pour cette compétition.")

    # ── Section 3 : tableau récapitulatif ────────────────────────────────────
    st.divider()
    st.subheader("Récapitulatif des seuils")

    _penult_gw9 = int(_gws_sorted9[-2]) if len(_gws_sorted9) >= 2 else (int(_gws_sorted9[-1]) if _gws_sorted9 else 0)
    _recap9 = (
        _arena9[
            (_arena9["gw_int"] == _penult_gw9) &
            (_arena9["rarity_type"] == _rar9) &
            _arena9["score_threshold"].notna()
        ]
        .groupby("leaderboard_name", as_index=False)
        .agg(
            seuil_entree=("score_threshold", "min"),
            seuil_top=("score_threshold", "max"),
            nb_divisions=("leaderboard_slug", "nunique"),
        )
        .sort_values("seuil_entree")
    )
    _recap9.columns = ["Compétition", "Seuil entrée", "Seuil top", "Nb divisions"]
    st.caption(f"GW{_penult_gw9} · rareté {_rar9}")
    st.dataframe(
        _recap9.style.format({"Seuil entrée": "{:.1f}", "Seuil top": "{:.1f}"}),
        use_container_width=True, hide_index=True,
    )

    # ── Section 4 : Hot Streak référence ─────────────────────────────────────
    st.divider()
    st.subheader("Hot Streak — seuils de référence")
    st.caption("Seuils fixes (indépendants de la GW). Bonus essences = par équipe supplémentaire atteignant le seuil.")
    _hs_disp9 = _hs9[_hs9["rarity_type"] == _rar9][
        ["score_threshold", "reward_quantity", "bonus_shards"]
    ].rename(columns={
        "score_threshold": "Score cible",
        "reward_quantity": "Essences (1ère équipe)",
        "bonus_shards":    "Bonus / équipe supp.",
    })
    st.dataframe(
        _hs_disp9.style.format({"Score cible": "{:.0f}", "Essences (1ère équipe)": "{:.0f}", "Bonus / équipe supp.": "{:.0f}"}),
        use_container_width=True, hide_index=True,
    )

    # ── Section 5 : Comparaison de rentabilité ────────────────────────────────
    st.divider()
    st.subheader("Comparaison de rentabilité")

    _ESS_RATE9        = 3 / 1000
    _ARENA_ENTRY9     = {"Beginner": 100, "Elite": 800}
    _ARENA_ENTRY_DEF9 = 300
    _LINEUP_SIZE9     = {"Hitters": 5, "Sandlot": 5}   # autres : 7 joueurs par défaut
    _LINEUP_COMP9     = {"Hitters": "5 hitters", "Sandlot": "3 hitters + 2 SP"}

    # ── Paliers HS pour la rareté active ──────────────────────────────────────
    _hs_all9 = (
        _hs9[_hs9["rarity_type"] == _rar9]
        .sort_values("score_threshold")
        .reset_index(drop=True)
    )
    _hs_palier_labels9 = [
        f"Palier {i+1} ({int(r.score_threshold)} pts)"
        for i, r in enumerate(_hs_all9.itertuples(index=False))
    ]

    # ── Contrôles ─────────────────────────────────────────────────────────────
    _cmp_c1, _cmp_c2, _cmp_c3 = st.columns([4, 2, 2])
    with _cmp_c1:
        _score_cmp9 = st.slider(
            "Score cible (lineup 7 joueurs)", min_value=100, max_value=400, value=200, step=5, key="lb9_score_cmp"
        )
    with _cmp_c2:
        _hs_palier_sel9 = st.selectbox(
            "Palier HS actuel",
            options=list(range(len(_hs_palier_labels9))),
            format_func=lambda i: _hs_palier_labels9[i],
            key="lb9_hs_palier",
        )
    with _cmp_c3:
        _n_teams_hs9 = st.number_input(
            "Équipes Hot Streak", min_value=1, max_value=4, value=1, step=1, key="lb9_n_teams_hs"
        )

    _gw_mode_cmp9 = st.radio(
        "Référence GW", ["Dernière GW terminée", "Moyenne 5 dernières GW terminées"],
        horizontal=True, key="lb9_gw_mode_cmp",
    )
    _gws_excl_last9 = _gws_sorted9[:-1]  # exclut la GW en cours
    if _gw_mode_cmp9 == "Dernière GW terminée":
        _gws_cmp9      = [int(_gws_excl_last9[-1])] if len(_gws_excl_last9) >= 1 else []
        _gw_ref_lbl9   = f"GW{_gws_cmp9[0]}" if _gws_cmp9 else "—"
    else:
        _last5_cmp9    = _gws_excl_last9[-5:] if len(_gws_excl_last9) >= 5 else _gws_excl_last9
        _gws_cmp9      = [int(g) for g in _last5_cmp9]
        _gw_ref_lbl9   = f"moy. GW{_gws_cmp9[0]}–GW{_gws_cmp9[-1]}" if _gws_cmp9 else "—"

    st.caption(f"Hypothèse : 1 000 essences = 3 $ · Référence : {_gw_ref_lbl9}")

    def _best_tier_reached(df_ref, score):
        hits = df_ref[df_ref["score_threshold"] <= score]
        return hits.sort_values("score_threshold", ascending=False).iloc[0] if not hits.empty else None

    # ── Données de référence : toutes compétitions × types de récompenses ─────
    _ref_base9 = _arena9[
        (_arena9["rarity_type"] == _rar9) &
        _arena9["gw_int"].isin(_gws_cmp9) &
        _arena9["score_threshold"].notna()
    ]
    _is_arena_map9 = _ref_base9.groupby("leaderboard_name")["is_arena"].first().to_dict()

    _comp_ref9 = (
        _ref_base9
        .groupby(["leaderboard_name", "reward_type", "tier_rank"], as_index=False)
        .agg(
            score_threshold=("score_threshold",  "median"),
            reward_quantity=("reward_quantity",   "median"),
            reward_usd_cents=("reward_usd_cents", "median"),
        )
    )

    # ── Construction du tableau ────────────────────────────────────────────────
    _cmp_rows9 = []
    _comp_order9 = sorted(_comp_ref9["leaderboard_name"].unique())
    for _cname9 in _comp_order9:
        _is_arena_c9  = bool(_is_arena_map9.get(_cname9, False))
        _entry9_cost  = _ARENA_ENTRY9.get(_cname9, _ARENA_ENTRY_DEF9) if _is_arena_c9 else 0
        _prefix9      = "ARENA — " if _is_arena_c9 else ""
        _n_players9   = _LINEUP_SIZE9.get(_cname9, 7)
        _fmt_lbl9     = _LINEUP_COMP9.get(_cname9, f"{_n_players9} joueurs")

        _adj9 = 7 / _n_players9  # facteur de normalisation vers équivalent 7 joueurs

        for _rtype9 in ["monetary", "card_shard"]:
            _sub9 = _comp_ref9[
                (_comp_ref9["leaderboard_name"] == _cname9) &
                (_comp_ref9["reward_type"] == _rtype9)
            ].copy()
            if _sub9.empty:
                continue

            # Normalise les seuils vers l'équivalent 7 joueurs avant comparaison
            _sub9["score_threshold"] = _sub9["score_threshold"] * _adj9
            _best9 = _best_tier_reached(_sub9, _score_cmp9)

            if _rtype9 == "monetary":
                _lbl9 = f"{_prefix9}{_cname9} (cash)"
                if _best9 is not None:
                    _val9   = float(_best9["reward_usd_cents"]) / 100
                    _rew9   = f"${_val9:.2f}"
                    _thr_adj9  = _best9["score_threshold"]
                    _thr_real9 = _thr_adj9 / _adj9
                    _seuil9 = (
                        f"{_thr_adj9:.0f} pts ({_thr_real9:.0f} réel)"
                        if _n_players9 != 7
                        else f"{_thr_adj9:.0f} pts"
                    )
                else:
                    _val9   = 0.0
                    _rew9   = "$0"
                    _seuil9 = "non atteint"
            else:
                _lbl9 = f"{_prefix9}{_cname9} (ess.)"
                if _best9 is not None:
                    _ess9      = float(_best9["reward_quantity"])
                    _net9      = _ess9 - _entry9_cost
                    _val9      = _net9 * _ESS_RATE9
                    _thr_adj9  = _best9["score_threshold"]
                    _thr_real9 = _thr_adj9 / _adj9
                    _seuil9 = (
                        f"{_thr_adj9:.0f} pts ({_thr_real9:.0f} réel)"
                        if _n_players9 != 7
                        else f"{_thr_adj9:.0f} pts"
                    )
                    _rew9   = (
                        f"{int(_ess9)} − {_entry9_cost} = {int(_net9)} ess. → ${_val9:.2f}"
                        if _entry9_cost > 0
                        else f"{int(_ess9)} ess. → ${_val9:.2f}"
                    )
                else:
                    _net9   = -_entry9_cost
                    _val9   = _net9 * _ESS_RATE9
                    _seuil9 = "non atteint"
                    _rew9   = (
                        f"0 − {_entry9_cost} = {int(_net9)} ess. → ${_val9:.2f}"
                        if _entry9_cost > 0
                        else "0 ess. → $0"
                    )

            _cmp_rows9.append({
                "Compétition":      _lbl9,
                "Format":           _fmt_lbl9,
                "Score nécessaire": _seuil9,
                "Récompense":       _rew9,
                "Valeur ($)":       _val9,
            })

    # ── Hot Streak ────────────────────────────────────────────────────────────
    _hsr_sel9    = _hs_all9.iloc[_hs_palier_sel9]
    _hs_thr9     = float(_hsr_sel9["score_threshold"])
    _hs_rew9     = float(_hsr_sel9["reward_quantity"])
    _hs_bon9     = float(_hsr_sel9.get("bonus_shards", 0) or 0)
    _hs_label9   = _hs_palier_labels9[_hs_palier_sel9]

    if _score_cmp9 >= _hs_thr9:
        _hs_total9   = _hs_rew9 + (_n_teams_hs9 - 1) * _hs_bon9
        _hs_val9     = _hs_total9 * _ESS_RATE9
        _hs_rew_str9 = (
            f"{int(_hs_rew9)} ess. → ${_hs_val9:.2f}" if _n_teams_hs9 == 1
            else f"{int(_hs_rew9)} + {_n_teams_hs9-1}×{int(_hs_bon9)} = {int(_hs_total9)} ess. → ${_hs_val9:.2f}"
        )
        _hs_seuil9   = f"{int(_hs_thr9)} pts ✓"
        _hs_next9    = (_hs_palier_labels9[_hs_palier_sel9 + 1]
                        if _hs_palier_sel9 + 1 < len(_hs_palier_labels9)
                        else "Streak complète !")
    else:
        _hs_val9     = 0.0
        _hs_rew_str9 = "$0 + reset palier 1"
        _hs_seuil9   = f"{int(_hs_thr9)} pts ✗"
        _hs_next9    = "—"

    _cmp_rows9.append({
        "Compétition":      f"Hot Streak {_hs_label9}",
        "Format":           "7 joueurs",
        "Score nécessaire": _hs_seuil9,
        "Récompense":       _hs_rew_str9,
        "Valeur ($)":       _hs_val9,
    })

    # ── Affichage ─────────────────────────────────────────────────────────────
    _cmp_df9   = pd.DataFrame(_cmp_rows9).sort_values("Valeur ($)", ascending=False).reset_index(drop=True)
    _best_val9 = float(_cmp_df9["Valeur ($)"].max())

    def _hl_best9(row):
        bg = "background-color: rgba(34,197,94,0.20)" if row["Valeur ($)"] == _best_val9 and _best_val9 > 0 else ""
        return [bg] * len(row)

    _display_cols9 = ["Compétition", "Format", "Score nécessaire", "Récompense", "Valeur ($)"]
    st.dataframe(
        _cmp_df9[_display_cols9].style.apply(_hl_best9, axis=1).format({"Valeur ($)": "${:.2f}"}),
        use_container_width=True, hide_index=True,
    )

    if _best_val9 > 0:
        _winner9 = _cmp_df9.iloc[0]
        st.success(f"**Meilleur choix à {_score_cmp9} pts :** {_winner9['Compétition']} — {_winner9['Récompense']}")

    if _score_cmp9 >= _hs_thr9 and _hs_next9 not in ("—", "Streak complète !"):
        st.info(f"Hot Streak réussie → prochain palier : **{_hs_next9}**")

    st.caption(
        "Arena : coût d'entrée déduit (Beginner 100 ess., Elite 800 ess., autres 300 ess.). "
        "Hitters / Sandlot : seuils multipliés par 7/5 pour comparaison sur base 7 joueurs (valeur réelle entre parenthèses). "
        "Champion / Challenger (cash) et (ess.) sont mutuellement exclusifs selon le classement final. "
        "Hot Streak : tout ou rien — échec = $0 et retour au palier 1. "
        "Multi-équipes HS : toutes les équipes supposées au même score."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 10 — MES LINEUPS SAUVEGARDÉS
# ═══════════════════════════════════════════════════════════════════════════════

with tab10:
    _saved = load_saved_lineups()
    _saved_mgr = [l for l in _saved if l.get("manager") == sel_manager]

    if not _saved_mgr:
        st.info("Aucun lineup sauvegardé. Crée une équipe dans l'onglet 🏗️ Équipe puis clique sur 💾 Sauvegarder.")
    else:
        _gs_all = load_game_scores_all()

        # ── Filtres ───────────────────────────────────────────────────────────
        _gws_saved   = sorted({l["gw_int"] for l in _saved_mgr}, reverse=True)
        _modes_saved = sorted({l["mode"]   for l in _saved_mgr})

        _fc1, _fc2, _fc3 = st.columns(3)
        with _fc1:
            _sel_gw10 = st.selectbox(
                "Game Week", _gws_saved,
                format_func=lambda g: f"GW{g}",
                key="l10_gw",
            )
        with _fc2:
            _sel_mode10 = st.selectbox(
                "Mode", ["Tous"] + _modes_saved, key="l10_mode"
            )
        with _fc3:
            _sel_rar10 = st.selectbox(
                "Rareté", ["Toutes", "limited", "rare", "super_rare", "unique"],
                key="l10_rar",
            )

        _lineups10 = [
            l for l in _saved_mgr
            if l["gw_int"] == _sel_gw10
            and (_sel_mode10 == "Tous"    or l["mode"]   == _sel_mode10)
            and (_sel_rar10  == "Toutes"  or l["rarity"] == _sel_rar10)
        ]

        if not _lineups10:
            st.info("Aucun lineup correspond aux filtres.")
        else:
            # Scores réels disponibles pour cette GW ?
            _gs_gw10 = (
                _gs_all[_gs_all["gw_int"] == _sel_gw10]
                .groupby("player_slug", as_index=False)["score"]
                .sum()
                .set_index("player_slug")["score"]
                .to_dict()
                if not _gs_all.empty else {}
            )
            _has_real = bool(_gs_gw10)

            def _color_diff10(val):
                if val is None or pd.isna(val):
                    return ""
                return "color: #22c55e" if val >= 0 else "color: #ef4444"

            for _l10 in _lineups10:
                _lid        = _l10["lineup_id"]
                _ldate      = _l10["saved_at"][:16].replace("T", " ")
                _src_label  = _l10.get("score_src", "—")
                # Compat ancien format (suggested_slots) + nouveau format
                _sug_auto10   = (_l10.get("suggested_slots_auto")
                                 or _l10.get("suggested_slots") or {})
                _sug_sorare10 = _l10.get("suggested_slots_sorare") or {}
                _title      = (
                    f"{_l10['mode']} · {_l10['rarity']} · GW{_l10['gw_int']} "
                    f"· {_src_label} — sauvegardé le {_ldate}"
                )

                with st.expander(_title, expanded=True):
                    # ── Tableau principal ─────────────────────────────────────
                    _rows10 = []
                    for _slot, _sdata in _l10["slots"].items():
                        _sug10  = _sug_auto10.get(_slot)
                        _modif  = bool(
                            _sdata and _sug10 and
                            _sdata.get("player_slug") != _sug10.get("player_slug")
                        )
                        if not _sdata:
                            _rows10.append({
                                "Slot": _slot, "Joueur": "—",
                                "Prédit": None, "Réel": None, "Diff": None, "✏️": "",
                            })
                            continue
                        _pslug = _sdata.get("player_slug")
                        _pred  = _sdata.get("proj_score_eff")
                        _real  = _gs_gw10.get(_pslug) if _pslug else None
                        _diff  = round(_real - _pred, 1) if (_real is not None and _pred is not None) else None
                        _rows10.append({
                            "Slot":    _slot,
                            "Joueur":  _sdata.get("player_name", "—"),
                            "Prédit":  round(float(_pred), 1) if _pred is not None else None,
                            "Réel":    round(float(_real), 1) if _real is not None else None,
                            "Diff":    _diff,
                            "✏️":      "✏️" if _modif else "",
                        })

                    _df10 = pd.DataFrame(_rows10)

                    # Métriques résumé
                    _tot_pred = _df10["Prédit"].sum() if _df10["Prédit"].notna().any() else None
                    _tot_real = _df10["Réel"].sum()   if _df10["Réel"].notna().any()   else None
                    _tot_diff = round(_tot_real - _tot_pred, 1) if (_tot_pred is not None and _tot_real is not None) else None

                    _mc = st.columns(3)
                    _mc[0].metric("Score prédit", f"{_tot_pred:.1f} pts" if _tot_pred is not None else "—")
                    _mc[1].metric(
                        "Score réel",
                        f"{_tot_real:.1f} pts" if _tot_real is not None else ("En attente" if not _has_real else "—"),
                    )
                    _mc[2].metric(
                        "Différence",
                        f"{_tot_diff:+.1f} pts" if _tot_diff is not None else "—",
                        delta=f"{_tot_diff:+.1f}" if _tot_diff is not None else None,
                    )

                    if not _has_real:
                        st.caption("Les résultats de cette GW ne sont pas encore disponibles.")

                    st.dataframe(
                        _df10[["Slot", "Joueur", "✏️", "Prédit", "Réel", "Diff"]]
                        .style.map(_color_diff10, subset=["Diff"]),
                        use_container_width=True,
                        hide_index=True,
                    )

                    # ── Comparaison vs suggestions ────────────────────────────
                    def _render_ecart10(sug_dict, label, key_sfx):
                        if not sug_dict:
                            return
                        _diff_slots = [
                            s for s, d in _l10["slots"].items()
                            if d and sug_dict.get(s)
                            and d.get("player_slug") != sug_dict[s].get("player_slug")
                        ]
                        if not _diff_slots:
                            st.caption(f"✅ Votre équipe est identique à la suggestion {label}.")
                            return
                        st.markdown(f"**✏️ Écarts vs suggestion {label}**")
                        _erows = []
                        _tot_act = 0.0
                        _tot_sg  = 0.0
                        for _s in _diff_slots:
                            _a = _l10["slots"][_s]
                            _g = sug_dict[_s]
                            _ra = _gs_gw10.get(_a.get("player_slug")) if _a.get("player_slug") else None
                            _rs = _gs_gw10.get(_g.get("player_slug")) if _g.get("player_slug") else None
                            _gn = round(_ra - _rs, 1) if (_ra is not None and _rs is not None) else None
                            if _ra is not None: _tot_act += _ra
                            if _rs is not None: _tot_sg  += _rs
                            _erows.append({
                                "Slot":         _s,
                                "Joué":         _a.get("player_name", "—"),
                                "Prédit joué":  round(float(_a.get("proj_score_eff") or 0), 1),
                                "Réel joué":    round(float(_ra), 1) if _ra is not None else None,
                                "Suggéré":      _g.get("player_name", "—"),
                                "Prédit sug.":  round(float(_g.get("proj_score_eff") or 0), 1),
                                "Réel suggéré": round(float(_rs), 1) if _rs is not None else None,
                                "Gain/Perte":   _gn,
                            })
                        st.dataframe(
                            pd.DataFrame(_erows).style.map(_color_diff10, subset=["Gain/Perte"]),
                            use_container_width=True, hide_index=True,
                        )
                        if _has_real and _erows:
                            _delta = round(_tot_act - _tot_sg, 1)
                            st.caption(
                                f"Sur ces slots : **{_delta:+.1f} pts** "
                                f"({'mieux' if _delta >= 0 else 'moins bien'} que la suggestion {label})"
                            )

                    _render_ecart10(_sug_auto10,   "Auto (ML)", f"{_lid}_auto")
                    if _sug_sorare10:
                        st.divider()
                        _render_ecart10(_sug_sorare10, "Sorare GW+", f"{_lid}_sor")

                    # ── Bouton supprimer ──────────────────────────────────────
                    if st.button("🗑️ Supprimer ce lineup", key=f"del10_{_lid}"):
                        _delete_lineup(_lid)
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 11 — MARCHÉ (scores ML + prix pour tous les joueurs)
# ═══════════════════════════════════════════════════════════════════════════════

with tab11:
    if df_ml.empty:
        st.info("Aucune prédiction ML disponible. Lancez `update_data.py` pour générer les données.")
    else:
        try:
            _df_p11, _gw11 = load_upcoming_pitchers()
        except Exception:
            _df_p11, _gw11 = pd.DataFrame(), 0

        # Construire le dataframe combiné : scores ML + prix marché
        _ml11 = df_ml[["player_slug", "player_name", "position", "team_slug",
                        "n_games_gw", "pred_median", "pred_lo", "pred_hi",
                        "gallery_manager"]].copy()
        _ml11["n_games_gw"]  = pd.to_numeric(_ml11["n_games_gw"],  errors="coerce").fillna(0).astype(int)
        _ml11["pred_median"] = pd.to_numeric(_ml11["pred_median"], errors="coerce")
        _ml11["ml_score"]    = (_ml11["pred_median"] * _ml11["n_games_gw"]).round(1)
        _ml11["position_agg"] = _ml11["position"].map(lambda x: POSITION_AGG.get(x, x) if x else x)

        _price_cols11 = ["price_limited_is", "price_limited_oos",
                         "price_rare_is", "price_rare_oos",
                         "price_sr_is", "price_sr_oos",
                         "price_unique_is", "price_unique_oos"]

        if not df_market.empty:
            _ml11 = _ml11.merge(
                df_market[["player_slug"] + [c for c in _price_cols11 if c in df_market.columns]],
                on="player_slug", how="left",
            )
        else:
            for c in _price_cols11:
                _ml11[c] = float("nan")

        _ml11["valeur_lim_is"] = (_ml11["ml_score"] / _ml11["price_limited_is"]).round(3)

        _gw_lbl11 = f"GW{_gw11}" if _gw11 else "prochaine GW"
        st.subheader(f"{_gw_lbl11} — Score ML + Prix marché ({len(_ml11)} joueurs)")

        if df_market.empty:
            st.warning(
                "Aucun prix disponible. Lancez `python update_data.py --prices-all` "
                "pour récupérer les prix de tous les joueurs GW (~10k appels API)."
            )
        elif _ml11["price_limited_is"].notna().sum() < len(_ml11) * 0.5:
            st.info(
                f"Prix disponibles pour {_ml11['price_limited_is'].notna().sum()} joueurs sur {len(_ml11)}. "
                "Lancez `python update_data.py --prices-all` pour étendre la couverture."
            )

        # ── Filtres ───────────────────────────────────────────────────────────
        _c11a, _c11b, _c11c, _c11d = st.columns([2, 2, 2, 2])
        with _c11a:
            _pos_filter11 = st.multiselect(
                "Position", ["SP", "RP", "CI", "MI", "OF"],
                default=[], key="mkt11_pos",
            )
        with _c11b:
            _only_priced11 = st.checkbox("Avec prix uniquement", value=False, key="mkt11_priced")
        with _c11c:
            _only_gw11 = st.checkbox("En GW uniquement", value=True, key="mkt11_gw")
        with _c11d:
            _sort11 = st.selectbox(
                "Trier par",
                ["Score ML", "Valeur (pts/€ Lim IS)", "Prix Lim IS", "Prix Lim OOS"],
                key="mkt11_sort",
            )

        _sort_col_map11 = {
            "Score ML":             "ml_score",
            "Valeur (pts/€ Lim IS)": "valeur_lim_is",
            "Prix Lim IS":          "price_limited_is",
            "Prix Lim OOS":         "price_limited_oos",
        }

        _df11 = _ml11.copy()

        if _only_gw11:
            _df11 = _df11[_df11["n_games_gw"] > 0]

        if _pos_filter11:
            _pos_to_raw11 = {
                "SP":  ["SP", "baseball_starting_pitcher"],
                "RP":  ["RP", "baseball_relief_pitcher"],
                "CI":  ["CI", "baseball_first_base", "baseball_third_base", "baseball_designated_hitter"],
                "MI":  ["MI", "baseball_second_base", "baseball_shortstop", "baseball_catcher"],
                "OF":  ["OF", "baseball_outfield"],
            }
            _allowed11 = set()
            for _p in _pos_filter11:
                _allowed11.update(_pos_to_raw11.get(_p, [_p]))
            _df11 = _df11[_df11["position"].isin(_allowed11) | _df11["position_agg"].isin(_pos_filter11)]

        if _only_priced11:
            _df11 = _df11[_df11["price_limited_is"].notna() | _df11["price_limited_oos"].notna()]

        _sort_key11 = _sort_col_map11.get(_sort11, "ml_score")
        if _sort_key11 in _df11.columns:
            _df11 = _df11.sort_values(_sort_key11, ascending=False, na_position="last")

        # ── Affichage dataframe ───────────────────────────────────────────────
        _display_rename11 = {
            "player_name":      "Joueur",
            "position_agg":     "Pos",
            "team_slug":        "Équipe",
            "n_games_gw":       "N matchs",
            "ml_score":         "Score ML",
            "price_limited_is":  "Lim IS (€)",
            "price_limited_oos": "Lim OOS (€)",
            "price_rare_is":     "Rare IS (€)",
            "price_rare_oos":    "Rare OOS (€)",
            "price_sr_is":       "SR IS (€)",
            "price_sr_oos":      "SR OOS (€)",
            "price_unique_is":   "Unique IS (€)",
            "price_unique_oos":  "Unique OOS (€)",
            "valeur_lim_is":     "Pts/€ Lim IS",
            "gallery_manager":   "Galerie",
        }
        _show_cols11 = ["player_name", "position_agg", "team_slug", "n_games_gw", "ml_score",
                        "price_limited_is", "price_limited_oos",
                        "price_rare_is", "price_rare_oos",
                        "price_sr_is", "price_sr_oos",
                        "price_unique_is", "price_unique_oos",
                        "valeur_lim_is", "gallery_manager"]
        _show_cols11 = [c for c in _show_cols11 if c in _df11.columns]

        _col_cfg11 = {
            "Joueur":       st.column_config.TextColumn(),
            "Score ML":     st.column_config.NumberColumn(format="%.1f"),
            "Lim IS (€)":   st.column_config.NumberColumn(format="%.0f"),
            "Lim OOS (€)":  st.column_config.NumberColumn(format="%.0f"),
            "Rare IS (€)":  st.column_config.NumberColumn(format="%.0f"),
            "Rare OOS (€)": st.column_config.NumberColumn(format="%.0f"),
            "SR IS (€)":    st.column_config.NumberColumn(format="%.0f"),
            "SR OOS (€)":   st.column_config.NumberColumn(format="%.0f"),
            "Unique IS (€)": st.column_config.NumberColumn(format="%.0f"),
            "Unique OOS (€)": st.column_config.NumberColumn(format="%.0f"),
            "Pts/€ Lim IS": st.column_config.NumberColumn(format="%.3f"),
        }

        st.dataframe(
            _df11[_show_cols11].rename(columns=_display_rename11),
            use_container_width=True,
            column_config=_col_cfg11,
            hide_index=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 12 — Comparaison prédictions platoon (temporaire)
# ═══════════════════════════════════════════════════════════════════════════════

with tab12:
    st.subheader("🔬 Comparaison prédictions platoon — GW à venir")
    st.caption(
        "Onglet temporaire : compare les 5 indicateurs de score (Base EWMA, Sorare GW+, "
        "Options A/B/C platoon). À supprimer après validation."
    )

    if df_ml.empty:
        st.info("Aucune prédiction ML. Lance `python ml_predict_gw.py`.")
    else:
        _has_plat12 = df_ml["pred_A"].notna().any()
        _PITCHER_POS12 = {"SP", "RP", "baseball_starting_pitcher", "baseball_relief_pitcher"}

        _c12a, _c12b, _c12c = st.columns([2, 2, 3])
        with _c12a:
            _mgr_opts12 = ["Tous"] + sorted(df_ml["gallery_manager"].dropna().unique().tolist())
            _filt_mgr12 = st.radio("Manager", _mgr_opts12, horizontal=True, key="plt12_mgr")
        with _c12b:
            _filt_pos12 = st.radio(
                "Position", ["Tous", "Hitters", "Pitchers"],
                horizontal=True, key="plt12_pos",
            )
        with _c12c:
            _sort_opts12 = ["Option C (hybride)", "Option B (league avg)",
                            "Option A (perso.)", "Base EWMA", "Sorare GW+"]
            _sort12 = st.radio("Trier par", _sort_opts12, horizontal=True, key="plt12_sort")

        _df12 = df_ml.copy()
        if _filt_mgr12 != "Tous":
            _df12 = _df12[_df12["gallery_manager"] == _filt_mgr12]
        if _filt_pos12 == "Hitters":
            _df12 = _df12[~_df12["position"].isin(_PITCHER_POS12)]
        elif _filt_pos12 == "Pitchers":
            _df12 = _df12[_df12["position"].isin(_PITCHER_POS12)]

        # Scores GW totaux = prédiction par match × n_games_gw
        _n12 = pd.to_numeric(_df12["n_games_gw"], errors="coerce").fillna(1)
        for _c12 in ("pred_median", "pred_A", "pred_B", "pred_C"):
            if _c12 in _df12.columns:
                _df12[f"gw_{_c12}"] = (pd.to_numeric(_df12[_c12], errors="coerce") * _n12).round(1)

        _sort_map12 = {
            "Option C (hybride)":  "gw_pred_C",
            "Option B (league avg)": "gw_pred_B",
            "Option A (perso.)":   "gw_pred_A",
            "Base EWMA":           "gw_pred_median",
            "Sorare GW+":          "proj_score_sorare",
        }
        _sc12 = _sort_map12[_sort12]
        if _sc12 in _df12.columns:
            _df12 = _df12.sort_values(_sc12, ascending=False, na_position="last")

        _pos_short12 = {"baseball_starting_pitcher": "SP", "baseball_relief_pitcher": "RP"}
        _df12["pos_disp"] = _df12["position"].map(lambda x: _pos_short12.get(x, x) if x else "")

        _dcols12 = ["player_name", "pos_disp", "team_slug", "n_games_gw"]
        if "bat_hand" in _df12.columns:
            _dcols12.append("bat_hand")
        if "opp_pitcher_hand" in _df12.columns:
            _dcols12.append("opp_pitcher_hand")
        _dcols12.append("gw_pred_median")
        if "proj_score_sorare" in _df12.columns:
            _dcols12.append("proj_score_sorare")
        if _has_plat12:
            _dcols12 += [
                "gw_pred_A", "platoon_factor_A",
                "gw_pred_B", "platoon_factor_B",
                "gw_pred_C", "platoon_factor_C",
            ]

        _rename12 = {
            "player_name": "Joueur", "pos_disp": "Pos", "team_slug": "Équipe",
            "n_games_gw": "GW matchs", "bat_hand": "Main",
            "opp_pitcher_hand": "Pitcher(s) adverse(s)",
            "gw_pred_median": "Base EWMA (GW)",
            "proj_score_sorare": "Sorare GW+",
            "gw_pred_A": "Option A — perso. (GW)", "platoon_factor_A": "× A",
            "gw_pred_B": "Option B — league avg (GW)", "platoon_factor_B": "× B",
            "gw_pred_C": "Option C — hybride (GW)", "platoon_factor_C": "× C",
        }

        _disp12 = (
            _df12[[c for c in _dcols12 if c in _df12.columns]]
            .rename(columns=_rename12)
        )
        for _cn12 in _disp12.select_dtypes("number").columns:
            _disp12[_cn12] = _disp12[_cn12].round(3 if "×" in _cn12 else 1)

        st.dataframe(_disp12, use_container_width=True, height=600, hide_index=True)

        if not _has_plat12:
            st.warning(
                "⚠️ Colonnes platoon absentes — relance `python ml_predict_gw.py` pour les générer."
            )

        with st.expander("ℹ️ Explication des indicateurs"):
            st.markdown("""
**Base EWMA** — EWMA (demi-vie 25 matchs) des scores historiques × nb matchs GW. Pas d'ajustement pitcher.

**Sorare GW+** — Score projeté par Sorare pour la GW Classic.

**Option A — Splits personnels** — Ajuste sur la moyenne réelle du hitter vs pitchers G/D dans l'historique.
Facteur = `avg_score_vs_main / avg_score_global`. Requiert ≥15 matchs vs cette main ; facteur = ×1.00 si données insuffisantes.

**Option B — League average** — Facteurs MLB moyens selon (main hitter × main pitcher) :

| Hitter \\ Pitcher | Gaucher | Droitier |
|---|---|---|
| **Gaucher** | ×0.94 | ×1.03 |
| **Droitier** | ×1.05 | ×0.97 |
| **Switch** | ×1.00 | ×1.00 |

**Option C — Hybride** — Splits personnels si ≥15 matchs, mélange progressif entre 5 et 14 matchs, league average si <5 matchs.

*Pitchers : aucun ajustement platoon appliqué (ils affrontent des lineups mixtes).*
""")
        st.caption("Source bat_hand : `mlb.players.bat_hand` (Sorare API). Pitcher adverse : `mlb.games.{home,away}_probable_pitcher`.")
