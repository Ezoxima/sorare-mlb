"""
fetch_weather.py
----------------
Récupère les données météo pour les matchs MLB via Open-Meteo (gratuit, sans clé).

Stratégie :
  - API forecast (api.open-meteo.com) avec past_days pour couvrir passé + futur.
  - 1 appel par stade (groupement par home_team_slug) → max 30 appels/run.
  - Upsert dans mlb.game_weather ; les prévisions sont rafraîchies à chaque run.

Labels vent (wind_label) — calculés depuis cf_orientation_deg + wind_dir_deg :
  out      : vent poussant de home vers CF  → booste les HRs
  in       : vent venant de CF vers home    → supprime les HRs
  cross_R  : vent latéral côté RF
  cross_L  : vent latéral côté LF
  calm     : < 5 mph
  dome     : stade fermé (is_dome = true)

Usage :
    python fetch_weather.py           # 7 jours passés + 16 jours futurs
    python fetch_weather.py --full    # 30 jours passés + 16 jours futurs
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, Table, MetaData, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

FORECAST_URL        = "https://api.open-meteo.com/v1/forecast"
SLEEP_BETWEEN_CALLS = 0.4   # politesse envers Open-Meteo

HOURLY_VARS = (
    "temperature_2m,relative_humidity_2m,"
    "wind_speed_10m,wind_direction_10m,"
    "precipitation,cloud_cover"
)

NOW_UTC = datetime.now(timezone.utc)


# ── Config ─────────────────────────────────────────────────────────────────────

def _load_config():
    load_dotenv(Path(__file__).parent.parent / ".env")
    return create_engine(
        f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )


# ── Calcul labels ──────────────────────────────────────────────────────────────

def _wind_label(speed_mph: float, wind_dir: int, cf_deg: int | None, is_dome: bool) -> str:
    if is_dome:
        return "dome"
    if speed_mph < 5 or cf_deg is None:
        return "calm"
    # Angle relatif : wind_dir par rapport à la direction home→CF
    # 0° = vent venant de CF (in), 180° = vent de dos (out)
    rel = (wind_dir - cf_deg) % 360
    if rel <= 45 or rel >= 315:
        return "in"
    elif 135 <= rel <= 225:
        return "out"
    elif 45 < rel < 135:
        return "cross_R"
    else:
        return "cross_L"


def _condition(precip_mm: float, cloud_pct: float, is_dome: bool) -> str:
    if is_dome:
        return "dome"
    if precip_mm > 1.0:
        return "rain"
    if cloud_pct > 75:
        return "cloudy"
    return "clear"


# ── Requête Open-Meteo ─────────────────────────────────────────────────────────

def _fetch_hourly(lat: float, lon: float, past_days: int, forecast_days: int = 16) -> pd.DataFrame:
    params = {
        "latitude":         lat,
        "longitude":        lon,
        "hourly":           HOURLY_VARS,
        "wind_speed_unit":  "mph",
        "temperature_unit": "fahrenheit",
        "timezone":         "UTC",
        "past_days":        past_days,
        "forecast_days":    forecast_days,
    }
    try:
        r = requests.get(FORECAST_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        print(f"    Erreur Open-Meteo ({lat:.3f},{lon:.3f}): {exc}")
        return pd.DataFrame()

    h = data.get("hourly", {})
    times = h.get("time", [])
    if not times:
        return pd.DataFrame()

    df = pd.DataFrame({
        "hour_utc":   pd.to_datetime(times, utc=True),
        "temp_f":     h.get("temperature_2m", [None] * len(times)),
        "humidity":   h.get("relative_humidity_2m", [None] * len(times)),
        "wind_speed": h.get("wind_speed_10m", [None] * len(times)),
        "wind_dir":   h.get("wind_direction_10m", [None] * len(times)),
        "precip":     h.get("precipitation", [None] * len(times)),
        "cloud":      h.get("cloud_cover", [None] * len(times)),
    })
    return df.set_index("hour_utc")


def _match_hour(hourly: pd.DataFrame, game_dt: datetime) -> pd.Series | None:
    """Ligne météo la plus proche de game_dt (fenêtre ±3h)."""
    if hourly.empty:
        return None
    pivot = game_dt.replace(minute=0, second=0, microsecond=0)
    window = hourly.loc[
        (hourly.index >= pivot - pd.Timedelta(hours=3)) &
        (hourly.index <= pivot + pd.Timedelta(hours=3))
    ]
    if window.empty:
        return None
    diffs = [(idx - pivot).total_seconds() for idx in window.index]
    return window.iloc[int(pd.Series(diffs).abs().argmin())]


# ── Pipeline ───────────────────────────────────────────────────────────────────

def run(engine, full_mode: bool = False):
    past_days = 30 if full_mode else 7

    # 1. Matchs dans la fenêtre avec coordonnées de stade
    with engine.connect() as conn:
        games = pd.read_sql(text("""
            SELECT g.game_id,
                   g.game_date,
                   g.home_team_slug,
                   s.latitude,
                   s.longitude,
                   s.cf_orientation_deg,
                   s.is_dome,
                   w.game_id      AS w_game_id,
                   w.is_forecast  AS w_is_forecast
            FROM mlb.games g
            JOIN mlb.stadiums s ON g.home_team_slug = s.team_slug
            LEFT JOIN mlb.game_weather w ON g.game_id = w.game_id
            WHERE g.game_date >= NOW() - make_interval(days => :past)
              AND g.game_date <= NOW() + INTERVAL '16 days'
        """), conn, params={"past": past_days})

    if games.empty:
        print("  Aucun match dans la fenêtre.")
        return

    # Traiter : pas de météo OU prévision à rafraîchir
    to_process = games[
        games["w_game_id"].isna() |
        games["w_is_forecast"].eq(True)
    ].copy()

    total_games = len(games)
    print(f"  {len(to_process)} matchs à mettre à jour (fenêtre : {total_games} matchs)")

    if to_process.empty:
        print("  Tout est déjà à jour.")
        return

    # 2. Un appel API par stade (groupement par home_team_slug)
    results = []
    grouped = to_process.groupby("home_team_slug")

    for team_slug, grp in grouped:
        row0    = grp.iloc[0]
        lat     = float(row0["latitude"])
        lon     = float(row0["longitude"])
        cf_deg  = int(row0["cf_orientation_deg"]) if pd.notna(row0["cf_orientation_deg"]) else None
        is_dome = bool(row0["is_dome"])

        hourly = _fetch_hourly(lat, lon, past_days=past_days)
        time.sleep(SLEEP_BETWEEN_CALLS)

        n_ok = 0
        for _, game in grp.iterrows():
            row_w = _match_hour(hourly, game["game_date"])
            if row_w is None:
                continue

            speed_mph = float(row_w["wind_speed"] or 0)
            wind_dir  = int(row_w["wind_dir"] or 0)
            precip    = float(row_w["precip"] or 0)
            cloud     = float(row_w["cloud"] or 0)

            results.append({
                "game_id":        game["game_id"],
                "temperature_f":  round(float(row_w["temp_f"]), 1) if pd.notna(row_w["temp_f"]) else None,
                "humidity_pct":   round(float(row_w["humidity"]), 1) if pd.notna(row_w["humidity"]) else None,
                "wind_speed_mph": round(speed_mph, 1),
                "wind_dir_deg":   wind_dir,
                "wind_label":     _wind_label(speed_mph, wind_dir, cf_deg, is_dome),
                "precip_mm":      round(precip, 2),
                "condition":      _condition(precip, cloud, is_dome),
                "is_forecast":    game["game_date"] > NOW_UTC,
            })
            n_ok += 1

        print(f"  {team_slug}: {n_ok}/{len(grp)} matchs", flush=True)

    if not results:
        print("  Aucune donnée récupérée.")
        return

    # 3. Upsert dans mlb.game_weather
    meta = MetaData()
    meta.reflect(bind=engine, schema="mlb", only=["game_weather"])
    tbl = meta.tables["mlb.game_weather"]

    with engine.begin() as conn:
        for rec in results:
            stmt = (
                pg_insert(tbl)
                .values(**rec)
                .on_conflict_do_update(
                    index_elements=["game_id"],
                    set_={k: getattr(pg_insert(tbl).excluded, k) for k in rec if k != "game_id"},
                )
            )
            conn.execute(stmt)

    # Résumé
    df_res = pd.DataFrame(results)
    n_hist = df_res["is_forecast"].eq(False).sum()
    n_fore = df_res["is_forecast"].eq(True).sum()
    print(f"\n  {len(results)} entrées upsertées ({n_hist} historiques, {n_fore} prévisions)")

    print("\nDistribution wind_label :")
    print(df_res["wind_label"].value_counts().to_string())
    print("\nDistribution condition :")
    print(df_res["condition"].value_counts().to_string())
    print("\nTempérature (°F) — min/moy/max :")
    temps = df_res["temperature_f"].dropna()
    if not temps.empty:
        print(f"  {temps.min():.1f} / {temps.mean():.1f} / {temps.max():.1f}")


if __name__ == "__main__":
    full_mode = "--full" in sys.argv
    window    = "30 jours passés + 16 jours futurs" if full_mode else "7 jours passés + 16 jours futurs"
    print(f"[Weather] Météo MLB ({window})...")
    engine = _load_config()
    run(engine, full_mode=full_mode)
