import math as _math
import streamlit as st
import pandas as pd

from data_loaders import (
    load_upcoming_pitchers, load_matchup_stats, load_player_avg_scores,
    load_pitcher_stats_vv, FENETRE_OPTIONS, POSITION_AGG, POSITION_EXACT,
)


def render(ctx: dict) -> None:
    df_calendar = ctx["df_calendar"]
    df_ml       = ctx["df_ml"]
    df_prices   = ctx["df_prices"]
    sel_manager = ctx["sel_manager"]
    fenetre     = ctx["fenetre"]

    try:
        df_p7, gw7 = load_upcoming_pitchers()
    except Exception as e:
        st.error(f"Impossible de charger les matchs : {e}")
        df_p7, gw7 = pd.DataFrame(), 0

    if df_p7.empty:
        st.info("Aucun match programmé pour le prochain fixture CLASSIC.")
    else:
        _gw_teams7 = set(df_p7["home_team_slug"].dropna()) | set(df_p7["away_team_slug"].dropna())
        _gw_pit_slugs7 = set(df_p7["home_pitcher_slug"].dropna()) | set(df_p7["away_pitcher_slug"].dropna())

        _gal_h7 = (
            df_calendar[
                (df_calendar["gallery_manager"] == sel_manager) &
                df_calendar["active_club_slug"].isin(_gw_teams7) &
                ~df_calendar["position_agg"].isin(["SP", "RP"])
            ]
            .drop_duplicates("player_slug")
        )
        _gal_sp7 = (
            df_calendar[
                (df_calendar["gallery_manager"] == sel_manager) &
                df_calendar["player_slug"].isin(_gw_pit_slugs7)
            ]
            .drop_duplicates("player_slug")
        )

        _h_slugs7    = tuple(_gal_h7["player_slug"])
        _p_slugs7    = tuple(_gal_sp7["player_slug"])
        _all_p7      = tuple(_gw_pit_slugs7)

        df_mu7 = load_matchup_stats(_h_slugs7, _all_p7)
        mu7: dict = {}
        for _, r in df_mu7.iterrows():
            if pd.notna(r["avg_sorare_score"]):
                mu7[(r["hitter_slug"], r["pitcher_slug"])] = float(r["avg_sorare_score"])

        _fen7      = FENETRE_OPTIONS[fenetre]
        df_havg7   = load_player_avg_scores(_h_slugs7, _fen7)
        havg7      = df_havg7.set_index("player_slug")["avg_score"].to_dict()

        df_pgen7, _ = load_pitcher_stats_vv(_p_slugs7, ())
        pavg7: dict = (
            df_pgen7.drop_duplicates("player_slug")
            .set_index("player_slug")["avg_sorare_score"]
            .dropna()
            .to_dict()
        ) if not df_pgen7.empty else {}

        team_sched7: dict = {}
        for _, g in df_p7.iterrows():
            hts, ats = g["home_team_slug"], g["away_team_slug"]
            gdt = g["game_date"]
            if hts:
                team_sched7.setdefault(hts, []).append({
                    "pitcher_slug": g["away_pitcher_slug"] or None,
                    "opp_name":     g["away_team_name"],
                    "game_date":    gdt,
                })
            if ats:
                team_sched7.setdefault(ats, []).append({
                    "pitcher_slug": g["home_pitcher_slug"] or None,
                    "opp_name":     g["home_team_name"],
                    "game_date":    gdt,
                })

        max_games7 = max((len(v) for v in team_sched7.values()), default=0)

        _sorare_proj7: dict = (
            df_prices[df_prices["gallery_manager"] == sel_manager]
            .drop_duplicates("player_slug")
            .set_index("player_slug")["next_gw_projected_score"]
            .dropna()
            .to_dict()
        )

        _ml7: dict = {}
        if not df_ml.empty:
            _ml7 = (
                df_ml[df_ml["gallery_manager"] == sel_manager]
                .drop_duplicates("player_slug")
                .set_index("player_slug")[[
                    "pred_median", "pred_lo", "pred_hi",
                    "pred_contextual", "park_factor", "weather_factor",
                    "opp_quality_factor", "day_night_factor", "rest_factor", "home_away_factor",
                    "platoon_factor_C", "bat_hand", "opp_pitcher_hand",
                ]]
                .to_dict("index")
            )

        proj7 = []

        for _, row in _gal_h7.iterrows():
            h_slug  = row["player_slug"]
            h_team  = row["active_club_slug"]
            games   = sorted(team_sched7.get(h_team, []), key=lambda x: x["game_date"])
            total   = 0.0
            nb_g    = 0
            game_scores = []
            for gm in games:
                ps    = gm["pitcher_slug"]
                score = (mu7.get((h_slug, ps)) if ps else None) or havg7.get(h_slug)
                if score is not None:
                    total += score
                    nb_g  += 1
                game_scores.append(round(score, 1) if score is not None else None)

            ml_d   = _ml7.get(h_slug)
            ml_med = round(ml_d["pred_median"] * nb_g, 1) if ml_d and nb_g > 0 else None
            _ctx7  = ml_d.get("pred_contextual") if ml_d else None
            ctx_pred = (round(float(_ctx7) * nb_g, 1)
                        if (_ctx7 is not None and not _math.isnan(float(_ctx7)) and nb_g > 0)
                        else None)

            entry = {
                "player_slug":        h_slug,
                "player_name":        row["player_name"],
                "position_agg":       row["position_agg"] or "?",
                "in_season_eligible": row["in_season_eligible"],
                "category":           "Hitter",
                "nb_games":           nb_g,
                "projected_score":    round(total, 1) if nb_g > 0 else None,
                "sorare_proj":        _sorare_proj7.get(h_slug),
                "ml_pred":            ml_med,
                "ctx_pred":           ctx_pred,
                "bat_hand":           ml_d.get("bat_hand")           if ml_d else None,
                "opp_pitcher_hand":   ml_d.get("opp_pitcher_hand")   if ml_d else None,
                "platoon_factor_C":   ml_d.get("platoon_factor_C")   if ml_d else None,
                "park_factor":        ml_d.get("park_factor")        if ml_d else None,
                "weather_factor":     ml_d.get("weather_factor")     if ml_d else None,
                "opp_quality_factor": ml_d.get("opp_quality_factor") if ml_d else None,
                "home_away_factor":   ml_d.get("home_away_factor")   if ml_d else None,
                "day_night_factor":   ml_d.get("day_night_factor")   if ml_d else None,
                "rest_factor":        ml_d.get("rest_factor")        if ml_d else None,
            }
            for i, gs in enumerate(game_scores):
                entry[f"G{i+1}"] = gs
            proj7.append(entry)

        for _, row in _gal_sp7.iterrows():
            ps    = row["player_slug"]
            score = pavg7.get(ps)
            ml_d  = _ml7.get(ps)
            _ng_sp7 = 1 if score is not None else 0
            _ctx_sp = ml_d.get("pred_contextual") if ml_d else None
            ctx_pred_sp = (round(float(_ctx_sp) * _ng_sp7, 1)
                           if (_ctx_sp is not None and not _math.isnan(float(_ctx_sp)) and _ng_sp7 > 0)
                           else None)
            entry = {
                "player_slug":        ps,
                "player_name":        row["player_name"],
                "position_agg":       row["position_agg"] or "SP",
                "in_season_eligible": row["in_season_eligible"],
                "category":           "SP",
                "nb_games":           _ng_sp7,
                "projected_score":    round(float(score), 1) if score is not None else None,
                "sorare_proj":        _sorare_proj7.get(ps),
                "ml_pred":            ml_d["pred_median"] if ml_d else None,
                "ctx_pred":           ctx_pred_sp,
                "bat_hand":           None,
                "opp_pitcher_hand":   None,
                "platoon_factor_C":   None,
                "park_factor":        ml_d.get("park_factor")        if ml_d else None,
                "weather_factor":     ml_d.get("weather_factor")     if ml_d else None,
                "opp_quality_factor": ml_d.get("opp_quality_factor") if ml_d else None,
                "home_away_factor":   ml_d.get("home_away_factor")   if ml_d else None,
                "day_night_factor":   ml_d.get("day_night_factor")   if ml_d else None,
                "rest_factor":        ml_d.get("rest_factor")        if ml_d else None,
                "G1":                 round(float(score), 1) if score is not None else None,
            }
            proj7.append(entry)

        df7 = pd.DataFrame(proj7)
        game_cols7 = (
            [f"G{i+1}" for i in range(max_games7) if f"G{i+1}" in df7.columns]
            if not df7.empty else []
        )

        _show_all7 = st.checkbox(
            "Charger les données de tous les joueurs", value=False, key="proj7_all"
        )
        if _show_all7 and not df_ml.empty:
            _already7 = set(df7["player_slug"]) if not df7.empty else set()
            _extra7   = []
            for _, _mr7 in df_ml.iterrows():
                _s7 = _mr7["player_slug"]
                if _s7 in _already7:
                    continue
                _pos7_raw = str(_mr7.get("position", ""))
                _pos7_agg = POSITION_AGG.get(_pos7_raw, POSITION_EXACT.get(_pos7_raw, _pos7_raw))
                _isp7     = _pos7_agg in ("SP", "RP")
                _ng7      = int(_mr7.get("n_games_gw") or 0)
                _mu7_     = float(_mr7["pred_median"] or 0)
                _mm7      = round(_mu7_ * _ng7, 1) if _ng7 > 0 else None
                _ctx7_raw = _mr7.get("pred_contextual")
                _ctx7_tot = (round(float(_ctx7_raw) * _ng7, 1)
                             if (_ctx7_raw is not None and not _math.isnan(float(_ctx7_raw)) and _ng7 > 0)
                             else None)
                _extra7.append({
                    "player_slug":        _s7,
                    "player_name":        _mr7["player_name"],
                    "position_agg":       _pos7_agg,
                    "in_season_eligible": None,
                    "category":           "SP" if _isp7 else "Hitter",
                    "nb_games":           _ng7,
                    "projected_score":    None,
                    "ml_pred":            _mm7,
                    "ctx_pred":           _ctx7_tot,
                    "bat_hand":           _mr7.get("bat_hand") if not _isp7 else None,
                    "opp_pitcher_hand":   _mr7.get("opp_pitcher_hand") if not _isp7 else None,
                    "platoon_factor_C":   _mr7.get("platoon_factor_C") if not _isp7 else None,
                    "park_factor":        _mr7.get("park_factor"),
                    "weather_factor":     _mr7.get("weather_factor"),
                    "opp_quality_factor": _mr7.get("opp_quality_factor"),
                    "home_away_factor":   _mr7.get("home_away_factor"),
                    "day_night_factor":   _mr7.get("day_night_factor"),
                    "rest_factor":        _mr7.get("rest_factor"),
                })
            if _extra7:
                df7 = pd.concat([df7, pd.DataFrame(_extra7)], ignore_index=True)

        st.markdown(
            f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
            f'<span class="title">GW{gw7} — Projections</span>'
            f'<span class="pill accent">ML + CTX</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        col7f1, col7f2, col7f3 = st.columns([2, 3, 4])
        with col7f1:
            show_cat7 = st.radio(
                "Catégorie", ["Hitter", "SP"],
                horizontal=True, key="proj7_cat",
            )
        with col7f2:
            _pos_opts7 = (
                ["CI", "MI", "OF"] if show_cat7 == "Hitter" else ["SP", "RP"]
            )
            sel_pos7 = st.multiselect(
                "Poste", _pos_opts7, default=_pos_opts7, key="proj7_pos",
            )
        with col7f3:
            sort_by7 = st.radio(
                "Trier par", ["Score historique", "Prédiction ML", "CTX", "Sorare proj."],
                horizontal=True, key="proj7_sort",
            )

        df7_f = df7[df7["category"] == show_cat7].copy() if not df7.empty else pd.DataFrame()
        if not df7_f.empty and sel_pos7:
            df7_f = df7_f[df7_f["position_agg"].isin(sel_pos7)]

        sort_map7 = {
            "Score historique": ("projected_score", False),
            "Prédiction ML":    ("ml_pred", False),
            "CTX":              ("ctx_pred", False),
            "Sorare proj.":     ("sorare_proj", False),
        }
        sort_col7, sort_asc7 = sort_map7[sort_by7]
        if not df7_f.empty:
            df7_f = df7_f.sort_values(sort_col7, ascending=sort_asc7, na_position="last")

        display_cols7 = (
            ["player_name", "position_agg", "in_season_eligible", "projected_score"]
            + game_cols7
            + ["sorare_proj", "ml_pred",
               "bat_hand", "opp_pitcher_hand", "platoon_factor_C",
               "park_factor", "weather_factor", "opp_quality_factor",
               "home_away_factor", "day_night_factor", "rest_factor", "ctx_pred"]
        )
        display_cols7 = [c for c in display_cols7 if not df7_f.empty and c in df7_f.columns]

        col_config7 = {
            "player_name":        st.column_config.TextColumn("Joueur"),
            "position_agg":       st.column_config.TextColumn("Poste"),
            "in_season_eligible": st.column_config.CheckboxColumn("In Season"),
            "projected_score":    st.column_config.NumberColumn("Score hist. GW", format="%.1f"),
            "sorare_proj":        st.column_config.NumberColumn("Sorare proj.", format="%.1f"),
            "ml_pred":            st.column_config.NumberColumn("ML pred.", format="%.1f"),
            "bat_hand":           st.column_config.TextColumn("Main"),
            "opp_pitcher_hand":   st.column_config.TextColumn("Pitcher(s)"),
            "platoon_factor_C":   st.column_config.NumberColumn("⚾ Platoon", format="%.3f"),
            "park_factor":        st.column_config.NumberColumn("🏟 Stade", format="%.2f"),
            "weather_factor":     st.column_config.NumberColumn("🌬 Météo", format="%.2f"),
            "opp_quality_factor": st.column_config.NumberColumn("⚔ Adv.", format="%.2f"),
            "home_away_factor":   st.column_config.NumberColumn("🏠 Dom.", format="%.2f"),
            "day_night_factor":   st.column_config.NumberColumn("☀ J/N", format="%.2f"),
            "rest_factor":        st.column_config.NumberColumn("💤 Repos", format="%.2f"),
            "ctx_pred":           st.column_config.NumberColumn("CTX", format="%.1f"),
        }
        for gc in game_cols7:
            col_config7[gc] = st.column_config.NumberColumn(gc, format="%.1f")

        st.dataframe(
            df7_f[display_cols7].reset_index(drop=True) if not df7_f.empty else pd.DataFrame(),
            use_container_width=True,
            hide_index=True,
            column_config=col_config7,
        )
        st.caption(f"{len(df7_f)} joueurs affichés")
