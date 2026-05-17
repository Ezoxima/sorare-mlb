"""
ml_pipeline.py
--------------
Pipeline ML — prediction du score Sorare MLB.

2 modeles :
  - hitters  : OF, 1B, 2B, 3B, SS, C, DH
  - pitchers : SP + RP (is_sp comme feature discriminante)

Methode : LightGBM quantile (q=0.10/0.50/0.90) + calibration conforme
          → intervalle de prediction a 80% avec garantie marginale.

Split temporel strict (pas de fuite) :
  Train  : GW <= 100
  Val    : GW 101-115  (aussi utilise pour la calibration conforme)
  Test   : GW > 115

Usage :
    python ml_pipeline.py
"""

import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).parent.parent / ".env")

DB_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME')}"
)
MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

TRAIN_GW_MAX = 100
VAL_GW_MAX   = 115

# ── 1. Chargement ────────────────────────────────────────────────────────────

def load_raw_data(engine):
    print("[1/5] Chargement game_scores...")
    gs = pd.read_sql("""
        SELECT player_slug, game_date, gw_int, score::float AS score, position
        FROM mlb.game_scores
        WHERE played_in_game = true AND score IS NOT NULL
        ORDER BY player_slug, game_date
    """, engine)
    print(f"  {len(gs):,} lignes")

    print("[1/5] Chargement game_score_details...")
    gsd = pd.read_sql("""
        SELECT player_slug, game_date, stat, stat_value::float AS stat_value
        FROM mlb.game_score_details
        WHERE stat IN (
            'hitting_home_runs','hitting_runs_batted_in','hitting_stolen_bases',
            'hitting_walks','hitting_strikeouts','hitting_singles','hitting_doubles',
            'hitting_triples','hitting_runs',
            'pitching_innings_pitched','pitching_strikeouts','pitching_earned_runs',
            'pitching_hits_allowed','pitching_walks','pitching_wins',
            'pitching_saves','pitching_holds','pitching_relief_appearance'
        )
    """, engine)
    print(f"  {len(gsd):,} lignes")

    print("[1/5] Chargement players...")
    players = pd.read_sql(
        "SELECT player_slug, age::float FROM mlb.players", engine
    )
    return gs, gsd, players


# ── 2. Dataset large ─────────────────────────────────────────────────────────

STAT_RENAME = {
    "hitting_home_runs":          "hr",
    "hitting_runs_batted_in":     "rbi",
    "hitting_stolen_bases":       "sb",
    "hitting_walks":              "hit_bb",
    "hitting_strikeouts":         "hit_so",
    "hitting_singles":            "s1",
    "hitting_doubles":            "s2",
    "hitting_triples":            "s3",
    "hitting_runs":               "run",
    "pitching_innings_pitched":   "ip",
    "pitching_strikeouts":        "pit_so",
    "pitching_earned_runs":       "er",
    "pitching_hits_allowed":      "ha",
    "pitching_walks":             "pit_bb",
    "pitching_wins":              "win",
    "pitching_saves":             "sav",
    "pitching_holds":             "hld",
    "pitching_relief_appearance": "app",
}
STAT_COLS = list(STAT_RENAME.values())


def build_wide(gs, gsd, players):
    print("[2/5] Pivot stats...")
    gsd = gsd.copy()
    gsd["stat"] = gsd["stat"].map(STAT_RENAME)
    wide = (
        gsd.pivot_table(index=["player_slug","game_date"], columns="stat",
                        values="stat_value", aggfunc="first")
        .reset_index()
    )
    wide.columns.name = None

    df = gs.merge(wide, on=["player_slug","game_date"], how="left")
    df = df.merge(players, on="player_slug", how="left")

    for c in STAT_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        else:
            df[c] = 0.0

    df["game_date"] = pd.to_datetime(df["game_date"], utc=True)
    df = df.sort_values(["player_slug","game_date"]).reset_index(drop=True)
    print(f"  {len(df):,} lignes x {df.shape[1]} colonnes")
    return df


# ── 3. Feature engineering (training) ────────────────────────────────────────

