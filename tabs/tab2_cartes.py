import json
import streamlit as st
import pandas as pd
import requests
from pathlib import Path

from data_loaders import RARITY_ORDER

_REMISES_PATH = Path(__file__).parent.parent / "data" / "remises.json"


def load_remises() -> dict:
    try:
        return json.loads(_REMISES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_remises(remises: dict) -> None:
    _REMISES_PATH.write_text(
        json.dumps(remises, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@st.cache_data(ttl=3600)
def _load_fx() -> dict:
    rates = {"eur_to_usd": 1.08, "usd_to_eur": 0.926, "eth_to_eur": 2400.0}
    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "EUR", "to": "USD"},
            timeout=8,
        )
        resp.raise_for_status()
        eur_to_usd = resp.json()["rates"]["USD"]
        rates["eur_to_usd"] = eur_to_usd
        rates["usd_to_eur"] = round(1 / eur_to_usd, 6)
    except Exception:
        pass
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum", "vs_currencies": "eur"},
            timeout=8,
        )
        resp.raise_for_status()
        rates["eth_to_eur"] = resp.json()["ethereum"]["eur"]
    except Exception:
        pass
    return rates


def _get(row, col) -> float | None:
    v = row.get(col)
    return float(v) if v is not None and pd.notna(v) else None


def _price_eur(row, eur_col: str, usd_col: str, wei_col: str, fx: dict) -> float | None:
    """Un prix unique converti en EUR — priorité EUR, fallback USD, fallback wei."""
    v = _get(row, eur_col)
    if v is not None:
        return v / 100
    v = _get(row, usd_col)
    if v is not None:
        return v * fx["usd_to_eur"] / 100
    v = _get(row, wei_col)
    if v is not None:
        return v / 1e18 * fx["eth_to_eur"]
    return None


def _min_price_eur(row, eur_sale: str, usd_sale: str, wei_sale: str,
                   eur_primary: str, usd_primary: str, wei_primary: str,
                   fx: dict) -> float | None:
    """Minimum entre sale et primary, chacun converti en EUR (EUR > USD > wei)."""
    candidates = [
        _price_eur(row, eur_sale,    usd_sale,    wei_sale,    fx),
        _price_eur(row, eur_primary, usd_primary, wei_primary, fx),
    ]
    valid = [v for v in candidates if v is not None]
    return min(valid) if valid else None


def _market_is_result(row, fx: dict) -> tuple[float | None, bool]:
    """Prix IS en EUR : primary divisé par 2 (crédits marché Sorare 50%).
    Retourne (prix_eur, from_primary)."""
    sale     = _price_eur(row, "lpc_sale_eur_cents",    "lpc_sale_usd_cents",    "lpc_sale_wei",    fx)
    prim_raw = _price_eur(row, "lpc_primary_eur_cents", "lpc_primary_usd_cents", "lpc_primary_wei", fx)
    prim     = prim_raw / 2 if prim_raw is not None else None

    if sale is None and prim is None:
        return None, False
    if sale is None:
        return prim, True
    if prim is None:
        return sale, False
    if prim < sale:
        return prim, True
    return sale, False


def _to_eur(row, eur_cols: list, usd_cols: list, usd_to_eur: float) -> float | None:
    """Premier champ non-null parmi eur_cols, fallback usd_cols converti (pour achat)."""
    for c in eur_cols:
        v = _get(row, c)
        if v is not None:
            return v / 100
    for c in usd_cols:
        v = _get(row, c)
        if v is not None:
            return v * usd_to_eur / 100
    return None


