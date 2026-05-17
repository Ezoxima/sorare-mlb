"""
ml_predict_gw.py
----------------
Calcule les predictions pour TOUS les joueurs dont l'equipe joue dans
la prochaine GW, et les sauvegarde dans data/ml_predictions.parquet.

Approche : moyenne ponderee exponentiellement (EWMA) par joueur
  - mu     = EWMA des scores historiques (half-life 25 matchs)
  - sigma  = ecart-type empirique sur les 50 derniers matchs
  - IC 80% per match : mu +/- 1.282 * sigma
  - n_games_gw : nb de matchs de l'equipe dans la GW (pour scaling dans l'app)

La colonne gallery_manager est renseignee uniquement pour les joueurs
presents dans la galerie d'un manager.

Usage :
    python ml_predict_gw.py
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).parent.parent / ".env")

DB_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME')}"
)
DATA_DIR = Path(__file__).parent / "data"
OUT_FILE = DATA_DIR / "ml_predictions.parquet"

HALF_LIFE = 25
SIGMA_N   = 50
MIN_GAMES = 5
Z80       = 1.282

_PITCHER_POSITIONS = {
    "SP", "RP",
    "baseball_starting_pitcher",
    "baseball_relief_pitcher",
}


def _is_pitcher(pos: str) -> bool:
    return str(pos or "").strip() in _PITCHER_POSITIONS


def _exp_weights(n: int) -> np.ndarray:
    i = np.arange(n, dtype=float)
    w = 0.5 ** ((n - 1 - i) / HALF_LIFE)
    return w / w.sum()


def _predict_player(scores_asc: np.ndarray) -> dict:
    w  = _exp_weights(len(scores_asc))
    mu = float(np.dot(w, scores_asc))
    recent = scores_asc[-SIGMA_N:]
    sigma  = float(np.std(recent, ddof=1)) if len(recent) >= 2 else 0.0
    hw = Z80 * sigma
    return {
        "pred_median": mu,
        "pred_lo":     max(0.0, mu - hw),
        "pred_hi":     mu + hw,
    }


def run(engine=None):
    if engine is None:
        engine = create_engine(DB_URL)

    # ── 1. Prochaine GW et equipes concernees ────────────────────────────────
    gw_row = pd.read_sql("""
        SELECT MIN(gw_int) AS gw_int,
               MIN(game_date)::date AS gw_start,
               MAX(game_date)::date AS gw_end
        FROM mlb.games
        WHERE game_date >= CURRENT_DATE
    """, engine).iloc[0]

    if pd.isna(gw_row["gw_int"]):
        print("  Aucune GW a venir dans mlb.games.")
        return pd.DataFrame()

    upcoming_gw = int(gw_row["gw_int"])
    print(f"  GW{upcoming_gw}  ({gw_row['gw_start']} -> {gw_row['gw_end']})")

    # Nb de matchs par equipe dans la GW
    team_games = pd.read_sql("""
        SELECT team_slug, COUNT(*)::int AS n_games
        FROM (
            SELECT home_team_slug AS team_slug FROM mlb.games WHERE gw_int = %s
            UNION ALL
            SELECT away_team_slug               FROM mlb.games WHERE gw_int = %s
        ) t
        GROUP BY team_slug
    """, engine, params=(upcoming_gw, upcoming_gw))
    team_n    = team_games.set_index("team_slug")["n_games"].to_dict()
    gw_teams  = tuple(team_n.keys())

    print(f"  {len(gw_teams)} equipes dans la GW")

    # ── 2. Tous les joueurs de ces equipes ───────────────────────────────────
    players = pd.read_sql("""
        SELECT player_slug,
               display_name  AS player_name,
               team_slug,
               agg_position_1 AS position
        FROM mlb.players
        WHERE team_slug IN %s
    """, engine, params=(gw_teams,))

    if players.empty:
        print("  Aucun joueur trouve pour ces equipes.")
        return pd.DataFrame()

    print(f"  {len(players)} joueurs trouves")

    # ── 3. Appartenance a la galerie ─────────────────────────────────────────
    gallery = pd.read_sql("""
        SELECT DISTINCT ON (player_slug)
            player_slug,
            id_manager,
            gallery_manager,
            card_display_position AS position_gallery,
            next_game_date
        FROM mlb.gallery_players
        ORDER BY player_slug, next_game_date
    """, engine)

    players = players.merge(
        gallery[["player_slug", "id_manager", "gallery_manager",
                 "position_gallery", "next_game_date"]],
        on="player_slug", how="left",
    )
    # Priorite a la position de la carte (plus precise que agg_position_1)
    players["position"] = players["position_gallery"].combine_first(players["position"])

    # ── 4. Historique des scores ─────────────────────────────────────────────
    slugs = tuple(players["player_slug"].unique())
    scores = pd.read_sql("""
        SELECT player_slug, game_date, score::float AS score
        FROM mlb.game_scores
        WHERE player_slug IN %s
          AND played_in_game = true
          AND score IS NOT NULL
        ORDER BY player_slug, game_date
    """, engine, params=(slugs,))

    # ── 5. Fallback global hitter/pitcher ────────────────────────────────────
    if not scores.empty:
        _pos_map = players.set_index("player_slug")["position"].to_dict()
        scores["_pitcher"] = scores["player_slug"].map(
            lambda s: _is_pitcher(_pos_map.get(s, ""))
        )
        fb = (
            scores.groupby("_pitcher")["score"]
            .agg(mu="mean", sigma=lambda x: x.std(ddof=1))
            .rename(index={True: "pitcher", False: "hitter"})
        )
    else:
        fb = pd.DataFrame(
            {"mu": {"hitter": 5.5, "pitcher": 15.0},
             "sigma": {"hitter": 4.0, "pitcher": 10.0}}
        )

    def _fallback(pos: str) -> dict:
        grp   = "pitcher" if _is_pitcher(pos) else "hitter"
        mu    = float(fb.loc[grp, "mu"])    if grp in fb.index else 5.5
        sigma = float(fb.loc[grp, "sigma"]) if grp in fb.index else 4.0
        hw    = Z80 * sigma
        return {"pred_median": mu, "pred_lo": max(0.0, mu - hw), "pred_hi": mu + hw}

    # ── 6. Calcul par joueur ─────────────────────────────────────────────────
    scores_grouped = {
        slug: grp["score"].to_numpy()
        for slug, grp in scores.groupby("player_slug")
    }

    rows = []
    for _, player in players.iterrows():
        slug     = player["player_slug"]
        position = player["position"]
        team     = player["team_slug"]
        n_gw     = int(team_n.get(team, 0))

        # SPs : 1 depart par GW ; RPs et hitters : n matchs de l'equipe
        if position in ("SP", "baseball_starting_pitcher"):
            n_gw = min(n_gw, 1)

        h      = scores_grouped.get(slug, np.array([]))
        n_hist = len(h)

        pred   = _predict_player(h) if n_hist >= MIN_GAMES else _fallback(position)

        rows.append({
            "player_slug":     slug,
            "player_name":     player["player_name"],
            "id_manager":      player.get("id_manager"),
            "gallery_manager": player.get("gallery_manager"),
            "position":        position,
            "team_slug":       team,
            "n_games_gw":      n_gw,
            "next_game_date":  pd.to_datetime(
                player.get("next_game_date"), utc=True, errors="coerce"
            ),
            "n_games_history": n_hist,
            "pred_median":     pred["pred_median"],
            "pred_lo":         pred["pred_lo"],
            "pred_hi":         pred["pred_hi"],
        })

    if not rows:
        print("  Aucune prediction generee.")
        return pd.DataFrame()

    df_pred = pd.DataFrame(rows)
    df_pred.to_parquet(OUT_FILE, index=False)

    n_gal = df_pred["gallery_manager"].notna().sum()
    print(f"  {len(df_pred)} predictions ({n_gal} en galerie) -> {OUT_FILE.name}")
    return df_pred


if __name__ == "__main__":
    print("[Pred] Calcul des predictions GW (tous joueurs de la GW)...")
    df = run()
    if not df.empty:
        print("\nTop 20 (pred_median desc) :")
        print(df[["player_name", "position", "n_games_gw", "n_games_history",
                   "pred_lo", "pred_median", "pred_hi"]]
              .sort_values("pred_median", ascending=False)
              .head(20)
              .to_string(index=False))
