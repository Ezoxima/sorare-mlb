import math as _math9

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render(ctx: dict) -> None:
    df_lb = ctx["df_lb"]

    if df_lb.empty:
        st.info("Aucune donnée de compétition. Lance `python fetch_leaderboard_history.py` pour collecter.")
        st.stop()

    _arena9 = df_lb[
        (df_lb["source"] == "arena") &
        ~df_lb["leaderboard_slug"].str.lower().str.endswith("_pve", na=False)
    ].copy()
    _hs9    = df_lb[df_lb["source"] == "hot_streak"].copy()

    _RAR_DISPLAY9 = {"limited": "Limited", "rare": "Rare", "super_rare": "Super Rare"}

    _col9a, _col9b, _col9c_filt = st.columns([2, 2, 3])
    with _col9a:
        _rar9 = st.radio(
            "Rareté", ["limited", "rare", "super_rare"],
            format_func=lambda r: _RAR_DISPLAY9.get(r, r),
            horizontal=True, key="lb9_rar",
        )
    _rar9_disp = _RAR_DISPLAY9.get(_rar9, _rar9)
    with _col9b:
        _arena_filter9 = st.radio(
            "Type", ["Toutes", "Arena", "Classiques"],
            horizontal=True, key="lb9_arena_filter",
        )

    _rar_df9 = _arena9[_arena9["rarity_type"] == _rar9].copy()
    if _arena_filter9 == "Arena":
        _rar_df9 = _rar_df9[_rar_df9["is_arena"] == True]
    elif _arena_filter9 == "Classiques":
        _rar_df9 = _rar_df9[_rar_df9["is_arena"] == False]

    _name_map9 = {
        (f"ARENA — {n}" if bool(
            _rar_df9[_rar_df9["leaderboard_name"] == n]["is_arena"].any()
        ) else n): n
        for n in sorted(_rar_df9["leaderboard_name"].dropna().unique())
    }
    _all_comps9_disp = list(_name_map9.keys())
    _default_real9   = ["Champion"]
    _default_disp9   = [d for d, r in _name_map9.items() if r in _default_real9]

    with _col9c_filt:
        _sel_comps9_disp = st.multiselect(
            "Compétitions", _all_comps9_disp,
            default=_default_disp9,
            key="lb9_comps",
        )

    _sel_comps9 = [_name_map9[d] for d in _sel_comps9_disp if d in _name_map9]

    st.divider()

    _df9 = _arena9[
        (_arena9["rarity_type"] == _rar9) &
        (_arena9["leaderboard_name"].isin(_sel_comps9)) &
        _arena9["score_threshold"].notna() &
        _arena9["gw_int"].notna()
    ].copy()
    _df9["gw_int"] = _df9["gw_int"].astype(int)
    _rev_map9 = {v: k for k, v in _name_map9.items()}
    _df9["leaderboard_display"] = _df9["leaderboard_name"].map(_rev_map9).fillna(_df9["leaderboard_name"])

    st.subheader("Évolution des seuils par compétition")
    st.caption("Seuil d'entrée = score minimum pour toute récompense · Seuil top = score le plus haut")

    _entry9 = (
        _df9.groupby(["gw_int", "leaderboard_display"], as_index=False)
        .agg(
            entry=("score_threshold", "min"),
            top=("score_threshold", "max"),
            median=("score_threshold", "median"),
            nb_div=("leaderboard_slug", "nunique"),
        )
        .sort_values("gw_int")
    )

    _COMP_COLORS = {
        "Champion":   "#f59e0b",
        "Challenger": "#ef4444",
        "Standard":   "#3b82f6",
        "American":   "#10b981",
        "National":   "#8b5cf6",
        "Beginner":   "#94a3b8",
        "Elite":      "#ec4899",
        "Hitters":    "#06b6d4",
        "Legacy":     "#a16207",
        "OG":         "#7c3aed",
        "Sandlot":    "#059669",
    }

    fig_entry = go.Figure()
    for comp_disp in _sel_comps9_disp:
        comp_real = _name_map9.get(comp_disp, comp_disp)
        sub = _entry9[_entry9["leaderboard_display"] == comp_disp]
        if sub.empty:
            continue
        color = _COMP_COLORS.get(comp_real, "#888")
        if (sub["top"] - sub["entry"]).max() > 1:
            fig_entry.add_trace(go.Scatter(
                x=list(sub["gw_int"]) + list(sub["gw_int"])[::-1],
                y=list(sub["top"]) + list(sub["entry"])[::-1],
                fill="toself",
                fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.10)",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ))
        fig_entry.add_trace(go.Scatter(
            x=sub["gw_int"], y=sub["entry"],
            mode="lines+markers",
            name=f"{comp_disp} — entrée",
            line=dict(color=color, width=2, dash="dot"),
            marker=dict(size=6),
            customdata=sub[["nb_div"]].values,
            hovertemplate="%{y:.1f} pts · %{customdata[0]} division(s)<extra>%{fullData.name}</extra>",
        ))
        fig_entry.add_trace(go.Scatter(
            x=sub["gw_int"], y=sub["top"],
            mode="lines+markers",
            name=f"{comp_disp} — top",
            line=dict(color=color, width=2),
            marker=dict(size=6),
            customdata=sub[["nb_div"]].values,
            hovertemplate="%{y:.1f} pts · %{customdata[0]} division(s)<extra>%{fullData.name}</extra>",
        ))

    _champ_real9 = "Champion"
    _champ_disp9 = _rev_map9.get(_champ_real9, _champ_real9)
    if _champ_disp9 in _sel_comps9_disp:
        _champ_mon9 = (
            _df9[
                (_df9["leaderboard_name"] == _champ_real9) &
                (_df9["reward_type"] == "monetary") &
                _df9["score_threshold"].notna()
            ]
            .groupby("gw_int", as_index=False)
            .agg(entree_dollar=("score_threshold", "min"))
            .sort_values("gw_int")
        )
        if not _champ_mon9.empty:
            fig_entry.add_trace(go.Scatter(
                x=_champ_mon9["gw_int"], y=_champ_mon9["entree_dollar"],
                mode="lines+markers",
                name=f"{_champ_disp9} — entrée $",
                line=dict(color="#22c55e", width=2, dash="dashdot"),
                marker=dict(size=7, symbol="diamond"),
                hovertemplate="%{y:.1f} pts<extra>%{fullData.name}</extra>",
            ))

    _gw_min9 = int(_df9["gw_int"].min()) if not _df9.empty else 119
    _gw_max9 = int(_df9["gw_int"].max()) if not _df9.empty else 133
    fig_entry.update_layout(
        xaxis=dict(title="GW", tickmode="linear", dtick=1,
                   range=[_gw_min9 - 0.5, _gw_max9 + 0.5]),
        yaxis=dict(title="Score"),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        margin=dict(r=200),
    )
    st.plotly_chart(fig_entry, use_container_width=True)

    st.divider()
    st.subheader("Structure des paliers — détail")

    _gws_sorted9 = sorted(_arena9["gw_int"].dropna().unique())

    _col9c, _col9d, _col9e = st.columns([2, 2, 2])
    with _col9c:
        _comp_detail9_disp = st.selectbox(
            "Compétition", _sel_comps9_disp if _sel_comps9_disp else _all_comps9_disp,
            key="lb9_comp_detail",
        )
    with _col9d:
        _detail_mode9 = st.radio(
            "Période", ["GW spécifique", "Moyenne 5 dernières GW"],
            horizontal=True, key="lb9_detail_mode",
        )
    _comp_detail9_real = _name_map9.get(_comp_detail9_disp, _comp_detail9_disp) if _comp_detail9_disp else None

    _gw_detail9 = None
    if _detail_mode9 == "GW spécifique":
        with _col9e:
            _gws_avail9 = sorted(
                _df9[_df9["leaderboard_name"] == _comp_detail9_real]["gw_int"].unique(), reverse=True
            ) if _comp_detail9_real else []
            _gw_detail9 = st.selectbox(
                "GW", _gws_avail9, index=0, key="lb9_gw_detail"
            ) if _gws_avail9 else None

    if _comp_detail9_real and (_gw_detail9 is not None or _detail_mode9 == "Moyenne 5 dernières GW"):
        _has_from_rank9 = "from_rank" in _df9.columns

        if _detail_mode9 == "GW spécifique":
            _detail9 = _df9[
                (_df9["leaderboard_name"] == _comp_detail9_real) &
                (_df9["gw_int"] == _gw_detail9) &
                _df9["score_threshold"].notna()
            ]
            _title_base9 = f"{_comp_detail9_disp} {_rar9_disp} — GW{_gw_detail9}"
        else:
            _gws_comp9 = sorted(_df9[_df9["leaderboard_name"] == _comp_detail9_real]["gw_int"].unique())
            _gws_comp_excl9 = _gws_comp9[:-1] if len(_gws_comp9) > 1 else _gws_comp9
            _last5_detail9  = _gws_comp_excl9[-5:]
            _detail9 = _df9[
                (_df9["leaderboard_name"] == _comp_detail9_real) &
                _df9["gw_int"].isin(_last5_detail9) &
                _df9["score_threshold"].notna()
            ]
            _gw_range9   = f"GW{int(_last5_detail9[0])}–GW{int(_last5_detail9[-1])}"
            _title_base9 = f"{_comp_detail9_disp} {_rar9_disp} — moy. {_gw_range9}"

        def _build_tiers(df_sub: pd.DataFrame) -> pd.DataFrame:
            if df_sub.empty:
                return pd.DataFrame()
            agg = dict(
                score_min=("score_threshold", "min"),
                score_median=("score_threshold", "median"),
                score_max=("score_threshold", "max"),
                reward_quantity=("reward_quantity", "median"),
                reward_usd_cents=("reward_usd_cents", "median"),
            )
            if _has_from_rank9:
                agg["from_rank"] = ("from_rank", "first")
            t = df_sub.groupby("tier_rank", as_index=False).agg(**agg).sort_values("tier_rank")
            if "from_rank" not in t.columns:
                t["from_rank"] = None
            return t

        _tiers_mon9 = _build_tiers(_detail9[_detail9["reward_type"] == "monetary"])
        _tiers_ess9 = _build_tiers(_detail9[_detail9["reward_type"] == "card_shard"])

        def _fig_paliers(tiers: pd.DataFrame, title: str, bar_color: str, reward_type: str = "card_shard") -> go.Figure:
            fig = go.Figure()
            for _, row in tiers.iterrows():
                tier  = int(row["tier_rank"])
                score = row["score_median"]
                x_label = (
                    f"Top {int(row['from_rank'])}"
                    if pd.notna(row.get("from_rank"))
                    else f"Palier {tier}"
                )
                if reward_type == "monetary" and pd.notna(row.get("reward_usd_cents")):
                    reward_text = f"${row['reward_usd_cents'] / 100:.0f}"
                elif pd.notna(row.get("reward_quantity")):
                    reward_text = f"{int(row['reward_quantity'])}"
                else:
                    reward_text = ""
                err_y = dict(
                    type="data", symmetric=False,
                    array=[row["score_max"] - score],
                    arrayminus=[score - row["score_min"]],
                    visible=True, color=bar_color,
                ) if (row["score_max"] - row["score_min"]) > 0.5 else None
                fig.add_trace(go.Bar(
                    x=[x_label], y=[score],
                    error_y=err_y,
                    marker_color=bar_color,
                    text=[reward_text],
                    textposition="inside",
                    insidetextanchor="middle",
                    textangle=0,
                    textfont=dict(color="white", size=13),
                    showlegend=False,
                    hovertemplate=f"Score seuil : %{{y:.1f}}<br>Récompense : {reward_text}<extra></extra>",
                ))
            y_max = float(tiers["score_max"].max()) if not tiers.empty else 300
            fig.update_layout(
                title=title,
                yaxis=dict(title="Score requis", range=[0, y_max * 1.18]),
                xaxis=dict(title="Classement"),
                height=360,
                bargap=0.35,
                margin=dict(t=50, b=40),
            )
            return fig

        _fcols9 = st.columns(2)
        with _fcols9[0]:
            if not _tiers_mon9.empty:
                st.plotly_chart(
                    _fig_paliers(_tiers_mon9, f"Récompenses en Cash — {_title_base9}", "#22c55e", reward_type="monetary"),
                    use_container_width=True,
                )
            else:
                st.caption("Pas de récompenses monétaires pour cette compétition.")
        with _fcols9[1]:
            if not _tiers_ess9.empty:
                st.plotly_chart(
                    _fig_paliers(_tiers_ess9, f"Essences — {_title_base9}", "#a78bfa"),
                    use_container_width=True,
                )
            else:
                st.caption("Pas de récompenses en essences pour cette compétition.")

    st.divider()
    st.subheader("Récapitulatif des seuils")

    _gws_recap9 = (_gws_sorted9[:-1] if len(_gws_sorted9) > 1 else _gws_sorted9)[-5:]
    _recap_per_gw9 = (
        _arena9[
            (_arena9["gw_int"].isin(_gws_recap9)) &
            (_arena9["rarity_type"] == _rar9) &
            _arena9["score_threshold"].notna()
        ]
        .groupby(["gw_int", "leaderboard_name"], as_index=False)
        .agg(
            seuil_entree=("score_threshold", "min"),
            seuil_top=("score_threshold", "max"),
            nb_divisions=("leaderboard_slug", "nunique"),
        )
    )
    _recap9 = (
        _recap_per_gw9
        .groupby("leaderboard_name", as_index=False)
        .agg(
            seuil_entree=("seuil_entree", "mean"),
            seuil_top=("seuil_top", "mean"),
            nb_divisions=("nb_divisions", "mean"),
        )
        .sort_values("seuil_entree")
    )
    _recap9.columns = ["Compétition", "Seuil entrée", "Seuil top", "Nb divisions"]
    _gw_range_recap9 = (
        f"GW{int(_gws_recap9[0])}–GW{int(_gws_recap9[-1])}"
        if len(_gws_recap9) >= 2 else f"GW{int(_gws_recap9[0])}"
    ) if _gws_recap9 else "—"
    st.caption(f"Moy. {_gw_range_recap9} · rareté {_rar9_disp}")
    st.dataframe(
        _recap9.style.format({"Seuil entrée": "{:.1f}", "Seuil top": "{:.1f}"}),
        use_container_width=True, hide_index=True,
    )

    st.divider()
    st.subheader("Hot Streak — seuils de référence")
    st.caption("Seuils fixes (indépendants de la GW). Bonus essences = par équipe supplémentaire atteignant le seuil.")
    _hs_disp9 = _hs9[_hs9["rarity_type"] == _rar9][
        ["score_threshold", "reward_quantity", "bonus_shards"]
    ].rename(columns={
        "score_threshold": "Score cible",
        "reward_quantity": "Essences (1ère équipe)",
        "bonus_shards":    "Bonus / équipe supp.",
    })
    st.dataframe(
        _hs_disp9.style.format({"Score cible": "{:.0f}", "Essences (1ère équipe)": "{:.0f}", "Bonus / équipe supp.": "{:.0f}"}),
        use_container_width=True, hide_index=True,
    )

    st.divider()
    st.subheader("Comparaison de rentabilité")

    _ESS_RATE9        = 3 / 1000
    _ARENA_ENTRY9     = {"Beginner": 100, "Elite": 800}
    _ARENA_ENTRY_DEF9 = 300
    _LINEUP_SIZE9     = {"Hitters": 5, "Sandlot": 5}
    _LINEUP_COMP9     = {"Hitters": "5 hitters", "Sandlot": "3 hitters + 2 SP"}

    _hs_all9 = (
        _hs9[_hs9["rarity_type"] == _rar9]
        .sort_values("score_threshold")
        .reset_index(drop=True)
    )
    _hs_palier_labels9 = [
        f"Palier {i+1} ({int(r.score_threshold)} pts)"
        for i, r in enumerate(_hs_all9.itertuples(index=False))
    ]

    _cmp_c1, _cmp_c2, _cmp_c3 = st.columns([4, 2, 2])
    with _cmp_c1:
        _score_cmp9 = st.slider(
            "Score cible (lineup 7 joueurs)", min_value=100, max_value=400, value=200, step=5, key="lb9_score_cmp"
        )
    with _cmp_c2:
        _hs_palier_sel9 = st.selectbox(
            "Palier HS actuel",
            options=list(range(len(_hs_palier_labels9))),
            format_func=lambda i: _hs_palier_labels9[i],
            key="lb9_hs_palier",
        )
    with _cmp_c3:
        _n_teams_hs9 = st.number_input(
            "Équipes Hot Streak", min_value=1, max_value=4, value=1, step=1, key="lb9_n_teams_hs"
        )

    _gw_mode_cmp9 = st.radio(
        "Référence GW", ["Dernière GW terminée", "Moyenne 5 dernières GW terminées"],
        horizontal=True, key="lb9_gw_mode_cmp",
    )
    _gws_excl_last9 = _gws_sorted9[:-1]
    if _gw_mode_cmp9 == "Dernière GW terminée":
        _gws_cmp9      = [int(_gws_excl_last9[-1])] if len(_gws_excl_last9) >= 1 else []
        _gw_ref_lbl9   = f"GW{_gws_cmp9[0]}" if _gws_cmp9 else "—"
    else:
        _last5_cmp9    = _gws_excl_last9[-5:] if len(_gws_excl_last9) >= 5 else _gws_excl_last9
        _gws_cmp9      = [int(g) for g in _last5_cmp9]
        _gw_ref_lbl9   = f"moy. GW{_gws_cmp9[0]}–GW{_gws_cmp9[-1]}" if _gws_cmp9 else "—"

    st.caption(f"Hypothèse : 1 000 essences = 3 $ · Référence : {_gw_ref_lbl9}")

    def _best_tier_reached(df_ref, score):
        hits = df_ref[df_ref["score_threshold"] <= score]
        return hits.sort_values("score_threshold", ascending=False).iloc[0] if not hits.empty else None

    _ref_base9 = _arena9[
        (_arena9["rarity_type"] == _rar9) &
        _arena9["gw_int"].isin(_gws_cmp9) &
        _arena9["score_threshold"].notna()
    ]
    _is_arena_map9 = _ref_base9.groupby("leaderboard_name")["is_arena"].first().to_dict()

    _comp_ref9 = (
        _ref_base9
        .groupby(["leaderboard_name", "reward_type", "tier_rank"], as_index=False)
        .agg(
            score_threshold=("score_threshold",  "median"),
            reward_quantity=("reward_quantity",   "median"),
            reward_usd_cents=("reward_usd_cents", "median"),
        )
    )

    _cmp_rows9 = []
    _comp_order9 = sorted(_comp_ref9["leaderboard_name"].unique())
    for _cname9 in _comp_order9:
        _is_arena_c9  = bool(_is_arena_map9.get(_cname9, False))
        _entry9_cost  = _ARENA_ENTRY9.get(_cname9, _ARENA_ENTRY_DEF9) if _is_arena_c9 else 0
        _prefix9      = "ARENA — " if _is_arena_c9 else ""
        _n_players9   = _LINEUP_SIZE9.get(_cname9, 7)
        _fmt_lbl9     = _LINEUP_COMP9.get(_cname9, f"{_n_players9} joueurs")

        _adj9 = 7 / _n_players9

        for _rtype9 in ["monetary", "card_shard"]:
            _sub9 = _comp_ref9[
                (_comp_ref9["leaderboard_name"] == _cname9) &
                (_comp_ref9["reward_type"] == _rtype9)
            ].copy()
            if _sub9.empty:
                continue

            _sub9["score_threshold"] = _sub9["score_threshold"] * _adj9
            _best9 = _best_tier_reached(_sub9, _score_cmp9)

            if _rtype9 == "monetary":
                _lbl9 = f"{_prefix9}{_cname9} (cash)"
                if _best9 is not None:
                    _val9   = float(_best9["reward_usd_cents"]) / 100
                    _rew9   = f"${_val9:.2f}"
                    _thr_adj9  = _best9["score_threshold"]
                    _thr_real9 = _thr_adj9 / _adj9
                    _seuil9 = (
                        f"{_thr_adj9:.0f} pts ({_thr_real9:.0f} réel)"
                        if _n_players9 != 7
                        else f"{_thr_adj9:.0f} pts"
                    )
                else:
                    _val9   = 0.0
                    _rew9   = "$0"
                    _seuil9 = "non atteint"
            else:
                _lbl9 = f"{_prefix9}{_cname9} (ess.)"
                if _best9 is not None:
                    _ess9      = float(_best9["reward_quantity"])
                    _net9      = _ess9 - _entry9_cost
                    _val9      = _net9 * _ESS_RATE9
                    _thr_adj9  = _best9["score_threshold"]
                    _thr_real9 = _thr_adj9 / _adj9
                    _seuil9 = (
                        f"{_thr_adj9:.0f} pts ({_thr_real9:.0f} réel)"
                        if _n_players9 != 7
                        else f"{_thr_adj9:.0f} pts"
                    )
                    _rew9   = (
                        f"{int(_ess9)} − {_entry9_cost} = {int(_net9)} ess. → ${_val9:.2f}"
                        if _entry9_cost > 0
                        else f"{int(_ess9)} ess. → ${_val9:.2f}"
                    )
                else:
                    _net9   = -_entry9_cost
                    _val9   = _net9 * _ESS_RATE9
                    _seuil9 = "non atteint"
                    _rew9   = (
                        f"0 − {_entry9_cost} = {int(_net9)} ess. → ${_val9:.2f}"
                        if _entry9_cost > 0
                        else "0 ess. → $0"
                    )

            _cmp_rows9.append({
                "Compétition":      _lbl9,
                "Format":           _fmt_lbl9,
                "Score nécessaire": _seuil9,
                "Récompense":       _rew9,
                "Valeur ($)":       _val9,
            })

    _hsr_sel9    = _hs_all9.iloc[_hs_palier_sel9]
    _hs_thr9     = float(_hsr_sel9["score_threshold"])
    _hs_rew9     = float(_hsr_sel9["reward_quantity"])
    _hs_bon9     = float(_hsr_sel9.get("bonus_shards", 0) or 0)
    _hs_label9   = _hs_palier_labels9[_hs_palier_sel9]

    if _score_cmp9 >= _hs_thr9:
        _hs_total9   = _hs_rew9 + (_n_teams_hs9 - 1) * _hs_bon9
        _hs_val9     = _hs_total9 * _ESS_RATE9
        _hs_rew_str9 = (
            f"{int(_hs_rew9)} ess. → ${_hs_val9:.2f}" if _n_teams_hs9 == 1
            else f"{int(_hs_rew9)} + {_n_teams_hs9-1}×{int(_hs_bon9)} = {int(_hs_total9)} ess. → ${_hs_val9:.2f}"
        )
        _hs_seuil9   = f"{int(_hs_thr9)} pts ✓"
        _hs_next9    = (_hs_palier_labels9[_hs_palier_sel9 + 1]
                        if _hs_palier_sel9 + 1 < len(_hs_palier_labels9)
                        else "Streak complète !")
    else:
        _hs_val9     = 0.0
        _hs_rew_str9 = "$0 + reset palier 1"
        _hs_seuil9   = f"{int(_hs_thr9)} pts ✗"
        _hs_next9    = "—"

    _cmp_rows9.append({
        "Compétition":      f"Hot Streak {_hs_label9}",
        "Format":           "7 joueurs",
        "Score nécessaire": _hs_seuil9,
        "Récompense":       _hs_rew_str9,
        "Valeur ($)":       _hs_val9,
    })

    _cmp_df9   = pd.DataFrame(_cmp_rows9).sort_values("Valeur ($)", ascending=False).reset_index(drop=True)
    _best_val9 = float(_cmp_df9["Valeur ($)"].max())

    def _hl_best9(row):
        bg = "background-color: rgba(34,197,94,0.20)" if row["Valeur ($)"] == _best_val9 and _best_val9 > 0 else ""
        return [bg] * len(row)

    _display_cols9 = ["Compétition", "Format", "Score nécessaire", "Récompense", "Valeur ($)"]
    st.dataframe(
        _cmp_df9[_display_cols9].style.apply(_hl_best9, axis=1).format({"Valeur ($)": "${:.2f}"}),
        use_container_width=True, hide_index=True,
    )

    if _best_val9 > 0:
        _winner9 = _cmp_df9.iloc[0]
        st.success(f"**Meilleur choix à {_score_cmp9} pts :** {_winner9['Compétition']} — {_winner9['Récompense']}")

    if _score_cmp9 >= _hs_thr9 and _hs_next9 not in ("—", "Streak complète !"):
        st.info(f"Hot Streak réussie → prochain palier : **{_hs_next9}**")

    st.caption(
        "Arena : coût d'entrée déduit (Beginner 100 ess., Elite 800 ess., autres 300 ess.). "
        "Hitters / Sandlot : seuils multipliés par 7/5 pour comparaison sur base 7 joueurs (valeur réelle entre parenthèses). "
        "Champion / Challenger (cash) et (ess.) sont mutuellement exclusifs selon le classement final. "
        "Hot Streak : tout ou rien — échec = $0 et retour au palier 1. "
        "Multi-équipes HS : toutes les équipes supposées au même score."
    )