def render(ctx: dict) -> None:
    df_prices   = ctx["df_prices"]
    sel_manager = ctx["sel_manager"]

    df_p = df_prices[df_prices["gallery_manager"] == sel_manager].copy()

    if df_p.empty:
        st.info("Aucune carte trouvée.")
        return

    fx = _load_fx()

    # ── Sélecteur de devise ────────────────────────────────────────────────────
    devise  = st.radio("Devise", ["€ EUR", "$ USD"], horizontal=True, key="tab2_devise")
    use_usd = devise == "$ USD"
    sym     = "$" if use_usd else "€"
    rate    = fx["eur_to_usd"] if use_usd else 1.0
    price_fmt = "%.2f $" if use_usd else "%.2f €"

    # ── Normalisation AVANT tri ────────────────────────────────────────────────
    if "owner_since" in df_p.columns:
        df_p["owner_since"] = pd.to_datetime(df_p["owner_since"], utc=True, errors="coerce")

    # Clés de tri en EUR (stables quelle que soit la devise affichée)
    lpc_present = bool({"lpc_sale_eur_cents", "lpc_sale_usd_cents",
                        "lpca_sale_eur_cents", "lpca_sale_usd_cents"} & set(df_p.columns))

    if lpc_present:
        def _market_row(row):
            if row.get("in_season_eligible"):
                return _market_is_result(row, fx)  # (prix_eur, from_primary)
            else:
                candidates = [
                    _min_price_eur(row,
                        "lpc_sale_eur_cents",  "lpc_sale_usd_cents",  "lpc_sale_wei",
                        "lpc_primary_eur_cents", "lpc_primary_usd_cents", "lpc_primary_wei",
                        fx),
                    _min_price_eur(row,
                        "lpca_sale_eur_cents",  "lpca_sale_usd_cents",  "lpca_sale_wei",
                        "lpca_primary_eur_cents", "lpca_primary_usd_cents", "lpca_primary_wei",
                        fx),
                ]
                valid = [v for v in candidates if v is not None]
                return (min(valid) if valid else None), False

        _results = df_p.apply(_market_row, axis=1)
        df_p["_market_sort"]    = _results.apply(lambda x: x[0])
        df_p["_market_primary"] = _results.apply(lambda x: x[1])
    else:
        df_p["_market_sort"]    = None
        df_p["_market_primary"] = False

    eur_col = "purchase_eur_cents" if "purchase_eur_cents" in df_p.columns else None
    usd_col = "purchase_usd_cents" if "purchase_usd_cents" in df_p.columns else None
    gbp_col = "purchase_gbp_cents" if "purchase_gbp_cents" in df_p.columns else None
    if eur_col or usd_col or gbp_col:
        df_p["_purchase_sort"] = df_p.apply(
            lambda r: _to_eur(r,
                [eur_col] if eur_col else [],
                [usd_col] if usd_col else [],
                fx["usd_to_eur"]) or (
                _get(r, gbp_col) * fx.get("gbp_to_eur", 0.926) / 100
                if gbp_col and _get(r, gbp_col) is not None else None
            ),
            axis=1
        )
    else:
        df_p["_purchase_sort"] = pd.to_numeric(df_p.get("purchase_price_eur"), errors="coerce")

    # ── Origine d'acquisition ─────────────────────────────────────────────────
    if "transfer_type" in df_p.columns:
        df_p["origine"] = df_p["transfer_type"].apply(
            lambda t: "🏆 Gagnée" if t in ("REWARD", "SHARDS") else ("🛒 Achetée" if pd.notna(t) else None)
        )
    else:
        df_p["origine"] = None

    # ── Δ Marché (clé de tri en EUR, stable) ──────────────────────────────────
    df_p["_diff_sort"] = df_p["_market_sort"] - df_p["_purchase_sort"]

    # ── Métriques ─────────────────────────────────────────────────────────────
    val_is   = df_p["price_in_season"].sum()
    val_oos  = df_p["price_out_season"].sum()
    n_priced = df_p["price_in_season"].notna().sum()
    total_purchase = df_p["_purchase_sort"].sum() if df_p["_purchase_sort"].notna().any() else None

    metrics_html = (
        f'<div class="metrics">'
        f'<div class="metric"><div class="k">Cartes</div><div class="v">{len(df_p)}</div></div>'
        f'<div class="metric"><div class="k">Avec prix</div><div class="v">{int(n_priced)}</div></div>'
        f'<div class="metric"><div class="k">Valeur IS</div><div class="v pos">{val_is:.0f} €</div></div>'
        f'<div class="metric"><div class="k">Valeur Classic</div><div class="v" style="color:var(--fg-2)">{val_oos:.0f} €</div></div>'
    )
    if total_purchase is not None:
        display_total = total_purchase * rate
        metrics_html += (
            f'<div class="metric"><div class="k">Coût total</div>'
            f'<div class="v" style="color:var(--fg-2)">{display_total:.0f} {sym}</div></div>'
        )
    metrics_html += '</div>'
    st.markdown(metrics_html, unsafe_allow_html=True)

    st.divider()

    # ── Filtres ────────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        raretés_filtre = sorted(df_p["card_display_rarity"].dropna().unique(),
                                key=lambda r: RARITY_ORDER.get(r.lower() if r else "", 99))
        sel_rar_p = st.multiselect("Rareté", raretés_filtre, default=raretés_filtre, key="rar_prices")
    with col_f2:
        positions_filtre = sorted(df_p["position_agg"].dropna().unique())
        sel_pos_p = st.multiselect("Poste", positions_filtre, default=positions_filtre, key="pos_prices")
    with col_f3:
        tri_options = {
            "Obtenue le desc":   ("owner_since",     False),
            "Power desc":        ("card_power",       False),
            "Prix marché desc":  ("_market_sort",     False),
            "Prix achat desc":   ("_purchase_sort",   False),
            "Δ Marché desc":     ("_diff_sort",       False),
            "Carte A-Z":         ("card_name",        True),
        }
        tri_label = st.selectbox("Trier par", list(tri_options.keys()), key="sort_prices")
        tri_col, tri_asc = tri_options[tri_label]

    # Remise par carte — chargée depuis fichier une seule fois par session
    if "remises" not in st.session_state:
        st.session_state["remises"] = load_remises()

    df_p_f = df_p[
        df_p["card_display_rarity"].isin(sel_rar_p) &
        df_p["position_agg"].isin(sel_pos_p)
    ].sort_values(tri_col, ascending=tri_asc, na_position="last").reset_index(drop=True)

    # Remise par carte depuis session state (clé = card_name, unique grâce au numéro de série)
    _remise_map = st.session_state["remises"]
    df_p_f["remise_pct"] = df_p_f["card_name"].map(
        lambda s: _remise_map.get(s, 0)
    ).fillna(0).astype(int)

    # ── Valeurs d'affichage (après tri) ───────────────────────────────────────
    def _fmt_market(row):
        v = row["_market_sort"]
        if v is None or pd.isna(v):
            return None
        amount = f"{v * rate:.2f} {sym}"
        if row.get("_market_primary"):
            return f"{amount} (crédits marché)"
        return amount

    df_p_f["market_price"] = df_p_f.apply(_fmt_market, axis=1)

    # Prix d'achat et Δ avec remise par carte
    def _purchase_display(row):
        v = row["_purchase_sort"]
        if pd.isna(v):
            return None
        return v * rate * (1 - row["remise_pct"] / 100)

    def _diff_amount(row):
        m = row["_market_sort"]
        p = row["_purchase_sort"]
        if pd.isna(m) or pd.isna(p):
            return None
        return (m - p * (1 - row["remise_pct"] / 100)) * rate

    def _diff_pct(row):
        p = row["_purchase_sort"]
        if row.get("origine") != "🛒 Achetée" or pd.isna(p) or p == 0:
            return None
        m = row["_market_sort"]
        if pd.isna(m):
            return None
        p_adj = p * (1 - row["remise_pct"] / 100)
        return (m - p_adj) / p_adj * 100 if p_adj else None

    df_p_f["purchase_price"] = df_p_f.apply(_purchase_display, axis=1)
    df_p_f["diff_amount"]    = df_p_f.apply(_diff_amount, axis=1)
    df_p_f["diff_pct"]       = df_p_f.apply(_diff_pct, axis=1)

    # ── XP % ──────────────────────────────────────────────────────────────────
    _xp_next = df_p_f["card_xp_needed_next_grade"].replace(0, None)
    df_p_f["xp_pct"] = (df_p_f["card_xp"].fillna(0) / _xp_next.fillna(1)).clip(0, 1) * 100

    # ── Tableau ────────────────────────────────────────────────────────────────
    price_label_achat  = f"Achat ({sym})"
    price_label_marche = f"Marché ({sym})"

    diff_label_amt = f"Δ ({sym})"
    diff_fmt       = "+%.2f $" if use_usd else "+%.2f €"

    base_cols = [
        "picture_url", "card_name", "position_agg", "card_display_rarity",
        "card_power", "card_grade", "xp_pct",
        "remise_pct", "purchase_price", "market_price", "diff_amount", "diff_pct",
        "in_season_eligible", "owner_since", "origine",
    ]
    rename_map = {
        "picture_url":         "Image",
        "card_name":           "Carte",
        "position_agg":        "Poste",
        "card_display_rarity": "Rareté",
        "card_power":          "Power",
        "card_grade":          "Grade",
        "xp_pct":              "XP",
        "remise_pct":          "Remise %",
        "purchase_price":      price_label_achat,
        "market_price":        price_label_marche,
        "diff_amount":         diff_label_amt,
        "diff_pct":            "Δ %",
        "in_season_eligible":  "In Season",
        "owner_since":         "Obtenue le",
        "origine":             "Origine",
    }
    col_config = {
        "Image":               st.column_config.ImageColumn(width="medium"),
        "Grade":               st.column_config.NumberColumn(format="%d"),
        "XP":                  st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
        "Power":               st.column_config.NumberColumn(format="%.2f"),
        "Remise %":            st.column_config.NumberColumn(
                                   min_value=0, max_value=100, step=5, format="%d %%",
                                   help="% remise crédits marketplace sur le prix d'achat"),
        price_label_achat:     st.column_config.NumberColumn(format=price_fmt),
        price_label_marche:    st.column_config.TextColumn(),
        diff_label_amt:        st.column_config.NumberColumn(format=diff_fmt),
        "Δ %":                 st.column_config.NumberColumn(format="%.1f%%"),
        "In Season":           st.column_config.CheckboxColumn(),
        "Obtenue le":          st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
    }

    if "so5_lineups_count" in df_p_f.columns:
        base_cols += ["so5_lineups_count", "so5_rewards_count"]
        rename_map["so5_lineups_count"] = "Compos"
        rename_map["so5_rewards_count"] = "Rewards"
        col_config["Compos"]  = st.column_config.NumberColumn(format="%d", help="Nombre de fois alignée en compétition")
        col_config["Rewards"] = st.column_config.NumberColumn(format="%d", help="Nombre de rewards gagnées")

    existing_cols = [c for c in base_cols if c in df_p_f.columns]
    table_p = df_p_f[existing_cols].rename(columns=rename_map)

    # Toutes les colonnes sont disabled sauf "Remise %"
    disabled_cols = [c for c in table_p.columns if c != "Remise %"]

    edited = st.data_editor(
        table_p,
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        disabled=disabled_cols,
        key=f"tab2_editor_{sel_manager}",
    )

    # Persistance des remises éditées → session state + fichier JSON
    if edited is not None and "Remise %" in edited.columns and "Carte" in edited.columns:
        changed = False
        for _, row in edited.iterrows():
            name = row["Carte"]
            if name:
                new_val = int(row["Remise %"])
                if st.session_state["remises"].get(name) != new_val:
                    st.session_state["remises"][name] = new_val
                    changed = True
        if changed:
            save_remises(st.session_state["remises"])

    st.caption(f"{len(df_p_f)} cartes affichées")
