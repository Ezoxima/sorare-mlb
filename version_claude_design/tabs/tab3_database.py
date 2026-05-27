import streamlit as st

from data_loaders import load_db_stats, FENETRE_OPTIONS, show_player_chart


def render(ctx: dict) -> None:
    sel_stat       = ctx["sel_stat"]
    sel_stat_label = ctx["sel_stat_label"]
    fenetre        = ctx["fenetre"]
    target         = ctx["target"]

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

    st.markdown(
        f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
        f'<span class="title">Top {int(top_n)} — {sel_stat_label}</span>'
        f'<span class="pill">{fenetre}</span>'
        f'<span class="right" style="color:var(--fg-3);font-size:9px">{len(df_db_f)} / {len(df_db)} joueurs</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

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
