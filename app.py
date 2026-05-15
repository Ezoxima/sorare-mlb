import os
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

_DATA_DIR = Path(__file__).parent / "data"


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
_slugs_today = set(_cal_today["player_slug"])
df_today = df[df["player_slug"].isin(_slugs_today)].reset_index(drop=True)

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

# ── Tabs ────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "🏆 Ma galerie",
    "📅 Calendrier",
    "💰 Mes cartes",
    "🔍 Base de données",
    "⚾ Pitchers GW",
    "⚔️ Vis-à-vis",
    "📈 Projections GW",
    "🏗️ Équipe",
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
        st.stop()

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

        # Joueurs blessés (actifs)
        injured_slugs = set(load_injured_players())

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
            proj7.append({
                "player_slug":       h_slug,
                "player_name":       row["player_name"],
                "rarity":            row["card_display_rarity"] or "",
                "position":          row["position_exact"] or row["position_agg"] or "?",
                "in_season_eligible": row["in_season_eligible"],
                "category":          "Hitter",
                "nb_games":          nb_g,
                "projected_score":   round(total, 1) if nb_g > 0 else None,
                "breakdown":         "  ·  ".join(parts) if parts else "—",
            })

        for _, row in _gal_sp7.iterrows():
            ps    = row["player_slug"]
            score = pavg7.get(ps)
            proj7.append({
                "player_slug":       ps,
                "player_name":       row["player_name"],
                "rarity":            row["card_display_rarity"] or "",
                "position":          "SP",
                "in_season_eligible": row["in_season_eligible"],
                "category":          "SP",
                "nb_games":          1 if score is not None else 0,
                "projected_score":   round(float(score), 1) if score is not None else None,
                "breakdown":         f"~{score:.1f} moy 5 derniers" if score else "—",
            })

        df7 = (
            pd.DataFrame(proj7)
            .sort_values("projected_score", ascending=False, na_position="last")
            .reset_index(drop=True)
        )

        # ── Métriques ────────────────────────────────────────────────────────
        st.subheader(f"GW{gw7} — Projections de score")
        st.caption(
            "🎯 = score basé sur l'historique vs ce pitcher spécifique  ·  "
            f"~ = moyenne générale ({fenetre})"
        )

        col71, col72, col73 = st.columns(3)
        col71.metric("Hitters en galerie",  len(_gal_h7))
        col72.metric("SP en galerie",       len(_gal_sp7))
        if not df7.empty and pd.notna(df7.iloc[0]["projected_score"]):
            best7 = df7.iloc[0]
            col73.metric(
                "Meilleure projection",
                f"{best7['projected_score']:.1f} pts",
                best7["player_name"],
            )

        st.divider()

        # Filtres
        col7f1, col7f2 = st.columns([2, 2])
        with col7f1:
            show_cat7 = st.multiselect(
                "Catégorie", ["Hitter", "SP"],
                default=["Hitter", "SP"], key="proj7_cat",
            )
        with col7f2:
            show_is7 = st.checkbox("In Season uniquement", value=False, key="proj7_is")

        df7_f = df7[df7["category"].isin(show_cat7)].copy()
        if show_is7:
            df7_f = df7_f[df7_f["in_season_eligible"] == True]

        # ── Affichage ────────────────────────────────────────────────────────
        for _, row7 in df7_f.iterrows():
            if pd.isna(row7["projected_score"]):
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
                f'<div class="stat-value">{row7["projected_score"]:.1f}'
                f'<small style="font-size:0.7rem;font-weight:400;opacity:0.7"> pts GW proj.</small>'
                f'</div>'
                f'<div class="kickoff" style="font-size:0.72rem;opacity:0.55">'
                f'{row7["breakdown"]}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 8 — CONSTRUCTION D'ÉQUIPE
# ═══════════════════════════════════════════════════════════════════════════════

