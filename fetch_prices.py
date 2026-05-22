"""
fetch_prices.py
---------------
Récupère le prix de marché le plus bas par (joueur, rareté, inSeason)
et alimente mlb.card_prices.

Cible : joueurs uniques présents dans mlb.gallery_players.
Long à exécuter (4 raretés × 2 inSeason = 8 appels API par joueur).

Usage :
    python fetch_prices.py
"""

import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SORARE_API = "https://api.sorare.com/graphql"

RARITIES   = ["limited", "rare", "super_rare", "unique"]
IN_SEASONS = [True, False]

# Taux de change de secours (utilisés si les APIs externes échouent)
_FX_FALLBACK = {"usd": 0.87, "gbp": 1.15, "eth": 1774.62}


def _load_fx_rates() -> dict:
    """
    Récupère les taux de change live vers EUR.
    - frankfurter.app (BCE) pour USD et GBP
    - CoinGecko pour ETH
    Retourne le fallback statique en cas d'échec.
    """
    rates = dict(_FX_FALLBACK)

    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "EUR", "to": "USD,GBP"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()["rates"]
        # frankfurter donne EUR→devise, on inverse pour avoir devise→EUR
        rates["usd"] = round(1 / data["USD"], 6)
        rates["gbp"] = round(1 / data["GBP"], 6)
        print(f"  Taux Frankfurter : 1 USD = {rates['usd']:.4f} EUR | 1 GBP = {rates['gbp']:.4f} EUR")
    except Exception as exc:
        print(f"  Frankfurter indisponible ({exc}), taux USD/GBP statiques utilisés")

    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum", "vs_currencies": "eur"},
            timeout=10,
        )
        resp.raise_for_status()
        rates["eth"] = resp.json()["ethereum"]["eur"]
        print(f"  Taux CoinGecko : 1 ETH = {rates['eth']:.2f} EUR")
    except Exception as exc:
        print(f"  CoinGecko indisponible ({exc}), taux ETH statique utilisé")

    return rates


# ── Helpers ────────────────────────────────────────────────────────────────────

def _api_post(payload: dict, headers: dict, timeout: int = 30, max_retries: int = 6) -> dict:
    for attempt in range(max_retries):
        try:
            resp = requests.post(SORARE_API, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 429:
                wait = 30 * (2 ** min(attempt, 3))
                print(f"    429 rate-limit, attente {wait}s...")
                time.sleep(wait)
                continue
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
    return engine, api_headers


def _to_eur(amounts: dict | None, fx: dict) -> float | None:
    if not amounts:
        return None
    if amounts.get("eurCents"):
        return amounts["eurCents"] / 100
    if amounts.get("usdCents"):
        return amounts["usdCents"] / 100 * fx["usd"]
    if amounts.get("gbpCents"):
        return amounts["gbpCents"] / 100 * fx["gbp"]
    if amounts.get("wei"):
        try:
            return int(amounts["wei"]) / 1e18 * fx["eth"]
        except (ValueError, TypeError):
            return None
    return None


def _extract_price(card: dict | None, fx: dict) -> float | None:
    if not card:
        return None
    try:
        amounts = card["liveSingleSaleOffer"]["receiverSide"]["amounts"]
        price = _to_eur(amounts, fx)
        if price is not None:
            return price
    except (KeyError, TypeError):
        pass
    try:
        amounts = card["latestPrimaryOffer"]["price"]
        return _to_eur(amounts, fx)
    except (KeyError, TypeError):
        return None


# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch_prices_for_player(slug: str, headers: dict, fx: dict) -> list[dict]:
    rows = []
    for rarity in RARITIES:
        for in_season in IN_SEASONS:
            in_season_str = "true" if in_season else "false"
            query = f"""{{
              anyPlayer(slug: "{slug}") {{
                ... on BaseballPlayer {{
                  lowestPriceAnyCard(inSeason: {in_season_str} rarity: {rarity}) {{
                    sealableFor
                    liveSingleSaleOffer {{
                      receiverSide {{
                        amounts {{
                          eurCents
                          gbpCents
                          usdCents
                          wei
                        }}
                      }}
                    }}
                    latestPrimaryOffer {{
                      price {{
                        eurCents
                        gbpCents
                        usdCents
                        wei
                      }}
                    }}
                  }}
                }}
              }}
            }}"""

            data = _api_post({"query": query}, headers)
            player_data = data["data"]["anyPlayer"]
            card = player_data.get("lowestPriceAnyCard") if player_data else None
            price = _extract_price(card, fx)
            sealable_for = card.get("sealableFor") if card else None

            rows.append({
                "player_slug": slug,
                "rarity":      rarity,
                "in_season":   in_season,
                "price_eur":   price,
                "sealable_for": sealable_for,
            })

    return rows


# ── Store ──────────────────────────────────────────────────────────────────────

def store_prices(engine, all_rows: list) -> None:
    if not all_rows:
        print("  Aucune donnée à enregistrer.")
        return

    slugs = list({r["player_slug"] for r in all_rows})
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM mlb.card_prices WHERE player_slug = ANY(:slugs)"
        ), {"slugs": slugs})

    df = pd.DataFrame(all_rows)
    df.to_sql("card_prices", engine, schema="mlb", if_exists="append", index=False)
    print(f"  {len(df)} lignes enregistrées dans mlb.card_prices")
    n_with_price = df["price_eur"].notna().sum()
    print(f"  ({n_with_price} avec prix, {len(df) - n_with_price} sans marché)")


# ── Main ───────────────────────────────────────────────────────────────────────

def get_gallery_slugs(engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT player_slug FROM mlb.gallery_players WHERE NOT sealed"
        )).fetchall()
    return [r[0] for r in rows]


if __name__ == "__main__":
    engine, api_headers = _load_config()

    player_slugs = get_gallery_slugs(engine)
    total = len(player_slugs)
    print(f"Récupération des prix pour {total} joueurs ({total * 8} appels API)...")

    print("Chargement des taux de change...")
    fx = _load_fx_rates()

    all_rows = []
    for i, slug in enumerate(player_slugs):
        remaining = total - (i + 1)
        print(f"  [{i+1}/{total}] {slug} ({remaining} restants)")
        all_rows.extend(fetch_prices_for_player(slug, api_headers, fx))

    print("Enregistrement en base...")
    store_prices(engine, all_rows)
    print("Terminé !")
