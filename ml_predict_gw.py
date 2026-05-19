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

PLATOON_B_FACTORS = {          # multiplicateurs league-average (main_hitter, main_pitcher)
    ("L", "L"): 0.94, ("L", "R"): 1.03,
    ("R", "L"): 1.05, ("R", "R"): 0.97,
    ("S", "L"): 1.00, ("S", "R"): 1.00,
}
MIN_SPLIT_GAMES = 15            # matchs minimum vs une main donnée pour Option A

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

    def _platoon_b(bh, ph) -> float:
        b = (bh or "").strip().upper()[:1]
        p = (ph or "").strip().upper()[:1]
        return PLATOON_B_FACTORS.get((b, p), 1.0)

    # ── 6. Calcul par joueur ─────────────────────────────────────────────────
    scores_grouped = {
        slug: grp["score"].to_numpy()
        for slug, grp in scores.groupby("player_slug")
    }

    # ── 6b. Donnees platoon ───────────────────────────────────────────────────
    bh_df = pd.read_sql(
        "SELECT player_slug, bat_hand FROM mlb.players WHERE player_slug IN %s",
        engine, params=(slugs,)
    )
    bat_hand_map: dict = bh_df.set_index("player_slug")["bat_hand"].to_dict()

    upg = pd.read_sql("""
        SELECT home_team_slug, away_team_slug,
               home_probable_pitcher, away_probable_pitcher
        FROM mlb.games WHERE gw_int = %s
    """, engine, params=(upcoming_gw,))
    pit_slugs_up: set = set()
    if not upg.empty:
        pit_slugs_up.update(upg["home_probable_pitcher"].dropna())
        pit_slugs_up.update(upg["away_probable_pitcher"].dropna())
    pit_hand_up: dict = {}
    if pit_slugs_up:
        ph_df = pd.read_sql(
            "SELECT player_slug, bat_hand FROM mlb.players WHERE player_slug IN %s",
            engine, params=(tuple(pit_slugs_up),)
        )
        pit_hand_up = ph_df.set_index("player_slug")["bat_hand"].to_dict()

    # Hitters domicile affrontent away_probable_pitcher, visiteurs le home_probable_pitcher
    team_opp_hands: dict = {}
    for _, g in upg.iterrows():
        aph = pit_hand_up.get(g.get("away_probable_pitcher") or "")
        if aph and g["home_team_slug"]:
            team_opp_hands.setdefault(g["home_team_slug"], []).append(aph)
        hph = pit_hand_up.get(g.get("home_probable_pitcher") or "")
        if hph and g["away_team_slug"]:
            team_opp_hands.setdefault(g["away_team_slug"], []).append(hph)

    hitter_slugs_plat = tuple(
        r["player_slug"] for _, r in players.iterrows()
        if not _is_pitcher(r["position"])
    )
    hitter_splits: dict = {}
    if hitter_slugs_plat:
        try:
            spl_df = pd.read_sql("""
                WITH hg AS (
                    SELECT gs.player_slug,
                           gs.score::float AS score,
                           CASE
                               -- Hitter visiteur : pitcher est du cote domicile
                               WHEN g.away_team_slug = p.team_slug THEN
                                   COALESCE(
                                       g.home_probable_pitcher,
                                       CASE WHEN g.winner_slug = g.home_team_slug
                                            THEN g.winning_pitcher
                                            ELSE g.losing_pitcher END
                                   )
                               -- Hitter domicile : pitcher est du cote visiteur
                               WHEN g.home_team_slug = p.team_slug THEN
                                   COALESCE(
                                       g.away_probable_pitcher,
                                       CASE WHEN g.winner_slug = g.away_team_slug
                                            THEN g.winning_pitcher
                                            ELSE g.losing_pitcher END
                                   )
                           END AS opp_pitcher_slug
                    FROM mlb.game_scores gs
                    JOIN mlb.players p ON gs.player_slug = p.player_slug
                    JOIN mlb.games g
                        ON gs.game_date::date = g.game_date::date
                       AND (g.home_team_slug = p.team_slug
                            OR g.away_team_slug = p.team_slug)
                    WHERE gs.played_in_game = true
                      AND gs.score IS NOT NULL
                      AND gs.player_slug IN %s
                )
                SELECT hg.player_slug, hg.score, p2.bat_hand AS pitcher_hand
                FROM hg
                LEFT JOIN mlb.players p2 ON hg.opp_pitcher_slug = p2.player_slug
                WHERE p2.bat_hand IS NOT NULL
            """, engine, params=(hitter_slugs_plat,))
            for slug_h, grp_h in spl_df.groupby("player_slug"):
                rec: dict = {"overall_avg": float(grp_h["score"].mean())}
                for h in ("L", "R"):
                    sub = grp_h[grp_h["pitcher_hand"] == h]["score"]
                    rec[f"n_vs_{h}"]   = len(sub)
                    rec[f"avg_vs_{h}"] = float(sub.mean()) if len(sub) else None
                hitter_splits[str(slug_h)] = rec
        except Exception as exc:
            print(f"  Warning platoon splits: {exc}")

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
        mu     = pred["pred_median"]

        # ── Facteurs platoon ─────────────────────────────────────────────────
        bh        = (bat_hand_map.get(slug) or "").strip().upper()[:1] or None
        opp_hands = [ph for ph in team_opp_hands.get(team, []) if ph]

        if _is_pitcher(position) or not opp_hands or not bh:
            factor_a = factor_b = factor_c = 1.0
        else:
            fb_list  = [_platoon_b(bh, ph) for ph in opp_hands]
            factor_b = sum(fb_list) / len(fb_list)

            splits  = hitter_splits.get(slug, {})
            ov_avg  = splits.get("overall_avg") or 0.0
            fa_list = []
            for ph in opp_hands:
                ph_key = ph.strip().upper()[:1]
                n_vs   = splits.get(f"n_vs_{ph_key}", 0)
                avg_vs = splits.get(f"avg_vs_{ph_key}")
                fa_list.append(
                    avg_vs / ov_avg
                    if (n_vs >= MIN_SPLIT_GAMES and avg_vs is not None and ov_avg > 0)
                    else None
                )
            valid_fa = [f for f in fa_list if f is not None]
            factor_a = sum(valid_fa) / len(valid_fa) if valid_fa else 1.0

            fc_list = []
            for ph in opp_hands:
                ph_key = ph.strip().upper()[:1]
                n_vs   = splits.get(f"n_vs_{ph_key}", 0)
                avg_vs = splits.get(f"avg_vs_{ph_key}")
                fb_loc = _platoon_b(bh, ph)
                if n_vs >= MIN_SPLIT_GAMES and avg_vs is not None and ov_avg > 0:
                    fc_list.append(avg_vs / ov_avg)
                elif n_vs >= 5 and avg_vs is not None and ov_avg > 0:
                    weight = n_vs / MIN_SPLIT_GAMES
                    fc_list.append(weight * (avg_vs / ov_avg) + (1 - weight) * fb_loc)
                else:
                    fc_list.append(fb_loc)
            factor_c = sum(fc_list) / len(fc_list) if fc_list else 1.0

        rows.append({
            "player_slug":      slug,
            "player_name":      player["player_name"],
            "id_manager":       player.get("id_manager"),
            "gallery_manager":  player.get("gallery_manager"),
            "position":         position,
            "team_slug":        team,
            "n_games_gw":       n_gw,
            "next_game_date":   pd.to_datetime(
                player.get("next_game_date"), utc=True, errors="coerce"
            ),
            "n_games_history":  n_hist,
            "bat_hand":         bh,
            "opp_pitcher_hand": "/".join(dict.fromkeys(opp_hands)) if opp_hands else None,
            "pred_median":      mu,
            "pred_lo":          pred["pred_lo"],
            "pred_hi":          pred["pred_hi"],
            "platoon_factor_A": round(factor_a, 4),
            "platoon_factor_B": round(factor_b, 4),
            "platoon_factor_C": round(factor_c, 4),
            "pred_A":           round(mu * factor_a, 3),
            "pred_B":           round(mu * factor_b, 3),
            "pred_C":           round(mu * factor_c, 3),
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
