import pandas as pd
import streamlit as st

from data_loaders import load_pitcher_pitches


def render(ctx: dict) -> None:
    _df_pp = load_pitcher_pitches()

    if _df_pp.empty:
        st.info(
            "Aucune donnée de pitch counts disponible. "
            "Lancez `python fetch_pitch_counts.py --full` pour initialiser, "
            "puis `python update_data.py --only 10` pour exporter le parquet."
        )
        return

    _pp_has_pos = "position" in _df_pp.columns

    _pp_c1, _pp_c2, _pp_c3, _pp_c4 = st.columns([2, 2, 3, 3])
    with _pp_c1:
        _pp_days = st.slider("Jours affichés", 3, 30, 10, key="pp_days")
    with _pp_c2:
        if _pp_has_pos:
            _pp_pos_filter = st.radio(
                "Position", ["SP", "RP", "SP + RP"],
                horizontal=True, key="pp_pos_filter",
            )
        else:
            _pp_pos_filter = "SP + RP"
            st.caption("Position dispo après prochain export parquet")
    with _pp_c3:
        _pp_search = st.text_input("🔍 Joueur", key="pp_search", placeholder="Nom...")
    with _pp_c4:
        _pp_teams_sel = st.multiselect(
            "Équipe",
            sorted(_df_pp["team_slug"].dropna().unique().tolist()),
            key="pp_teams",
        )

    _pp_cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=_pp_days)
    _df_pp_f = _df_pp[_df_pp["game_date"] >= _pp_cutoff].copy()

    if _pp_has_pos and _pp_pos_filter in ("SP", "RP"):
        _df_pp_f = _df_pp_f[_df_pp_f["position"] == _pp_pos_filter]
    if _pp_search:
        _df_pp_f = _df_pp_f[
            _df_pp_f["display_name"].fillna("").str.contains(_pp_search, case=False)
        ]
    if _pp_teams_sel:
        _df_pp_f = _df_pp_f[_df_pp_f["team_slug"].isin(_pp_teams_sel)]

    if _df_pp_f.empty:
        st.info("Aucun résultat pour ces filtres.")
        return

    _df_pp_f["_date_et"] = (
        _df_pp_f["game_date"].dt.tz_convert("America/New_York").dt.date
    )
    _sorted_dates = sorted(_df_pp_f["_date_et"].unique())
    _date_lbl = {d: f"{d.day} {d.strftime('%b')}" for d in _sorted_dates}

    _pivot = (
        _df_pp_f
        .pivot_table(
            index=["player_slug", "display_name", "team_slug"],
            columns="_date_et",
            values="pitches",
            aggfunc="sum",
        )
        .reset_index()
    )
    _pivot.columns.name = None
    _pivot = _pivot.rename(columns=_date_lbl)
    _date_cols_lbl = [_date_lbl[d] for d in _sorted_dates]

    _pivot["Total"] = _pivot[_date_cols_lbl].sum(axis=1, min_count=1)
    _pivot = _pivot.sort_values("Total", ascending=False).reset_index(drop=True)

    _pp_m1, _pp_m2, _pp_m3, _pp_m4 = st.columns(4)
    _pp_m1.metric("Pitchers", len(_pivot))
    _pp_m2.metric("Sorties", len(_df_pp_f))
    _pp_avg = _df_pp_f["pitches"].mean()
    _pp_m3.metric("Moy lancers / sortie", f"{_pp_avg:.0f}" if pd.notna(_pp_avg) else "—")
    if not _pivot.empty and pd.notna(_pivot["Total"].iloc[0]):
        _pp_top_name = str(_pivot["display_name"].iloc[0])[:18]
        _pp_top_tot  = int(_pivot["Total"].iloc[0])
        _pp_m4.metric("Top (total)", f"{_pp_top_name} ({_pp_top_tot})")

    _pp_disp = _pivot[["display_name", "team_slug"] + _date_cols_lbl + ["Total"]].copy()
    _pp_disp.columns = ["Pitcher", "Équipe"] + _date_cols_lbl + ["Total"]

    st.dataframe(
        _pp_disp,
        use_container_width=True,
        hide_index=True,
        column_config={
            **{c: st.column_config.NumberColumn(c, format="%d") for c in _date_cols_lbl},
            "Total": st.column_config.NumberColumn("Total", format="%d"),
        },
    )