with tab8:
    from collections import Counter as _Counter

    _EMPTY_TEAM = lambda: {s: None for s in ["SP", "RP", "CI", "MI", "OF", "Flex", "Libre"]}
    _SLOT_POS   = {
        "SP":    ["SP"],
        "RP":    ["RP"],
        "CI":    ["CI"],
        "MI":    ["MI"],
        "OF":    ["OF"],
        "Flex":  ["CI", "MI", "OF"],
        "Libre": ["SP", "RP", "CI", "MI", "OF"],
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

    _require_is = tb_mode in ("Champions", "Hot Streak")
    _max_t      = _MAX_TEAMS[tb_mode]

    # ── State par mode × rareté ────────────────────────────────────────────────
    _tb_sk = f"tb_teams_{tb_mode}_{tb_rar}"
    if _tb_sk not in st.session_state:
        st.session_state[_tb_sk] = [_EMPTY_TEAM()]
    tb_teams = st.session_state[_tb_sk]

    # ── Joueurs disponibles ────────────────────────────────────────────────────
    df_tb = (
        df_prices[
            (df_prices["gallery_manager"] == sel_manager) &
            (df_prices["card_display_rarity"].str.lower() == tb_rar.lower())
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
        _df_p8, _ = load_upcoming_pitchers()
    except Exception:
        _df_p8 = pd.DataFrame()

    if not _df_p8.empty:
        _tsched8: dict = {}
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

        df_tb["proj_score"] = df_tb.apply(
            lambda r: _gw_score8(r["player_slug"], r["active_club_slug"], r["position_agg"]),
            axis=1,
        )
    else:
        df_tb["proj_score"] = df_tb["player_slug"].map(_smap_tb).fillna(0.0)

    # Index card_name → row
    _cl = df_tb.set_index("card_name").to_dict("index")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _fmt_opt(x: str) -> str:
        if x == "—":
            return "—"
        r   = _cl.get(x, {})
        pos = r.get("position_exact") or "?"
        is_ = "IS" if r.get("is_eligible") else "OOS"
        sc  = r.get("proj_score") or 0.0
        return f"{x}  [{pos} · {is_} · {sc:.0f} pts]"

    def _tb_suggest(other_used: set, require_is: bool) -> dict:
        """Greedy team builder : IS en priorité, puis score projeté desc."""
        result:  dict = {}
        used:    set  = set()
        is_map        = df_tb.set_index("card_name")["is_eligible"].to_dict()
        df_s          = df_tb.sort_values(
            ["is_eligible", "proj_score"], ascending=[False, False]
        )
        slots = list(_SLOT_POS.items())
        n     = len(slots)
        for i, (slot_name, valid_pos) in enumerate(slots):
            cands = df_s[
                df_s["position_agg"].isin(valid_pos) &
                ~df_s["card_name"].isin(other_used | used)
            ]
            if cands.empty:
                result[slot_name] = None
                continue
            if require_is:
                is_so_far    = sum(1 for c in used if is_map.get(c, False))
                remaining    = n - i
                must_be_is   = max(0, 6 - is_so_far - (remaining - 1))
                if must_be_is > 0:
                    is_cands = cands[cands["is_eligible"]]
                    if not is_cands.empty:
                        cands = is_cands
            result[slot_name] = cands.iloc[0]["card_name"]
            used.add(result[slot_name])
        return result

    def _team_validation(team: dict) -> tuple:
        """Retourne (is_count, max_club_count, total_score, n_filled)."""
        cards = [v for v in team.values() if v]
        if not cards:
            return 0, 0, 0.0, 0
        is_c   = sum(1 for c in cards if _cl.get(c, {}).get("is_eligible", False))
        clubs  = [_cl.get(c, {}).get("active_club_slug", "") for c in cards]
        max_cl = max(_Counter(clubs).values()) if clubs else 0
        score  = sum(_cl.get(c, {}).get("proj_score", 0.0) for c in cards)
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

    # ── Éditeur de chaque équipe ───────────────────────────────────────────────
    for _ti, _team in enumerate(tb_teams):
        # Cartes utilisées dans les AUTRES équipes
        _other_used = {
            c for j, t in enumerate(tb_teams)
            for c in t.values()
            if c and j != _ti
        }

        with st.expander(f"Équipe {_ti + 1}", expanded=True):
            # Boutons suggérer / vider
            _cs, _cc = st.columns([2, 2])
            with _cs:
                if st.button("✨ Suggérer l'équipe", key=f"tb_sug_{_ti}"):
                    _sug = _tb_suggest(_other_used, _require_is)
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
                    _in_team_used = {v for k, v in _team.items() if v and k != _sname}
                    _cands = (
                        df_tb[
                            df_tb["position_agg"].isin(_vpos) &
                            ~df_tb["card_name"].isin(_other_used | _in_team_used)
                        ]
                        .sort_values("proj_score", ascending=False)
                    )
                    _opts    = ["—"] + _cands["card_name"].tolist()
                    _current = _team.get(_sname)
                    # Si la carte courante n'est plus disponible, la garder visible
                    if _current and _current not in _opts:
                        _opts.insert(1, _current)
                    _idx = _opts.index(_current) if _current in _opts else 0

                    _chosen = st.selectbox(
                        f"**{_sname}**"
                        + (" *(CI/MI/OF)*" if _sname == "Flex" else "")
                        + (" *(toute pos.)*" if _sname == "Libre" else ""),
                        _opts,
                        index=_idx,
                        key=f"tb_{_ti}_{_sname}",
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
                    f'<span style="color:#4CAF50">⚾ Score proj. : <b>{_sc:.1f}</b> pts</span>'
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
