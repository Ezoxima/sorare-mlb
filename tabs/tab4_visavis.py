import streamlit as st
import pandas as pd

from data_loaders import (
    load_upcoming_pitchers, load_all_hitters_for_gw, load_matchup_stats,
    load_pitcher_stats, FENETRE_OPTIONS,
)


def render(ctx: dict) -> None:
    df_calendar = ctx["df_calendar"]
    sel_manager = ctx["sel_manager"]
    fenetre     = ctx["fenetre"]

    try:
        df_vv, vv_gw = load_upcoming_pitchers()
    except Exception as e:
        st.error(f"Impossible de charger les matchs : {e}")
        df_vv, vv_gw = pd.DataFrame(), 0

    if df_vv.empty:
        st.info("Aucun match programmé pour le prochain fixture CLASSIC.")
    else:
        st.markdown(
            f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
            f'<span class="title">GW{vv_gw} — Vis-à-vis</span>'
            f'<span class="pill accent">CLASSIC</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        gal_hitters = (
            df_calendar[
                (df_calendar["gallery_manager"] == sel_manager) &
                df_calendar["active_club_slug"].notna() &
                ~df_calendar["position_agg"].isin(["SP", "RP"])
            ]
            .drop_duplicates("player_slug")
        )
        gal_set    = set(gal_hitters["player_slug"])
        gal_is_map = gal_hitters.set_index("player_slug")["in_season_eligible"].to_dict()

        _gw_teams = tuple(set(
            df_vv["home_team_slug"].dropna().tolist() +
            df_vv["away_team_slug"].dropna().tolist()
        ))

        if "vv_all_loaded" not in st.session_state:
            st.session_state["vv_all_loaded"] = False
        _col_b, _col_reset = st.columns([4, 1])
        with _col_b:
            if not st.session_state["vv_all_loaded"]:
                if st.button("⬇️ Charger tous les joueurs", key="vv_load_all"):
                    st.session_state["vv_all_loaded"] = True
                    st.rerun()
            else:
                st.caption("✅ Tous les joueurs chargés")
        with _col_reset:
            if st.session_state["vv_all_loaded"]:
                if st.button("Ma galerie", key="vv_gal_only"):
                    st.session_state["vv_all_loaded"] = False
                    st.rerun()

        show_gallery_only = not st.session_state["vv_all_loaded"]

        if show_gallery_only:
            _hitters_df = (
                gal_hitters[["player_slug", "player_name", "active_club_slug", "position_agg"]]
                .rename(columns={"active_club_slug": "team_slug"})
                .copy()
            )
            _hitters_df["in_gallery"]         = True
            _hitters_df["in_season_eligible"] = _hitters_df["player_slug"].map(gal_is_map)
        else:
            _hitters_df = load_all_hitters_for_gw(_gw_teams)
            _hitters_df["in_gallery"]         = _hitters_df["player_slug"].isin(gal_set)
            _hitters_df["in_season_eligible"] = _hitters_df["player_slug"].map(gal_is_map)

        team_to_hitters: dict[str, list] = {}
        for _, h in _hitters_df.iterrows():
            team_to_hitters.setdefault(h["team_slug"], []).append(h.to_dict())

        matchup_list = []
        for _, g in df_vv.iterrows():
            for pitcher_slug, pitcher_name, hitter_team in [
                (g["home_pitcher_slug"], g["home_pitcher_name"], g["away_team_slug"]),
                (g["away_pitcher_slug"], g["away_pitcher_name"], g["home_team_slug"]),
            ]:
                if not pitcher_slug:
                    continue
                for h in team_to_hitters.get(hitter_team, []):
                    matchup_list.append({
                        "hitter_slug":  h["player_slug"],
                        "hitter_name":  h["player_name"],
                        "position_agg": h.get("position_agg", "?"),
                        "hitter_team":  hitter_team,
                        "pitcher_slug": pitcher_slug,
                        "pitcher_name": pitcher_name or pitcher_slug,
                        "in_gallery":   h.get("in_gallery", False),
                        "in_season":    h.get("in_season_eligible"),
                    })

        HIT_STATS = ["H", "HR", "K", "BB", "RBI", "SB"]
        PIT_STATS  = ["IP", "SO", "HA", "ER", "BB"]

        if matchup_list:
            p_slugs = tuple({m["pitcher_slug"] for m in matchup_list})
            h_slugs = tuple({m["hitter_slug"]  for m in matchup_list})
            df_mu   = load_matchup_stats(h_slugs, p_slugs)
            mu_idx: dict = {}
            for _, r in df_mu.iterrows():
                key = (r["hitter_slug"], r["pitcher_slug"])
                mu_idx.setdefault(key, {"_nb": 0, "_score": None})[r["stat_short_name"]] = r["avg_val"]
                mu_idx[key]["_nb"] = int(r["nb_matchs"])
                if pd.notna(r["avg_sorare_score"]):
                    mu_idx[key]["_score"] = float(r["avg_sorare_score"])

            df_pit_gen = load_pitcher_stats(p_slugs, FENETRE_OPTIONS[fenetre])
            pit_idx: dict = {}
            for _, r in df_pit_gen.iterrows():
                slug = r["player_slug"]
                pit_idx.setdefault(slug, {"_nb": 0, "_score": None})[r["stat_short_name"]] = r["avg_val"]
                pit_idx[slug]["_nb"] = int(r["nb_matchs"])
                _ps = r.get("avg_sorare_score")
                if _ps is not None and pd.notna(_ps):
                    pit_idx[slug]["_score"] = float(_ps)
        else:
            mu_idx, pit_idx = {}, {}

        st.markdown(
            '<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
            '<span class="title">Hitters</span><span class="pill">vs SP probable</span></div>',
            unsafe_allow_html=True,
        )
        hit_rows = []
        for m in matchup_list:
            hist = mu_idx.get((m["hitter_slug"], m["pitcher_slug"]), {})
            row = {
                "Hitter":          m["hitter_name"],
                "Poste":           m["position_agg"],
                "Équipe":          m["hitter_team"],
                "Pitcher adverse": m["pitcher_name"],
                "IS":              m["in_season"],
                "Galerie":         m["in_gallery"],
                "Nb matchs vs":    hist.get("_nb", 0),
                "Score moy":       hist.get("_score"),
            }
            for s in HIT_STATS:
                row[s] = hist.get(s)
            hit_rows.append(row)

        df_hit_table = (
            pd.DataFrame(hit_rows)
            .sort_values(["Galerie", "Score moy"], ascending=[False, False])
            .drop(columns=["Galerie"])
            .reset_index(drop=True)
        )
        st.dataframe(df_hit_table, use_container_width=True, hide_index=True)

        st.divider()

        st.markdown('<div class="divider-h"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
            '<span class="title">Pitchers</span></div>',
            unsafe_allow_html=True,
        )
        seen_pitchers: dict[str, str] = {}
        for m in matchup_list:
            seen_pitchers.setdefault(m["pitcher_slug"], m["pitcher_name"])

        pit_rows = []
        for slug, name in seen_pitchers.items():
            stats = pit_idx.get(slug, {})
            row = {
                "Pitcher":   name,
                "Nb matchs": stats.get("_nb", 0),
                "Score moy": stats.get("_score"),
            }
            for s in PIT_STATS:
                row[s] = stats.get(s)
            pit_rows.append(row)

        df_pit_table = pd.DataFrame(pit_rows).reset_index(drop=True)
        st.dataframe(df_pit_table, use_container_width=True, hide_index=True)
