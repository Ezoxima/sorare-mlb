from collections import Counter as _Counter
from datetime import datetime, timezone
import uuid

import streamlit as st
import pandas as pd

from data_loaders import (
    load_player_avg_scores, load_upcoming_pitchers, load_matchup_stats,
    load_saved_lineups, _persist_lineup,
    POSITION_AGG, POSITION_EXACT, RARITY_COLOR, FENETRE_OPTIONS,
)


def render(ctx: dict) -> None:
    df_prices       = ctx["df_prices"]
    df_ml           = ctx["df_ml"]
    sel_manager     = ctx["sel_manager"]
    fenetre         = ctx["fenetre"]
    _injured_slugs  = ctx["_injured_slugs"]
    _slug_name_map  = ctx["_slug_name_map"]

    _t8_comp, _t8_arena = st.tabs(["🏗️ Compétitions", "🏟️ Arena"])

    # ── Compétitions ─────────────────────────────────────────────────────────────

    with _t8_comp:
        _EMPTY_TEAM = lambda: {s: None for s in ["SP", "RP", "CI", "MI", "OF", "Flex", "Libre"]}
        _SLOT_POS   = {
            "SP":    ["SP"],
            "RP":    ["RP"],
            "CI":    ["CI"],
            "MI":    ["MI"],
            "OF":    ["OF"],
            "Flex":  ["CI", "MI", "OF"],
            "Libre": ["CI", "MI", "OF"],
        }
        _MAX_TEAMS  = {"Champions": 3, "Hot Streak": 10, "Challenger": 4}

        col_m8, col_r8 = st.columns([3, 4])
        with col_m8:
            tb_mode = st.radio(
                "Mode", ["Champions", "Hot Streak", "Challenger"],
                horizontal=True, key="tb_mode",
            )
        with col_r8:
            tb_rar = st.radio(
                "Rareté", ["Limited", "Rare", "Super Rare", "Unique"],
                horizontal=True, key="tb_rar",
            )

        tb_score_src = st.radio(
            "Indicateur de score",
            ["Auto (ML → Hist.)", "Sorare GW+"],
            horizontal=True,
            key="tb_score_src",
            help="Auto : prédiction ML si dispo, sinon moyenne historique ajustée matchup.\n"
                 "Sorare GW+ : score projeté par Sorare pour la prochaine GW Classic.",
        )

        _require_is = tb_mode in ("Champions", "Hot Streak")
        _max_t      = _MAX_TEAMS[tb_mode]

        _tb_sk = f"tb_teams_{tb_mode}_{tb_rar}"
        _DEFAULT_N_TEAMS_INIT = {"Champions": 3, "Hot Streak": 4, "Challenger": 4}
        if _tb_sk not in st.session_state:
            _n_init = _DEFAULT_N_TEAMS_INIT.get(tb_mode, 1)
            st.session_state[_tb_sk] = [_EMPTY_TEAM() for _ in range(_n_init)]
        tb_teams = st.session_state[_tb_sk]

        df_tb = (
            df_prices[
                (df_prices["gallery_manager"] == sel_manager) &
                (df_prices["card_display_rarity"].str.lower() == tb_rar.lower()) &
                ~df_prices["player_slug"].isin(_injured_slugs)
            ]
            .drop_duplicates("card_name")
            .copy()
        )
        df_tb["position_agg"]   = df_tb["card_display_position"].map(POSITION_AGG)
        df_tb["position_agg_2"] = df_tb["card_display_position_2"].map(POSITION_AGG) if "card_display_position_2" in df_tb.columns else None
        df_tb["is_eligible"]    = df_tb["in_season_eligible"] == True

        _all_gal_prices = df_prices[df_prices["gallery_manager"] == sel_manager]
        _all_gal_slugs  = tuple(_all_gal_prices["player_slug"].unique())
        _all_gal_h_slugs = tuple(
            _all_gal_prices[
                ~_all_gal_prices["card_display_position"].map(POSITION_AGG).isin(["SP", "RP"])
            ]["player_slug"].unique()
        )
        _avg_tb  = load_player_avg_scores(_all_gal_slugs, FENETRE_OPTIONS[fenetre])
        _smap_tb = _avg_tb.set_index("player_slug")["avg_score"].to_dict()
        _nbm_tb  = _avg_tb.set_index("player_slug")["nb_matchs"].to_dict()

        try:
            _df_p8, _tb_gw8 = load_upcoming_pitchers()
        except Exception:
            _df_p8, _tb_gw8 = pd.DataFrame(), 0

        _tsched8: dict = {}
        if not _df_p8.empty:
            _tsched8 = {}
            for _, _g8 in _df_p8.iterrows():
                if _g8["home_team_slug"]:
                    _tsched8.setdefault(_g8["home_team_slug"], []).append(
                        {"pitcher_slug": _g8["away_pitcher_slug"] or None}
                    )
                if _g8["away_team_slug"]:
                    _tsched8.setdefault(_g8["away_team_slug"], []).append(
                        {"pitcher_slug": _g8["home_pitcher_slug"] or None}
                    )
            _all_p8 = tuple({
                s for col in ("home_pitcher_slug", "away_pitcher_slug")
                for s in _df_p8[col].dropna()
            })
            _df_mu8 = (
                load_matchup_stats(_all_gal_h_slugs, _all_p8)
                if _all_gal_h_slugs and _all_p8 else pd.DataFrame()
            )
            _mu8: dict = {}
            for _, _r8 in _df_mu8.iterrows():
                if pd.notna(_r8["avg_sorare_score"]):
                    _mu8[(_r8["hitter_slug"], _r8["pitcher_slug"])] = float(_r8["avg_sorare_score"])

            def _gw_score8(player_slug, team_slug, position_agg) -> float:
                if position_agg in ("SP", "RP"):
                    return _smap_tb.get(player_slug, 0.0)
                games8 = _tsched8.get(team_slug, [])
                total8 = 0.0
                for _gm in games8:
                    ps = _gm["pitcher_slug"]
                    sc = (_mu8.get((player_slug, ps)) if ps else None) or _smap_tb.get(player_slug)
                    if sc:
                        total8 += sc
                return round(total8, 1) if games8 else _smap_tb.get(player_slug, 0.0)

            df_tb["proj_score_hist"] = df_tb.apply(
                lambda r: _gw_score8(r["player_slug"], r["active_club_slug"], r["position_agg"]),
                axis=1,
            )
        else:
            df_tb["proj_score_hist"] = df_tb["player_slug"].map(_smap_tb).fillna(0.0)

        _tsched8_len = {t: len(g) for t, g in _tsched8.items()}

        if not df_ml.empty:
            _ml8 = (
                df_ml[df_ml["gallery_manager"] == sel_manager]
                .drop_duplicates("player_slug")
                .set_index("player_slug")["pred_contextual"]
            )

            def _ml_gw_score8(player_slug, team_slug, position_agg):
                ml = _ml8.get(player_slug)
                if ml is None:
                    return None
                if position_agg in ("SP", "RP"):
                    return round(float(ml), 1)
                nb = _tsched8_len.get(team_slug, 1)
                return round(float(ml) * nb, 1)

            df_tb["proj_score_ml"] = df_tb.apply(
                lambda r: _ml_gw_score8(r["player_slug"], r["active_club_slug"], r["position_agg"]),
                axis=1,
            )
            df_tb["proj_score"] = df_tb["proj_score_ml"].combine_first(df_tb["proj_score_hist"])
        else:
            df_tb["proj_score_ml"] = None
            df_tb["proj_score"]    = df_tb["proj_score_hist"]

        _sorare_gw = pd.to_numeric(df_tb.get("next_gw_projected_score", pd.Series(dtype=float)), errors="coerce")
        df_tb["proj_score_sorare"] = _sorare_gw

        if tb_score_src == "Sorare GW+":
            _base_score = _sorare_gw.fillna(0.0)
        else:
            _base_score = pd.to_numeric(df_tb["proj_score"], errors="coerce").fillna(0.0)

        _power_num = pd.to_numeric(df_tb["card_power"], errors="coerce").fillna(1.0)
        df_tb["proj_score_eff"] = (_base_score * _power_num).round(1)
        df_tb["proj_score_eff_auto"]   = (pd.to_numeric(df_tb["proj_score"],        errors="coerce").fillna(0.0) * _power_num).round(1)
        df_tb["proj_score_eff_sorare"] = (pd.to_numeric(df_tb["proj_score_sorare"], errors="coerce").fillna(0.0) * _power_num).round(1)

        if _tsched8:
            _probable_sp_slugs = {
                g["pitcher_slug"]
                for games in _tsched8.values()
                for g in games
                if g["pitcher_slug"]
            }
            _is_sp = df_tb["position_agg"] == "SP"
            df_tb = df_tb[~_is_sp | df_tb["player_slug"].isin(_probable_sp_slugs)].reset_index(drop=True)

        df_tb["nb_matchs"]   = df_tb["player_slug"].map(_nbm_tb).fillna(0).astype(int)
        df_tb["nb_games_gw"] = df_tb.apply(
            lambda r: 1 if r["position_agg"] == "SP"
                      else _tsched8_len.get(r["active_club_slug"], 0),
            axis=1,
        )

        _cl = df_tb.set_index("card_name").to_dict("index")

        def _fmt_opt(x: str) -> str:
            if x == "—":
                return "—"
            r    = _cl.get(x, {})
            pos  = r.get("position_exact") or "?"
            is_  = "IS" if r.get("is_eligible") else "OOS"
            try:
                sc = float(r.get("proj_score_eff") or r.get("proj_score") or 0.0)
            except (TypeError, ValueError):
                sc = 0.0
            try:
                pwr = float(r.get("card_power") or 1.0)
            except (TypeError, ValueError):
                pwr = 1.0
            ng = int(r.get("nb_games_gw") or 0)
            if tb_score_src == "Sorare GW+":
                src = "SOR" if r.get("proj_score_sorare") is not None else "—"
            else:
                src = "ML" if r.get("proj_score_ml") is not None else "~"
            return f"{x}  [{pos} · {is_} · {sc:.0f} pts eff. · ×{pwr:.3f} · {ng}G · {src}]"

        def _tb_suggest(other_used: set, other_used_slugs: set, require_is: bool,
                        score_col: str = "proj_score_eff",
                        slot_pos: dict | None = None,
                        df_pool: pd.DataFrame | None = None,
                        locked: dict | None = None) -> dict:
            _df      = df_pool if df_pool is not None else df_tb
            _spos    = slot_pos if slot_pos is not None else _SLOT_POS
            _locked  = locked or {}
            is_map   = _df.set_index("card_name")["is_eligible"].to_dict()
            slug_map = _df.set_index("card_name")["player_slug"].to_dict()

            _eff_col  = score_col if score_col in _df.columns else "proj_score_eff"
            _locked_cards = {c for c in _locked.values() if c}
            _locked_slugs = {slug_map.get(c, "") for c in _locked_cards}

            def _fill_is(pre_filled: dict, excl_cards: set, excl_slugs: set) -> dict:
                res       = dict(pre_filled)
                _used     = {c for c in res.values() if c}
                _u_slugs  = {slug_map.get(c, "") for c in _used}
                for sname, valid_pos in _spos.items():
                    if sname in res:
                        continue
                    cands_all = _df[
                        (_df["position_agg"].isin(valid_pos) | _df["position_agg_2"].isin(valid_pos)) &
                        ~_df["card_name"].isin(excl_cards | _used) &
                        ~_df["player_slug"].isin(excl_slugs | _u_slugs)
                    ]
                    if cands_all.empty:
                        res[sname] = None
                        continue
                    if require_is:
                        cands_is = cands_all[cands_all["is_eligible"]]
                        cands = (cands_is if not cands_is.empty else cands_all).sort_values(_eff_col, ascending=False)
                    else:
                        cands = cands_all.sort_values(_eff_col, ascending=False)
                    res[sname] = cands.iloc[0]["card_name"]
                    _used.add(res[sname])
                    _u_slugs.add(slug_map.get(res[sname], ""))
                return res

            result = _fill_is(dict(_locked), other_used, other_used_slugs)

            if require_is:
                is_p1 = sum(1 for c in result.values() if c and is_map.get(c, False))
                if is_p1 > 6:
                    score_map = _df.set_index("card_name")[_eff_col].to_dict()

                    def _team_score(t: dict) -> float:
                        return sum(score_map.get(c, 0.0) for c in t.values() if c)

                    best_score = _team_score(result)
                    best_team  = result

                    for sname, valid_pos in _spos.items():
                        if sname in _locked:
                            continue
                        non_is_c = _df[
                            (_df["position_agg"].isin(valid_pos) | _df["position_agg_2"].isin(valid_pos)) &
                            ~_df["card_name"].isin(other_used | _locked_cards) &
                            ~_df["player_slug"].isin(other_used_slugs | _locked_slugs) &
                            ~_df["is_eligible"]
                        ].sort_values(_eff_col, ascending=False)
                        if non_is_c.empty:
                            continue
                        ni_card = non_is_c.iloc[0]["card_name"]
                        pre   = {**_locked, sname: ni_card}
                        excl  = other_used | {ni_card}
                        excl_sl = other_used_slugs | {slug_map.get(ni_card, "")}
                        candidate = _fill_is(pre, excl, excl_sl)
                        sc = _team_score(candidate)
                        if sc > best_score:
                            best_score = sc
                            best_team  = candidate

                    result = best_team

            return result

        def _team_validation(team: dict) -> tuple:
            cards = [v for v in team.values() if v]
            if not cards:
                return 0, 0, 0.0, 0
            is_c   = sum(1 for c in cards if _cl.get(c, {}).get("is_eligible", False))
            clubs  = [_cl.get(c, {}).get("active_club_slug", "") for c in cards]
            max_cl = max(_Counter(clubs).values()) if clubs else 0
            score  = sum(float(_cl.get(c, {}).get("proj_score_eff") or 0.0) for c in cards)
            return is_c, max_cl, score, len(cards)

        col_a8, col_d8, col_r8 = st.columns([2, 3, 2])
        with col_a8:
            if len(tb_teams) < _max_t:
                if st.button("➕ Ajouter une équipe", key="tb_add"):
                    tb_teams.append(_EMPTY_TEAM())
                    st.rerun()
        with col_d8:
            if len(tb_teams) > 1:
                _del_opts = [f"Équipe {i+1}" for i in range(len(tb_teams))]
                _del_sel  = st.selectbox(
                    "Supprimer", _del_opts, key="tb_del_sel",
                    label_visibility="collapsed",
                )
                if st.button("🗑️ Supprimer cette équipe", key="tb_del"):
                    tb_teams.pop(int(_del_sel.split()[-1]) - 1)
                    st.rerun()
        with col_r8:
            if st.button("🧹 Tout réinitialiser", key="tb_reset_all"):
                n = len(tb_teams)
                st.session_state[_tb_sk] = [_EMPTY_TEAM() for _ in range(n)]
                for _i in range(n):
                    for _sl in _SLOT_POS:
                        st.session_state[f"tb_{tb_mode}_{tb_rar}_{_i}_{_sl}"] = "—"
                    st.session_state[f"tb_locks_{_i}"] = set()
                st.rerun()

        st.divider()

        _global_card_slug = (
            df_prices[df_prices["gallery_manager"] == sel_manager]
            .drop_duplicates("card_name")
            .set_index("card_name")["player_slug"]
            .to_dict()
        )

        for _ti, _team in enumerate(tb_teams):
            _all_used_cards = {
                c
                for key, teams in st.session_state.items()
                if (key.startswith("tb_teams_") or key.startswith("ar9_teams_")) and isinstance(teams, list)
                for t in teams
                for c in t.values()
                if c
            }
            _other_used = _all_used_cards - {v for v in tb_teams[_ti].values() if v}

            _locks_key = f"tb_locks_{_ti}"
            if _locks_key not in st.session_state:
                st.session_state[_locks_key] = set()
            _locks = st.session_state[_locks_key]

            with st.expander(f"Équipe {_ti + 1}", expanded=True):
                _cs, _cc, _cul = st.columns([2, 2, 2])
                with _cs:
                    if st.button("✨ Suggérer l'équipe", key=f"tb_sug_{_ti}"):
                        _locked_cards = {s: tb_teams[_ti].get(s) for s in _locks if tb_teams[_ti].get(s)}
                        _sug = _tb_suggest(_other_used, set(), _require_is, locked=_locked_cards)
                        tb_teams[_ti] = _sug
                        for _sl, _cn in _sug.items():
                            if _sl not in _locks:
                                st.session_state[f"tb_{tb_mode}_{tb_rar}_{_ti}_{_sl}"] = _cn if _cn is not None else "—"
                        st.rerun()
                with _cc:
                    if st.button("🗑️ Vider", key=f"tb_clr_{_ti}"):
                        tb_teams[_ti] = _EMPTY_TEAM()
                        st.session_state[_locks_key] = set()
                        for _sl in _SLOT_POS:
                            st.session_state[f"tb_{tb_mode}_{tb_rar}_{_ti}_{_sl}"] = "—"
                        st.rerun()
                with _cul:
                    if _locks and st.button("🔓 Déverrouiller tout", key=f"tb_unlock_{_ti}"):
                        st.session_state[_locks_key] = set()
                        st.rerun()

                _col_l, _col_r = st.columns(2)
                for _si, (_sname, _vpos) in enumerate(_SLOT_POS.items()):
                    _col = _col_l if _si < 4 else _col_r
                    with _col:
                        _in_team_used  = {v for k, v in _team.items() if v and k != _sname}
                        _in_team_slugs = {_global_card_slug[c] for c in _in_team_used if c in _global_card_slug}
                        _blocked_slugs = _in_team_slugs
                        _pos_match = df_tb["position_agg"].isin(_vpos) | df_tb["position_agg_2"].isin(_vpos)
                        _cands = (
                            df_tb[
                                _pos_match &
                                ~df_tb["card_name"].isin(_other_used | _in_team_used) &
                                ~df_tb["player_slug"].isin(_blocked_slugs)
                            ]
                            .sort_values("proj_score_eff", ascending=False)
                        )
                        _opts    = ["—"] + _cands["card_name"].tolist()
                        _current = _team.get(_sname)
                        if _current and _current not in _opts:
                            _opts.insert(1, _current)
                        # Fix widget key collision : inclure mode + rareté dans la clé
                        _wkey = f"tb_{tb_mode}_{tb_rar}_{_ti}_{_sname}"
                        if _wkey not in st.session_state:
                            st.session_state[_wkey] = _current if (_current and _current in _opts) else "—"

                        _is_locked = _sname in _locks
                        _lock_icon = " 🔒" if _is_locked else ""
                        _slot_label = (
                            f"**{_sname}{_lock_icon}**"
                            + (" *(CI/MI/OF)*" if _sname in ("Flex", "Libre") else "")
                        )

                        def _on_slot_change(_s=_sname, _lk=_locks_key):
                            st.session_state[_lk].add(_s)

                        _chosen = st.selectbox(
                            _slot_label,
                            _opts,
                            key=_wkey,
                            format_func=_fmt_opt,
                            on_change=_on_slot_change,
                        )
                        tb_teams[_ti][_sname] = _chosen if _chosen != "—" else None

                _is_c, _max_cl, _sc, _nf = _team_validation(tb_teams[_ti])
                if _nf > 0:
                    _is_ok  = not _require_is or _is_c >= 6
                    _cl_ok  = _max_cl <= 6
                    _is_clr = "#22c55e" if _is_ok  else "#ef4444"
                    _cl_clr = "#22c55e" if _cl_ok  else "#ef4444"
                    _is_ico = "✅" if _is_ok  else "⚠️"
                    _cl_ico = "✅" if _cl_ok  else "⚠️"
                    _is_req = " (min 6 requis)" if _require_is else ""
                    st.markdown(
                        f'<div style="display:flex;gap:16px;flex-wrap:wrap;'
                        f'margin-top:10px;padding:8px 12px;'
                        f'background:rgba(255,255,255,0.03);border-radius:8px;'
                        f'font-size:0.82rem">'
                        f'<span style="color:{_is_clr}">{_is_ico} IS : {_is_c}/7{_is_req}</span>'
                        f'<span style="color:{_cl_clr}">{_cl_ico} Club max : {_max_cl}/6</span>'
                        f'<span style="color:#4CAF50">⚾ Score eff. (×power) : <b>{_sc:.1f}</b> pts</span>'
                        f'<span style="opacity:0.45">{_nf}/7 slots remplis</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                _img_cols = st.columns(7)
                for (_sn, _), _icol in zip(_SLOT_POS.items(), _img_cols):
                    _cn = tb_teams[_ti].get(_sn)
                    _img_url = _cl.get(_cn or "", {}).get("picture_url")
                    with _icol:
                        if _img_url:
                            st.image(_img_url, caption=_sn, use_container_width=True)
                        else:
                            _rarity_c = RARITY_COLOR.get(
                                (_cl.get(_cn or "", {}).get("card_display_rarity") or "").lower(), "#555"
                            )
                            st.markdown(
                                f'<div style="height:90px;border:1px dashed rgba(128,128,128,0.3);'
                                f'border-radius:8px;display:flex;align-items:center;'
                                f'justify-content:center;font-size:0.7rem;opacity:0.4">'
                                f'{_sn}</div>',
                                unsafe_allow_html=True,
                            )

                st.divider()
                _sv_col1, _sv_col2 = st.columns([2, 3])
                with _sv_col1:
                    _sv_disabled = _nf == 0
                    if st.button(
                        f"💾 Sauvegarder (GW{_tb_gw8})" if _tb_gw8 else "💾 Sauvegarder",
                        key=f"tb_save_{_ti}",
                        disabled=_sv_disabled,
                        help="Aucun joueur dans l'équipe." if _sv_disabled else "Sauvegarde l'équipe pour comparer avec les résultats réels.",
                    ):
                        def _slot_data(card, eff_col="proj_score_eff"):
                            if not card:
                                return None
                            r = _cl.get(card, {})
                            return {
                                "card_name":      card,
                                "player_slug":    r.get("player_slug"),
                                "player_name":    _slug_name_map.get(r.get("player_slug", ""), card),
                                "picture_url":    r.get("picture_url"),
                                "proj_score_eff": r.get(eff_col),
                                "proj_score":     r.get("proj_score"),
                                "card_power":     r.get("card_power"),
                            }

                        _saved_ctx = [
                            l for l in load_saved_lineups()
                            if l.get("manager") == sel_manager
                            and l.get("gw_int") == _tb_gw8
                            and l.get("mode") == tb_mode
                            and l.get("rarity") == tb_rar
                        ]
                        _saved_auto_used = {
                            sd["card_name"]
                            for l in _saved_ctx
                            for sd in (l.get("suggested_slots_auto") or {}).values()
                            if sd and sd.get("card_name")
                        }
                        _saved_sorare_used = {
                            sd["card_name"]
                            for l in _saved_ctx
                            for sd in (l.get("suggested_slots_sorare") or {}).values()
                            if sd and sd.get("card_name")
                        }
                        _sug_auto   = _tb_suggest(_other_used | _saved_auto_used,   set(), _require_is, score_col="proj_score_eff_auto")
                        _sug_sorare = _tb_suggest(_other_used | _saved_sorare_used, set(), _require_is, score_col="proj_score_eff_sorare")

                        _entry = {
                            "lineup_id":              str(uuid.uuid4()),
                            "saved_at":               datetime.now(timezone.utc).isoformat(),
                            "gw_int":                 int(_tb_gw8),
                            "manager":                sel_manager,
                            "mode":                   tb_mode,
                            "rarity":                 tb_rar,
                            "score_src":              tb_score_src,
                            "slots":                  {s: _slot_data(c) for s, c in tb_teams[_ti].items()},
                            "suggested_slots_auto":   {s: _slot_data(c, "proj_score_eff_auto")   for s, c in _sug_auto.items()},
                            "suggested_slots_sorare": {s: _slot_data(c, "proj_score_eff_sorare") for s, c in _sug_sorare.items()},
                        }
                        _persist_lineup(_entry)
                        st.success(f"Équipe sauvegardée pour la GW{_tb_gw8} !")

    # ── Arena ─────────────────────────────────────────────────────────────────────

    with _t8_arena:
        _AL_SLUGS9 = frozenset({
            "oakland-athletics", "baltimore-orioles", "boston-red-sox",
            "chicago-white-sox", "cleveland-guardians", "detroit-tigers",
            "houston-astros", "kansas-city-royals", "los-angeles-angels",
            "minnesota-twins", "new-york-yankees", "seattle-mariners",
            "tampa-bay-rays", "texas-rangers",
        })
        _NL_SLUGS9 = frozenset({
            "arizona-diamondbacks", "atlanta-braves", "chicago-cubs",
            "cincinnati-reds", "colorado-rockies", "los-angeles-dodgers",
            "miami-marlins", "milwaukee-brewers", "new-york-mets",
            "philadelphia-phillies", "pittsburgh-pirates", "san-diego-padres",
            "san-francisco-giants", "st-louis-cardinals",
        })
        _SLOTS_7_AR9 = {
            "SP": ["SP"], "RP": ["RP"], "CI": ["CI"], "MI": ["MI"], "OF": ["OF"],
            "Hitter": ["CI", "MI", "OF"],
            "Libre":  ["CI", "MI", "OF"],
        }
        _SLOTS_S2_AR9 = {
            "SP1": ["SP"], "SP2": ["SP"],
            "H1": ["CI", "MI", "OF"], "H2": ["CI", "MI", "OF"], "H3": ["CI", "MI", "OF"],
        }
        _SLOTS_S5_AR9 = {f"H{i}": ["CI", "MI", "OF"] for i in range(1, 6)}
        _ARENA_DEFS9 = {
            "Standard":         {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": None,     "n": 7},
            "Beginner":         {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": None,     "n": 7},
            "Elite":            {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": None,     "n": 7},
            "American (AL)":    {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": "AL",     "n": 7},
            "National (NL)":    {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": "NL",     "n": 7},
            "OG (2022)":        {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": "OG",     "n": 7},
            "Legacy (2023-24)": {"slots": _SLOTS_7_AR9,  "max_club": 6, "filter": "Legacy", "n": 7},
            "Sandlot 2SP+3H":   {"slots": _SLOTS_S2_AR9, "max_club": 4, "filter": None,     "n": 5},
            "Sandlot 5H":       {"slots": _SLOTS_S5_AR9, "max_club": 4, "filter": None,     "n": 5},
        }

        _ar9c1, _ar9c2, _ar9c3 = st.columns([3, 2, 2])
        with _ar9c1:
            _ar9_type = st.selectbox("Type d'Arena", list(_ARENA_DEFS9.keys()), key="ar9_type")
        with _ar9c2:
            _ar9_rar = st.radio("Rareté", ["Limited", "Rare", "Super Rare", "Unique"],
                                horizontal=True, key="ar9_rar")
        with _ar9c3:
            _ar9_ssrc = st.radio("Score", ["Auto (ML → Hist.)", "Sorare GW+"],
                                 horizontal=True, key="ar9_ssrc")

        _ar9d    = _ARENA_DEFS9[_ar9_type]
        _ar9_sl  = _ar9d["slots"]
        _ar9_mc  = _ar9d["max_club"]
        _ar9_flt = _ar9d["filter"]
        _ar9_n   = _ar9d["n"]

        _df_ar9 = (
            df_prices[
                (df_prices["gallery_manager"] == sel_manager) &
                (df_prices["card_display_rarity"].str.lower() == _ar9_rar.lower()) &
                ~df_prices["player_slug"].isin(_injured_slugs)
            ]
            .drop_duplicates("card_name")
            .copy()
        )
        _df_ar9["position_agg"]   = _df_ar9["card_display_position"].map(POSITION_AGG)
        _df_ar9["position_agg_2"] = _df_ar9["card_display_position_2"].map(POSITION_AGG) if "card_display_position_2" in _df_ar9.columns else None
        _df_ar9["is_eligible"]    = _df_ar9["in_season_eligible"] == True

        if _ar9_flt == "AL":
            _df_ar9 = _df_ar9[_df_ar9["active_club_slug"].isin(_AL_SLUGS9)]
        elif _ar9_flt == "NL":
            _df_ar9 = _df_ar9[_df_ar9["active_club_slug"].isin(_NL_SLUGS9)]
        elif _ar9_flt == "OG":
            _df_ar9 = _df_ar9[_df_ar9["card_name"].str.contains("2022-23", na=False, regex=False)]
        elif _ar9_flt == "Legacy":
            _df_ar9 = _df_ar9[
                _df_ar9["card_name"].str.contains("2023-24", na=False, regex=False) |
                _df_ar9["card_name"].str.contains("2024-25", na=False, regex=False)
            ]

        if not df_ml.empty:
            _ml_ngw = (
                df_ml[df_ml["gallery_manager"] == sel_manager]
                .drop_duplicates("player_slug")
                .set_index("player_slug")["n_games_gw"]
            )
            _df_ar9["_n_games_gw"] = _df_ar9["player_slug"].map(_ml_ngw)
            _df_ar9 = _df_ar9[_df_ar9["_n_games_gw"].isna() | (_df_ar9["_n_games_gw"] > 0)]

        _ar9_pwr = pd.to_numeric(_df_ar9["card_power"], errors="coerce").fillna(1.0)
        if not df_ml.empty:
            _ml_ar9 = (
                df_ml[df_ml["gallery_manager"] == sel_manager]
                .drop_duplicates("player_slug")
                .set_index("player_slug")["pred_contextual"]
            )
            _df_ar9["_ml_val"] = _df_ar9["player_slug"].map(_ml_ar9)
        else:
            _df_ar9["_ml_val"] = None

        _ar9_slugs = tuple(_df_ar9["player_slug"].unique())
        _ar9_avg   = load_player_avg_scores(_ar9_slugs, FENETRE_OPTIONS[fenetre]) if _ar9_slugs else pd.DataFrame()
        _ar9_smap  = _ar9_avg.set_index("player_slug")["avg_score"].to_dict() if not _ar9_avg.empty else {}

        _ar9_ngw_raw = (
            _df_ar9["_n_games_gw"].fillna(1.0)
            if "_n_games_gw" in _df_ar9.columns
            else pd.Series(1.0, index=_df_ar9.index)
        )
        _ar9_is_pitcher = _df_ar9["position_agg"].isin(["SP", "RP"])
        _ar9_ngw = _ar9_ngw_raw.where(~_ar9_is_pitcher, other=1.0)

        _df_ar9["proj_score_hist"]   = (_df_ar9["player_slug"].map(_ar9_smap).fillna(0.0) * _ar9_ngw).round(1)
        _df_ar9["proj_score_auto"]   = (
            pd.to_numeric(_df_ar9["_ml_val"], errors="coerce").multiply(_ar9_ngw)
            .combine_first(_df_ar9["proj_score_hist"])
        )
        _df_ar9["proj_score_sorare"] = pd.to_numeric(
            _df_ar9.get("next_gw_projected_score", pd.Series(dtype=float)), errors="coerce"
        )
        _ar9_base = (
            _df_ar9["proj_score_sorare"].fillna(0.0) if _ar9_ssrc == "Sorare GW+"
            else _df_ar9["proj_score_auto"].fillna(0.0)
        )
        _df_ar9["proj_score_eff"] = _ar9_base.round(1)
        _cl_ar9 = _df_ar9.set_index("card_name").to_dict("index")

        def _fmt_opt_ar9(x: str) -> str:
            if x == "—":
                return "—"
            r = _cl_ar9.get(x, {})
            pos = POSITION_EXACT.get(r.get("card_display_position", ""), "?")
            try:
                sc = float(r.get("proj_score_eff") or 0.0)
            except (TypeError, ValueError):
                sc = 0.0
            return f"{x}  [{pos} · {sc:.0f} pts]"

        _EMPTY_AR9  = lambda: {s: None for s in _ar9_sl}
        _ar9_lk     = f"ar9_teams_{_ar9_type}_{_ar9_rar}"
        _ar9_tik    = f"ar9_ti_{_ar9_type}_{_ar9_rar}"

        _ar9_old_sk = f"arena_{_ar9_type}_{_ar9_rar}"
        if _ar9_old_sk in st.session_state and _ar9_lk not in st.session_state:
            st.session_state[_ar9_lk] = [st.session_state.pop(_ar9_old_sk)]

        if _ar9_lk not in st.session_state:
            st.session_state[_ar9_lk] = [_EMPTY_AR9()]
        ar9_teams = st.session_state[_ar9_lk]
        for _t in ar9_teams:
            for _s in _ar9_sl:
                _t.setdefault(_s, None)
            for _s in list(_t.keys()):
                if _s not in _ar9_sl:
                    del _t[_s]

        if _ar9_tik not in st.session_state or st.session_state[_ar9_tik] >= len(ar9_teams):
            st.session_state[_ar9_tik] = 0
        _ar9_ti   = st.session_state[_ar9_tik]
        _ar9_team = ar9_teams[_ar9_ti]

        if _df_ar9.empty:
            st.warning(f"Aucune carte {_ar9_rar} disponible pour cette arena.")
        else:
            _ar9_global_slug = (
                df_prices[df_prices["gallery_manager"] == sel_manager]
                .drop_duplicates("card_name")
                .set_index("card_name")["player_slug"]
                .to_dict()
            )

            _ar9_nav_cols = st.columns([1] * len(ar9_teams) + [0.6, 0.6])
            for _ni, _tc in enumerate(ar9_teams):
                _nc9 = sum(1 for v in _tc.values() if v)
                _lbl = f"Lineup {_ni + 1}" + (f" ({_nc9}/{_ar9_n})" if _nc9 else "")
                _act = _ni == _ar9_ti
                with _ar9_nav_cols[_ni]:
                    if st.button(_lbl, key=f"ar9_tab_{_ar9_type}_{_ar9_rar}_{_ni}",
                                 type="primary" if _act else "secondary", use_container_width=True):
                        st.session_state[_ar9_tik] = _ni
                        st.rerun()
            with _ar9_nav_cols[-2]:
                if st.button("➕", key=f"ar9_add_{_ar9_type}_{_ar9_rar}", use_container_width=True,
                             help="Ajouter une lineup"):
                    ar9_teams.append(_EMPTY_AR9())
                    st.session_state[_ar9_tik] = len(ar9_teams) - 1
                    st.rerun()
            with _ar9_nav_cols[-1]:
                _can_del = len(ar9_teams) > 1
                if st.button("➖", key=f"ar9_del_{_ar9_type}_{_ar9_rar}", use_container_width=True,
                             help="Supprimer cette lineup", disabled=not _can_del):
                    ar9_teams.pop(_ar9_ti)
                    st.session_state[_ar9_tik] = max(0, _ar9_ti - 1)
                    st.rerun()

            _ar9_used_comp = {
                c
                for key, teams in st.session_state.items()
                if (key.startswith("tb_teams_") or (key.startswith("ar9_teams_") and key != _ar9_lk))
                and isinstance(teams, list)
                for t in teams
                for c in t.values()
                if c
            }
            _ar9_other_used = _ar9_used_comp | {
                c for _ni, _tc in enumerate(ar9_teams)
                if _ni != _ar9_ti
                for c in _tc.values() if c
            }
            _ar9_other_slugs = {s for c in _ar9_other_used if (s := _ar9_global_slug.get(c)) and s}
            _ar9_other_slugs |= set(
                _df_ar9.loc[_df_ar9["card_name"].isin(_ar9_other_used), "player_slug"].dropna()
            )

            _df_ar9_suggest = _df_ar9[
                ~_df_ar9["card_name"].isin(_ar9_other_used) &
                ~_df_ar9["player_slug"].isin(_ar9_other_slugs)
            ]

            _ar9_btn1, _ar9_btn2 = st.columns([2, 2])
            with _ar9_btn1:
                if st.button("✨ Suggérer l'équipe", key=f"ar9_sug_{_ar9_ti}"):
                    _sug_ar9 = _tb_suggest(set(), set(), False,
                                           score_col="proj_score_eff",
                                           slot_pos=_ar9_sl,
                                           df_pool=_df_ar9_suggest)
                    ar9_teams[_ar9_ti] = _sug_ar9
                    for sl, cn in _sug_ar9.items():
                        st.session_state[f"ar9s_{_ar9_type}_{_ar9_rar}_{_ar9_ti}_{sl}"] = cn if cn else "—"
                    st.rerun()
            with _ar9_btn2:
                if st.button("🗑️ Vider", key=f"ar9_clr_{_ar9_ti}"):
                    ar9_teams[_ar9_ti] = _EMPTY_AR9()
                    for sl in _ar9_sl:
                        st.session_state[f"ar9s_{_ar9_type}_{_ar9_rar}_{_ar9_ti}_{sl}"] = "—"
                    st.rerun()

            _half_ar9 = (len(_ar9_sl) + 1) // 2
            _col_la9, _col_ra9 = st.columns(2)
            for _si9, (_sn9, _vp9) in enumerate(_ar9_sl.items()):
                _col9 = _col_la9 if _si9 < _half_ar9 else _col_ra9
                with _col9:
                    _in_used9  = {v for k, v in _ar9_team.items() if v and k != _sn9}
                    _in_slugs9 = {_ar9_global_slug[c] for c in _in_used9 if c in _ar9_global_slug}
                    _cands9 = (
                        _df_ar9[
                            (_df_ar9["position_agg"].isin(_vp9) | _df_ar9["position_agg_2"].isin(_vp9)) &
                            ~_df_ar9["card_name"].isin(_in_used9 | _ar9_other_used) &
                            ~_df_ar9["player_slug"].isin(_in_slugs9 | _ar9_other_slugs)
                        ]
                        .sort_values("proj_score_eff", ascending=False)
                    )
                    _opts9 = ["—"] + _cands9["card_name"].tolist()
                    _cur9  = _ar9_team.get(_sn9)
                    if _cur9 and _cur9 not in _opts9:
                        _opts9.insert(1, _cur9)
                    _wkey9 = f"ar9s_{_ar9_type}_{_ar9_rar}_{_ar9_ti}_{_sn9}"
                    if _wkey9 not in st.session_state:
                        st.session_state[_wkey9] = _cur9 if (_cur9 and _cur9 in _opts9) else "—"
                    _chosen9 = st.selectbox(
                        f"**{_sn9}**",
                        _opts9,
                        key=_wkey9,
                        format_func=_fmt_opt_ar9,
                    )
                    _ar9_team[_sn9] = _chosen9 if _chosen9 != "—" else None

            _cards9 = [v for v in _ar9_team.values() if v]
            _nf9    = len(_cards9)
            if _nf9 > 0:
                _clubs9 = [_cl_ar9.get(c, {}).get("active_club_slug", "") for c in _cards9]
                _mc9    = max(_Counter(_clubs9).values()) if _clubs9 else 0
                _sc9    = sum(float(_cl_ar9.get(c, {}).get("proj_score_eff") or 0.0) for c in _cards9)
                _mc_ok9 = _mc9 <= _ar9_mc
                _mc_clr = "#22c55e" if _mc_ok9 else "#ef4444"
                _mc_ico = "✅" if _mc_ok9 else "⚠️"
                st.markdown(
                    f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;padding:8px 12px;'
                    f'background:rgba(255,255,255,0.03);border-radius:8px;font-size:0.82rem">'
                    f'<span style="color:{_mc_clr}">{_mc_ico} Club max : {_mc9}/{_ar9_mc}</span>'
                    f'<span style="color:#4CAF50">⚾ Score : <b>{_sc9:.1f}</b> pts</span>'
                    f'<span style="opacity:0.45">{_nf9}/{_ar9_n} slots remplis</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            _img9_cols = st.columns(_ar9_n)
            for (_sna9, _), _icl9 in zip(_ar9_sl.items(), _img9_cols):
                _cn9  = _ar9_team.get(_sna9)
                _img9 = _cl_ar9.get(_cn9 or "", {}).get("picture_url")
                with _icl9:
                    if _img9:
                        st.image(_img9, caption=_sna9, use_container_width=True)
                    else:
                        st.markdown(
                            f'<div style="height:90px;border:1px dashed rgba(128,128,128,0.3);'
                            f'border-radius:8px;display:flex;align-items:center;'
                            f'justify-content:center;font-size:0.7rem;opacity:0.4">{_sna9}</div>',
                            unsafe_allow_html=True,
                        )

            st.divider()
            _sv9_dis = _nf9 == 0
            try:
                _, _ar9_gw = load_upcoming_pitchers()
            except Exception:
                _ar9_gw = 0
            if st.button(
                f"💾 Sauvegarder (GW{_ar9_gw})" if _ar9_gw else "💾 Sauvegarder",
                key=f"ar9_save_{_ar9_ti}",
                disabled=_sv9_dis,
                help="Aucun joueur dans l'équipe." if _sv9_dis else None,
            ):
                def _sd9(card):
                    if not card:
                        return None
                    r = _cl_ar9.get(card, {})
                    return {
                        "card_name":      card,
                        "player_slug":    r.get("player_slug"),
                        "player_name":    _slug_name_map.get(r.get("player_slug", ""), card),
                        "picture_url":    r.get("picture_url"),
                        "proj_score_eff": r.get("proj_score_eff"),
                        "proj_score":     None,
                        "card_power":     r.get("card_power"),
                    }
                _persist_lineup({
                    "lineup_id":              str(uuid.uuid4()),
                    "saved_at":               datetime.now(timezone.utc).isoformat(),
                    "gw_int":                 int(_ar9_gw),
                    "manager":                sel_manager,
                    "mode":                   f"Arena {_ar9_type}",
                    "rarity":                 _ar9_rar,
                    "score_src":              _ar9_ssrc,
                    "slots":                  {s: _sd9(c) for s, c in _ar9_team.items()},
                    "suggested_slots_auto":   None,
                    "suggested_slots_sorare": None,
                })
                st.success(f"Lineup {_ar9_ti + 1} Arena {_ar9_type} sauvegardée pour la GW{_ar9_gw} !")