def _roll_mean(s, w):
    """Moyenne rolling sur les w matchs PRECEDENTS (shift=1, sans fuite)."""
    return s.shift(1).rolling(w, min_periods=max(1, w // 2)).mean()

def _roll_std(s, w):
    return s.shift(1).rolling(w, min_periods=max(2, w // 2)).std()


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    print("[3/5] Feature engineering...")
    grp = df.groupby("player_slug", sort=False)

    for w in [3, 5, 10, 20]:
        df[f"score_roll{w}"] = grp["score"].transform(lambda s: _roll_mean(s, w))
    for w in [3, 5, 10]:
        df[f"score_std{w}"]  = grp["score"].transform(lambda s: _roll_std(s, w))
    for lag in [1, 2, 3]:
        df[f"score_lag{lag}"] = grp["score"].transform(lambda s: s.shift(lag))

    for col in ["hr","rbi","sb","hit_bb","hit_so","s1","s2","run"]:
        for w in [5, 10]:
            df[f"{col}_r{w}"] = grp[col].transform(lambda s: _roll_mean(s, w))

    for col in ["ip","pit_so","er","ha","pit_bb"]:
        for w in [5, 10]:
            df[f"{col}_r{w}"] = grp[col].transform(lambda s: _roll_mean(s, w))

    for col in ["win","sav","hld"]:
        df[f"{col}_r10"] = grp[col].transform(lambda s: _roll_mean(s, 10))

    # Ratios pitching composites (sur 10 matchs)
    ip10 = df["ip_r10"].replace(0, np.nan)
    df["era_r10"]  = df["er_r10"]                          / ip10 * 9
    df["whip_r10"] = (df["pit_bb_r10"] + df["ha_r10"])     / ip10
    df["k9_r10"]   = df["pit_so_r10"]                      / ip10 * 9
    df[["era_r10","whip_r10","k9_r10"]] = (
        df[["era_r10","whip_r10","k9_r10"]].fillna(0)
    )

    df["days_rest"]       = (grp["game_date"]
                             .transform(lambda s: s.diff().dt.days)
                             .clip(upper=15).fillna(4))
    df["games_played_log"] = np.log1p(grp.cumcount())
    df["season"]           = df["game_date"].dt.year
    df["month"]            = df["game_date"].dt.month

    POS = {
        "baseball_starting_pitcher": 0, "baseball_relief_pitcher": 1,
        "baseball_outfield": 2,         "baseball_first_base": 3,
        "baseball_second_base": 4,      "baseball_third_base": 5,
        "baseball_shortstop": 6,        "baseball_catcher": 7,
        "baseball_designated_hitter": 8,
    }
    df["pos_enc"] = df["position"].map(POS).fillna(-1).astype(int)
    df["is_sp"]   = (df["position"] == "baseball_starting_pitcher").astype(int)
    df["is_rp"]   = (df["position"] == "baseball_relief_pitcher").astype(int)
    df["age"]     = pd.to_numeric(df["age"], errors="coerce").fillna(28.0)

    print(f"  Shape : {df.shape}")
    return df


# ── 4. Feature sets ──────────────────────────────────────────────────────────

FEATURES_HIT = [
    "score_roll3","score_roll5","score_roll10","score_roll20",
    "score_std3","score_std5","score_std10",
    "score_lag1","score_lag2","score_lag3",
    "hr_r5","hr_r10",
    "rbi_r5","rbi_r10",
    "sb_r5","sb_r10",
    "hit_bb_r5","hit_bb_r10",
    "hit_so_r5","hit_so_r10",
    "s1_r5","s1_r10",
    "s2_r5","s2_r10",
    "run_r5","run_r10",
    "days_rest","games_played_log","season","month","age","pos_enc",
]

FEATURES_PIT = [
    "score_roll3","score_roll5","score_roll10","score_roll20",
    "score_std3","score_std5","score_std10",
    "score_lag1","score_lag2","score_lag3",
    "ip_r5","ip_r10",
    "pit_so_r5","pit_so_r10",
    "er_r5","er_r10",
    "ha_r5","ha_r10",
    "pit_bb_r5","pit_bb_r10",
    "era_r10","whip_r10","k9_r10",
    "win_r10","sav_r10","hld_r10",
    "days_rest","games_played_log","season","month","age","is_sp","is_rp",
]

LGBM_BASE = dict(
    n_estimators=800, learning_rate=0.02, num_leaves=63,
    min_child_samples=30, subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.05, reg_lambda=0.1, random_state=42,
    verbose=-1, n_jobs=-1,
)


# ── 5. Correlation check ─────────────────────────────────────────────────────

def check_correlations(X: pd.DataFrame, label: str, threshold=0.85):
    corr = X.corr().abs()
    cols = corr.columns.tolist()
    pairs = sorted([
        (cols[i], cols[j], float(corr.iloc[i,j]))
        for i in range(len(cols))
        for j in range(i+1, len(cols))
        if corr.iloc[i,j] >= threshold
    ], key=lambda x: -x[2])
    if pairs:
        print(f"  [Correlation {label}] {len(pairs)} paire(s) |r| >= {threshold} :")
        for a, b, c in pairs[:6]:
            print(f"    {a:28} / {b:28}  r={c:.3f}")
        print("  → Pour LightGBM : ne biaise pas les predictions, fragmente l'importance.")
    else:
        print(f"  [Correlation {label}] Aucune paire >= {threshold}")


# ── 6. Calibration conforme ───────────────────────────────────────────────────

def conformal_calibrate(models: dict, X_cal: pd.DataFrame,
                        y_cal: pd.Series, alpha: float = 0.20) -> float:
    """
    Calcule le facteur q_conf tel que [pred_lo - q_conf, pred_hi + q_conf]
    couvre >= 1-alpha des observations (garantie marginale).

    Ref : Angelopoulos & Bates (2021), "A Gentle Introduction to Conformal Prediction"
    """
    lo = models[0.10].predict(X_cal)
    hi = models[0.90].predict(X_cal)
    scores  = np.maximum(lo - y_cal.values, y_cal.values - hi)
    n       = len(scores)
    q_level = min(np.ceil((n + 1) * (1 - alpha)) / n, 1.0)
    return float(np.quantile(scores, q_level))


# ── 7. Entrainement ──────────────────────────────────────────────────────────

def train_group(df_group: pd.DataFrame, features: list, label: str):
    feats = [f for f in features if f in df_group.columns]
    df_g  = df_group.dropna(subset=["score_roll5","score_lag1"]).copy()
    print(f"\n  [{label}] {len(df_g):,} matchs avec historique")

    train = df_g[df_g["gw_int"] <= TRAIN_GW_MAX]
    val   = df_g[(df_g["gw_int"] > TRAIN_GW_MAX) & (df_g["gw_int"] <= VAL_GW_MAX)]
    test  = df_g[df_g["gw_int"] > VAL_GW_MAX]
    print(f"    Train: {len(train):,}  Val: {len(val):,}  Test: {len(test):,}")

    X_tr, y_tr = train[feats].fillna(0), train["score"]
    X_va, y_va = val[feats].fillna(0),   val["score"]
    X_te, y_te = test[feats].fillna(0),  test["score"]

    check_correlations(X_tr, label)

    cbs = [lgb.early_stopping(60, verbose=False), lgb.log_evaluation(-1)]

    models = {}
    for alpha in [0.10, 0.50, 0.90]:
        print(f"    q={alpha:.2f}...", end=" ", flush=True)
        m = lgb.LGBMRegressor(objective="quantile", alpha=alpha, **LGBM_BASE)
        m.fit(X_tr, y_tr, eval_set=[(X_va, y_va)],
              eval_metric="quantile", callbacks=cbs)
        models[alpha] = m
        print(f"iter={m.best_iteration_}")

    q_conf = conformal_calibrate(models, X_va, y_va, alpha=0.20)
    print(f"    q_conf (calibration conforme) = {q_conf:.2f}")

    lo_raw  = models[0.10].predict(X_te)
    med     = models[0.50].predict(X_te)
    hi_raw  = models[0.90].predict(X_te)
    lo_cal  = lo_raw - q_conf
    hi_cal  = hi_raw + q_conf

    mae          = mean_absolute_error(y_te, med)
    rmse         = float(np.sqrt(mean_squared_error(y_te, med)))
    base_mae     = mean_absolute_error(y_te, np.full(len(y_te), float(y_tr.mean())))
    cov_cal      = float(np.mean((y_te >= lo_cal) & (y_te <= hi_cal)))
    width_cal    = float(np.mean(hi_cal - lo_cal))

    print(f"\n  === Test [{label}] (GW > {VAL_GW_MAX}) ===")
    print(f"    MAE   : {mae:.2f}  |  RMSE : {rmse:.2f}")
    print(f"    Base  : {base_mae:.2f}  |  Gain : {(1-mae/base_mae)*100:.1f}%")
    print(f"    PI 80%: couverture={cov_cal:.1%}  largeur={width_cal:.1f} pts")

    imp = pd.Series(models[0.50].feature_importances_,
                    index=feats).sort_values(ascending=False).head(12)
    print(f"  Top features :")
    for f, v in imp.items():
        bar = "#" * int(v / imp.max() * 20)
        print(f"    {f:<28} {bar}")

    return models, feats, q_conf, {
        "mae": mae, "rmse": rmse, "base_mae": base_mae,
        "cov_cal": cov_cal, "width_cal": width_cal,
    }


# ── 8. Sauvegarde ────────────────────────────────────────────────────────────

def save_artifact(models: dict, feats: list, q_conf: float, label: str):
    slug = label.lower().replace(" ", "_")
    payload = {"models": models, "features": feats, "q_conf": q_conf, "label": label}
    path = MODELS_DIR / f"lgbm_{slug}.pkl"
    with open(path, "wb") as f:
        pickle.dump(payload, f)
    print(f"  Sauvegarde : {path}")
    return path


def load_artifact(label: str) -> dict:
    slug = label.lower().replace(" ", "_")
    path = MODELS_DIR / f"lgbm_{slug}.pkl"
    with open(path, "rb") as f:
        return pickle.load(f)


# ── 9. Feature engineering pour l'inference (sans fuite) ─────────────────────

def compute_inference_features(history: pd.DataFrame,
                                age: float,
                                position: str,
                                next_game_date: pd.Timestamp) -> dict:
    """
    Calcule les features pour predire le PROCHAIN match d'un joueur.

    history : DataFrame tri par game_date avec colonnes score + stats individuelles
              (ne doit contenir QUE les matchs deja joues)
    """
    if history.empty:
        return {}

    h = history.sort_values("game_date").copy()
    scores = h["score"].values.astype(float)
    n = len(scores)

    def roll_mean(arr, w):
        if n == 0:
            return 0.0
        window = arr[-w:] if n >= w else arr
        return float(np.mean(window)) if len(window) > 0 else 0.0

    def roll_std(arr, w):
        window = arr[-w:] if n >= w else arr
        return float(np.std(window, ddof=1)) if len(window) >= 2 else 0.0

    feat = {}

    # Score rolling (sur les derniers matchs reels)
    for w in [3, 5, 10, 20]:
        feat[f"score_roll{w}"] = roll_mean(scores, w)
    for w in [3, 5, 10]:
        feat[f"score_std{w}"]  = roll_std(scores, w)
    for lag in [1, 2, 3]:
        feat[f"score_lag{lag}"] = float(scores[-lag]) if n >= lag else 0.0

    # Stats individuelles rolling
    for col in ["hr","rbi","sb","hit_bb","hit_so","s1","s2","run",
                "ip","pit_so","er","ha","pit_bb"]:
        if col in h.columns:
            vals = h[col].fillna(0).values.astype(float)
            for w in [5, 10]:
                feat[f"{col}_r{w}"] = roll_mean(vals, w)
        else:
            for w in [5, 10]:
                feat[f"{col}_r{w}"] = 0.0

    for col in ["win","sav","hld"]:
        if col in h.columns:
            vals = h[col].fillna(0).values.astype(float)
            feat[f"{col}_r10"] = roll_mean(vals, 10)
        else:
            feat[f"{col}_r10"] = 0.0

    # Ratios pitching composites
    ip10 = feat["ip_r10"] if feat["ip_r10"] > 0 else np.nan
    feat["era_r10"]  = feat["er_r10"]                              / ip10 * 9  if ip10 else 0.0
    feat["whip_r10"] = (feat["pit_bb_r10"] + feat["ha_r10"])       / ip10       if ip10 else 0.0
    feat["k9_r10"]   = feat["pit_so_r10"]                          / ip10 * 9  if ip10 else 0.0

    # Repos
    last_date  = pd.to_datetime(h["game_date"].iloc[-1], utc=True)
    next_ts    = pd.to_datetime(next_game_date, utc=True)
    days_rest  = max(1, min(15, (next_ts - last_date).days))
    feat["days_rest"] = float(days_rest)

    # Experience
    feat["games_played_log"] = float(np.log1p(n))

    # Temporel
    feat["season"] = float(next_ts.year)
    feat["month"]  = float(next_ts.month)

    # Position
    POS = {
        "baseball_starting_pitcher": 0, "baseball_relief_pitcher": 1,
        "baseball_outfield": 2,         "baseball_first_base": 3,
        "baseball_second_base": 4,      "baseball_third_base": 5,
        "baseball_shortstop": 6,        "baseball_catcher": 7,
        "baseball_designated_hitter": 8,
    }
    feat["pos_enc"] = float(POS.get(position, -1))
    feat["is_sp"]   = 1.0 if position == "baseball_starting_pitcher" else 0.0
    feat["is_rp"]   = 1.0 if position == "baseball_relief_pitcher"   else 0.0
    feat["age"]     = float(age) if age and not np.isnan(age) else 28.0

    return feat


def predict_next_game(history: pd.DataFrame, age: float, position: str,
                      next_game_date: pd.Timestamp) -> dict | None:
    """
    Retourne {'pred_median', 'pred_lo', 'pred_hi'} ou None si pas d'historique.
    """
    is_pitcher = "pitcher" in position if position else False
    label      = "pitchers" if is_pitcher else "hitters"

    try:
        art = load_artifact(label)
    except FileNotFoundError:
        return None

    feat = compute_inference_features(history, age, position, next_game_date)
    if not feat:
        return None

    row = pd.DataFrame([feat])[art["features"]].fillna(0)

    lo  = float(art["models"][0.10].predict(row)[0]) - art["q_conf"]
    med = float(art["models"][0.50].predict(row)[0])
    hi  = float(art["models"][0.90].predict(row)[0]) + art["q_conf"]

    return {
        "pred_median": round(med, 1),
        "pred_lo":     round(lo,  1),
        "pred_hi":     round(hi,  1),
    }


# ── Main : entrainement ──────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = create_engine(DB_URL)

    gs, gsd, players = load_raw_data(engine)
    df = build_wide(gs, gsd, players)
    df = engineer_features(df)

    print("\n[4/5] Entrainement...")

    # Hitters
    df_hit = df[~df["position"].str.contains("pitcher", na=False)].copy()
    m_h, f_h, qc_h, met_h = train_group(df_hit, FEATURES_HIT, "hitters")
    save_artifact(m_h, f_h, qc_h, "hitters")

    # Pitchers (SP + RP fusionnes — is_sp comme feature discriminante)
    df_pit = df[df["position"].str.contains("pitcher", na=False)].copy()
    m_p, f_p, qc_p, met_p = train_group(df_pit, FEATURES_PIT, "pitchers")
    save_artifact(m_p, f_p, qc_p, "pitchers")

    print("\n[5/5] Resume")
    hdr = f"{'Groupe':<12} {'MAE':>5} {'RMSE':>5} {'Base':>5} {'Gain':>5} {'Cov.80%':>8} {'Larg.PI':>8}"
    print(hdr)
    print("-" * len(hdr))
    for lbl, m in [("Hitters", met_h), ("Pitchers", met_p)]:
        print(
            f"{lbl:<12} {m['mae']:>5.2f} {m['rmse']:>5.2f} {m['base_mae']:>5.2f}"
            f" {(1-m['mae']/m['base_mae'])*100:>4.1f}%"
            f" {m['cov_cal']:>7.1%} {m['width_cal']:>8.1f}"
        )
    print("\nModeles sauvegardes dans models/")
