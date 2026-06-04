"""
Récupère l'historique d'achats de cartes via user.trades.
Prix avant déduction des crédits marketplace.
"""

import time

import pandas as pd
import requests
from sqlalchemy import text

SORARE_API = "https://api.sorare.com/graphql"
SLEEP      = 0.3

_QUERY = """\
{{
  user(slug: "{slug}") {{
    trades(after: "{cursor}" sport: BASEBALL sortByEndDate: DESC) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        __typename
        ... on TokenPrimaryOffer {{
          id
          transactionDate
          anyCards {{ slug }}
          price {{ eurCents usdCents gbpCents }}
        }}
        ... on TokenAuction {{
          id
          transactionDate
          anyCards {{ slug }}
          userBuyer  {{ slug }}
          userSeller {{ slug }}
          bestBid {{ amounts {{ eurCents usdCents gbpCents }} }}
        }}
        ... on TokenOffer {{
          id
          transactionDate
          sender {{ ... on User {{ slug }} }}
          senderSide   {{ anyCards {{ slug }} }}
          receiverSide {{ amounts {{ eurCents usdCents gbpCents }} }}
        }}
      }}
    }}
  }}
}}"""


def _api_call(query: str, headers: dict) -> dict:
    resp = requests.post(SORARE_API, json={"query": query}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL : {data['errors']}")
    return data


def fetch_trades(manager_slug: str, headers: dict) -> list[dict]:
    rows   = []
    cursor = ""
    page   = 0

    while True:
        data      = _api_call(_QUERY.format(slug=manager_slug, cursor=cursor), headers)
        trades    = data["data"]["user"]["trades"]
        nodes     = trades["nodes"]
        page_info = trades["pageInfo"]
        page += 1
        print(f"    page {page} ({len(nodes)} trades)")

        for node in nodes:
            typename = node["__typename"]

            if typename == "TokenPrimaryOffer":
                _price    = node.get("price") or {}
                eur_cents = _price.get("eurCents")
                usd_cents = _price.get("usdCents")
                gbp_cents = _price.get("gbpCents")
                for card in node.get("anyCards", []):
                    rows.append({
                        "card_slug":        card["slug"],
                        "manager_slug":     manager_slug,
                        "deal_id":          node["id"],
                        "deal_type":        "primary",
                        "transaction_date": node.get("transactionDate"),
                        "price_eur_cents":  eur_cents,
                        "price_usd_cents":  usd_cents,
                        "price_gbp_cents":  gbp_cents,
                    })

            elif typename == "TokenAuction":
                user_buyer  = (node.get("userBuyer")  or {}).get("slug", "")
                user_seller = (node.get("userSeller") or {}).get("slug", "")
                if user_seller == manager_slug:
                    continue  # vente, pas achat
                if user_buyer and user_buyer != manager_slug:
                    continue  # achat d'un autre
                _amounts  = (node.get("bestBid") or {}).get("amounts") or {}
                eur_cents = _amounts.get("eurCents")
                usd_cents = _amounts.get("usdCents")
                gbp_cents = _amounts.get("gbpCents")
                for card in node.get("anyCards", []):
                    rows.append({
                        "card_slug":        card["slug"],
                        "manager_slug":     manager_slug,
                        "deal_id":          node["id"],
                        "deal_type":        "auction",
                        "transaction_date": node.get("transactionDate"),
                        "price_eur_cents":  eur_cents,
                        "price_usd_cents":  usd_cents,
                        "price_gbp_cents":  gbp_cents,
                    })

            elif typename == "TokenOffer":
                sender_slug = (node.get("sender") or {}).get("slug", "")
                if sender_slug == manager_slug:
                    cards_skipped = [(c["slug"]) for c in (node.get("senderSide") or {}).get("anyCards", [])]
                    if cards_skipped:
                        print(f"    [SKIP vente] {node['id']} cards={cards_skipped}")
                    continue  # vente
                _amounts  = (node.get("receiverSide") or {}).get("amounts") or {}
                eur_cents = _amounts.get("eurCents")
                usd_cents = _amounts.get("usdCents")
                gbp_cents = _amounts.get("gbpCents")
                for card in (node.get("senderSide") or {}).get("anyCards", []):
                    rows.append({
                        "card_slug":        card["slug"],
                        "manager_slug":     manager_slug,
                        "deal_id":          node["id"],
                        "deal_type":        "offer",
                        "transaction_date": node.get("transactionDate"),
                        "price_eur_cents":  eur_cents,
                        "price_usd_cents":  usd_cents,
                        "price_gbp_cents":  gbp_cents,
                    })

            else:
                print(f"    [UNKNOWN typename] {typename} id={node.get('id')}")

        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]
        time.sleep(SLEEP)

    return rows


def store_trades(engine, rows: list[dict], manager_slug: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mlb.card_purchase_prices (
                card_slug        TEXT        NOT NULL,
                manager_slug     TEXT        NOT NULL,
                deal_id          TEXT,
                deal_type        TEXT,
                transaction_date TIMESTAMPTZ,
                price_eur_cents  INTEGER,
                price_usd_cents  INTEGER,
                price_gbp_cents  INTEGER,
                PRIMARY KEY (card_slug, manager_slug)
            )
        """))
        conn.execute(text("""
            ALTER TABLE mlb.card_purchase_prices
            ADD COLUMN IF NOT EXISTS price_usd_cents INTEGER
        """))
        conn.execute(text("""
            ALTER TABLE mlb.card_purchase_prices
            ADD COLUMN IF NOT EXISTS price_gbp_cents INTEGER
        """))

    if not rows:
        print("  Aucune transaction à stocker.")
        return

    # Dédoublonnage : garder le trade le plus récent par carte
    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], utc=True, errors="coerce")
    df = (
        df.sort_values("transaction_date", ascending=False, na_position="last")
        .drop_duplicates(subset=["card_slug", "manager_slug"])
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM mlb.card_purchase_prices WHERE manager_slug = :slug"),
            {"slug": manager_slug},
        )
        for _, row in df.iterrows():
            params = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
            conn.execute(text("""
                INSERT INTO mlb.card_purchase_prices
                    (card_slug, manager_slug, deal_id, deal_type, transaction_date, price_eur_cents, price_usd_cents, price_gbp_cents)
                VALUES
                    (:card_slug, :manager_slug, :deal_id, :deal_type, :transaction_date, :price_eur_cents, :price_usd_cents, :price_gbp_cents)
                ON CONFLICT DO NOTHING
            """), params)

    print(f"  {len(df)} transactions dans mlb.card_purchase_prices")
