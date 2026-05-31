import streamlit as st
import pandas as pd

from data_loaders import RARITY_ORDER


def render(ctx: dict) -> None:
    df_prices   = ctx["df_prices"]
    sel_manager = ctx["sel_manager"]

    df_p = df_prices[df_prices["gallery_manager"] == sel_manager].copy()

    if df_p.empty:
        st.info("Aucune carte trouvée.")
    else:
        val_is  = df_p["price_in_season"].sum()
        val_oos = df_p["price_out_season"].sum()
        n_priced = df_p["price_in_season"].notna().sum()

        st.markdown(
            f'<div class="metrics">'
            f'<div class="metric"><div class="k">Cartes</div><div class="v">{len(df_p)}</div></div>'
            f'<div class="metric"><div class="k">Avec prix</div><div class="v">{int(n_priced)}</div></div>'
            f'<div class="metric"><div class="k">Valeur IS</div><div class="v pos">{val_is:.0f} €</div></div>'
            f'<div class="metric"><div class="k">Valeur Classic</div><div class="v" style="color:var(--fg-2)">{val_oos:.0f} €</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])
        with col_f1:
            raretés_filtre = sorted(df_p["card_display_rarity"].dropna().unique(),
                                    key=lambda r: RARITY_ORDER.get(r.lower() if r else "", 99))
            sel_rar_p = st.multiselect("Rareté", raretés_filtre, default=raretés_filtre, key="rar_prices")
        with col_f2:
            positions_filtre = sorted(df_p["position_agg"].dropna().unique())
            sel_pos_p = st.multiselect("Poste", positions_filtre, default=positions_filtre, key="pos_prices")
        with col_f3:
            tri_options = {
                "Power desc":  ("card_power", False),
                "Carte A-Z":   ("card_name",  True),
            }
            tri_label = st.selectbox("Trier par", list(tri_options.keys()), key="sort_prices")
            tri_col, tri_asc = tri_options[tri_label]
        with col_f4:
            remise_pct = st.number_input(
                "Remise (%)", min_value=0, max_value=100, value=0, step=5,
                key="remise_pct", help="% remise crédits marketplace appliquée au prix d'achat",
            )

        df_p_f = df_p[
            df_p["card_display_rarity"].isin(sel_rar_p) &
            df_p["position_agg"].isin(sel_pos_p)
        ].sort_values(tri_col, ascending=tri_asc).reset_index(drop=True)

        _xp_next = df_p_f["card_xp_needed_next_grade"].replace(0, None)
        df_p_f["xp_pct"] = (df_p_f["card_xp"].fillna(0) / _xp_next.fillna(1)).clip(0, 1) * 100

        if "purchase_price_eur" in df_p_f.columns:
            df_p_f["purchase_price"] = pd.to_numeric(df_p_f["purchase_price_eur"], errors="coerce")
            if remise_pct > 0:
                df_p_f["purchase_price"] = (
                    df_p_f["purchase_price"] * (1 - remise_pct / 100)
                ).round(2)
        else:
            df_p_f["purchase_price"] = None

        table_p = df_p_f[[
            "picture_url", "card_name", "position_agg", "card_display_rarity",
            "card_power", "card_grade", "xp_pct", "purchase_price", "in_season_eligible",
        ]].rename(columns={
            "picture_url":         "Image",
            "card_name":           "Carte",
            "position_agg":        "Poste",
            "card_display_rarity": "Rareté",
            "card_power":          "Power",
            "card_grade":          "Grade",
            "xp_pct":              "XP",
            "purchase_price":      "Prix achat (€)",
            "in_season_eligible":  "In Season",
        })

        st.dataframe(
            table_p,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Image":          st.column_config.ImageColumn(width="medium"),
                "Grade":          st.column_config.NumberColumn(format="%d"),
                "XP":             st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
                "Power":          st.column_config.NumberColumn(format="%.2f"),
                "Prix achat (€)": st.column_config.NumberColumn(format="%.2f €"),
                "In Season":      st.column_config.CheckboxColumn(),
            },
        )
        st.caption(f"{len(df_p_f)} cartes affichées")
