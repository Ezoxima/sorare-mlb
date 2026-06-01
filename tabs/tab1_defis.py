import re
import streamlit as st
import pandas as pd

from data_loaders import (
    render_terminal_card, gen_bar_sparkline_svg,
    load_stat_sparklines, load_top_db_players, load_db_sparklines,
    load_pitcher_stat_factors, load_sorare_tasks,
    _team_logo_html, load_team_codes,
)


def render(ctx: dict) -> None:
    df_today     = ctx["df_today"]
    df_prices    = ctx["df_prices"]
    sel_manager  = ctx["sel_manager"]
    sel_stat         = ctx["sel_stat"]
    sel_stat_label   = ctx["sel_stat_label"]
    sel_stat_display = ctx.get("sel_stat_display", sel_stat_label)
    fenetre      = ctx["fenetre"]
    fenetre_int  = {"5 matchs": 5, "10 matchs": 10, "20 matchs": 20}.get(fenetre, 10)
    categorie    = ctx["categorie"]
    target       = ctx["target"]
    sel_day      = ctx["sel_day"]
    now_paris    = ctx["now_paris"]
    df           = ctx["df"]
    _tlogos      = ctx.get("_tlogos", {})
    _tcodes      = load_team_codes()

    if sel_day is not None:
        _tab1_day_label = pd.Timestamp(sel_day).strftime("%A %d %B").capitalize()
    else:
        _tab1_day_label = now_paris.strftime("%A %d %B").capitalize()

    _f1, _f2, _f3, _f4 = st.columns(4)
    _postes_dispo = sorted(df_today["position_agg"].dropna().unique())
    _tab1_saison = _f1.selectbox(
        "Saison", ["Tous", "IS", "Classic"], key="tab1_saison"
    )
    _tab1_poste = _f2.selectbox(
        "Poste", ["Tous"] + _postes_dispo, key="tab1_poste"
    )
    _tab1_all_games = _f3.selectbox(
        "Tendances", ["Matchs joués", "Tous les matchs"], key="tab1_all_games"
    ) == "Tous les matchs"
    _pitcher_mode = False
    if categorie == "HITTING":
        _pitcher_mode = _f4.radio(
            "Tri", ["Historique", "vs Pitcher"], horizontal=True, key="tab1_tri_mode"
        ) == "vs Pitcher"

    df_view = df_today.copy()
    if _tab1_saison == "IS":
        df_view = df_view[df_view["in_season_eligible"] == True]
    elif _tab1_saison == "Classic":
        df_view = df_view[df_view["in_season_eligible"] == False]
    if _tab1_poste != "Tous":
        df_view = df_view[df_view["position_agg"] == _tab1_poste]

    # ── Facteurs pitcher + helpers ────────────────────────────────────────────
    _pf_factors: dict     = {}
    _pf_league_avg: float = 0.0
    _pf_slug_map: dict    = {}
    if _pitcher_mode:
        _pf_factors, _pf_league_avg = load_pitcher_stat_factors(sel_stat)

    def _pitcher_short(slug: str) -> str:
        if not slug:
            return ""
        parts = slug.split("-")
        if parts and len(parts[-1]) == 8 and parts[-1].isdigit():
            parts = parts[:-1]
        return parts[-1].capitalize() if parts else ""

    def _factor_html(factor) -> str:
        if factor is None or (hasattr(factor, '__float__') and factor != factor):
            return ""
        pct = (float(factor) - 1.0) * 100
        col = "var(--fg-3)" if abs(pct) < 3 else ("var(--pos)" if pct > 0 else "var(--neg)")
        sign = "+" if pct > 0 else ""
        return f'<span style="font-size:9px;color:{col};font-weight:600">{sign}{pct:.0f}%</span>'

    # ── Top 5 data chargé avant le panel (rendu en HTML pur dans la zone droite) ──
    _teams_day = ctx.get("_teams_day", ())
    _tgi       = ctx.get("_tgi", {})
    _t5_pool_n = 20 if _pitcher_mode else 5
    _df_top5 = load_top_db_players(sel_stat_label, sel_stat, fenetre_int,
                                   team_slugs_today=_teams_day, n=_t5_pool_n, target=target,
                                   min_matchs=max(3, fenetre_int // 2))

    if _pitcher_mode and not _df_top5.empty and _pf_factors:
        _df_top5 = _df_top5.copy()
        _df_top5["_opp_pitcher"] = _df_top5.get("team_slug", pd.Series(dtype=str)).map(
            {ts: info.get("opp_pitcher_slug", "") for ts, info in _tgi.items()}
        ).fillna("")
        _df_top5["_pf_factor"] = _df_top5["_opp_pitcher"].map(_pf_factors)
        _df_top5["_adj_score"] = _df_top5["moyenne"] * _df_top5["_pf_factor"].fillna(1.0)
        _df_top5 = _df_top5.sort_values("_adj_score", ascending=False).head(5).reset_index(drop=True)
    elif not _df_top5.empty:
        _df_top5 = _df_top5.head(5).reset_index(drop=True)

    _t5_sparks: dict = {}
    if not _df_top5.empty:
        _t5_sparks = load_db_sparklines(
            tuple(_df_top5["player_slug"].tolist()), sel_stat_label,
            n_games=fenetre_int, include_all_games=_tab1_all_games,
        )

    # ── Construire le HTML du Top 5 (injecté dans le panel) ──────────────────
    _T5_RANK_COL = ["#f7b100", "#aab4c2", "#cd7f32"]
    _top5_panel_html = ""

    def _t5_match_cell(team_slug: str) -> str:
        gi = _tgi.get(team_slug or "", {})
        if not gi:
            return '<div style="text-align:center;color:var(--fg-3);font-size:9px">—</div>'
        _ht, _at, _hr = gi.get("home_slug",""), gi.get("away_slug",""), gi.get("heure","—")
        def _lc(sl):
            url  = _tlogos.get(sl, "")
            code = _tcodes.get(sl) or (sl[:3].upper() if sl else "?")
            img  = (f'<img src="{url}" style="height:18px;width:18px;object-fit:contain">'
                    if url else f'<span style="font-size:9px;font-weight:700;color:var(--fg-1)">{code}</span>')
            return (f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px">'
                    f'{img}<span style="font-size:8px;font-weight:700;color:var(--fg-3);letter-spacing:0.04em">{code}</span></div>')
        return (f'<div style="display:inline-flex;align-items:center;gap:5px">'
                f'{_lc(_ht)}'
                f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px">'
                f'<span style="font-size:8px;color:var(--fg-3)">VS</span>'
                f'<span style="font-size:10px;font-weight:700;color:var(--info);font-family:var(--mono)">{_hr}</span>'
                f'</div>'
                f'{_lc(_at)}'
                f'</div>')

    if not _df_top5.empty:
        _top5_val_label = ("Atteint ajusté" if (target > 0 and _pitcher_mode)
                           else "Objectif" if target > 0
                           else sel_stat_display)
        _pp_col   = "120px " if _pitcher_mode else ""
        _reg_col  = "35px " if target > 0 else ""
        _gcols    = f"155px 87px 51px {_reg_col}136px {_pp_col}".strip()
        _hs       = "font-size:8px;letter-spacing:0.1em;text-transform:uppercase;color:var(--fg-3);font-family:var(--mono)"
        _pp_hdr   = f'<span style="{_hs};text-align:center">Pitcher</span>' if _pitcher_mode else ""
        _reg_hdr  = f'<span style="{_hs};text-align:center">Régu</span>' if target > 0 else ""
        _rows_html = (
            f'<div style="display:grid;grid-template-columns:{_gcols};gap:0 8px;'
            f'padding-bottom:4px;margin-bottom:3px;border-bottom:1px solid var(--line)">'
            f'<span style="{_hs}">Joueur</span>'
            f'<span style="{_hs};text-align:center">Tendance</span>'
            f'<span style="{_hs};text-align:center">{_top5_val_label}</span>'
            f'{_reg_hdr}'
            f'<span style="{_hs};text-align:center">Match</span>'
            f'{_pp_hdr}</div>'
        )
        for _t5_rank, (_, _t5_row) in enumerate(_df_top5.iterrows()):
            _t5_slug  = _t5_row["player_slug"]
            _t5_name  = _t5_row.get("display_name") or _t5_slug
            _t5_spark = gen_bar_sparkline_svg(_t5_sparks.get(_t5_slug, []), w=87, h=20, target=target)
            _t5_rc    = _T5_RANK_COL[_t5_rank] if _t5_rank < 3 else "var(--fg-3)"
            if _pitcher_mode and "_adj_score" in _t5_row and _t5_row["_adj_score"] == _t5_row["_adj_score"]:
                _t5_val = f'{_t5_row["_adj_score"]:.2f}'
            elif target > 0:
                _t5_val = f'{int(_t5_row["nb_success"])}/{int(_t5_row["nb_matchs"])}'
            else:
                _t5_val = f'{_t5_row["moyenne"]:.2f}'
            _t5_reg_cell = ""
            if target > 0:
                _t5_sv = [v for v in _t5_sparks.get(_t5_slug, []) if v is not None and v == v]
                if _t5_sv:
                    _t5_n_ok = sum(1 for v in _t5_sv if v >= target)
                    _t5_rp   = _t5_n_ok / len(_t5_sv)
                    _t5_reg_col = "var(--pos)" if _t5_rp >= 0.6 else "var(--neg)"
                    _t5_reg_cell = (
                        f'<div style="text-align:center;line-height:1.2">'
                        f'<div style="font-size:11px;color:{_t5_reg_col};font-weight:700">'
                        f'{"✓" if _t5_rp >= 0.6 else "✗"}</div>'
                        f'<div style="font-size:8px;color:var(--fg-3);font-family:var(--mono)">'
                        f'{int(_t5_rp * 100)}%</div>'
                        f'</div>'
                    )
                else:
                    _t5_reg_cell = '<div style="text-align:center;color:var(--fg-3);font-size:9px">—</div>'
            _pp_cell = ""
            if _pitcher_mode:
                _pn = _pitcher_short(_t5_row.get("_opp_pitcher", ""))
                _pf = _t5_row.get("_pf_factor")
                _pp_cell = (
                    f'<div style="text-align:center;font-family:var(--mono);line-height:1.3">'
                    f'<div style="font-size:9px;color:var(--fg-1)">{_pn or "—"}</div>'
                    f'<div>{_factor_html(_pf) if (_pf is not None and _pf == _pf) else ""}</div>'
                    f'</div>'
                )
            _t5_ts   = _t5_row.get("team_slug", "")
            _rows_html += (
                f'<div style="display:grid;grid-template-columns:{_gcols};gap:0 8px;'
                f'padding:7px 0;align-items:center">'
                f'<div style="display:flex;align-items:center;gap:4px;min-width:0">'
                f'<span style="font-size:8px;color:{_t5_rc};min-width:14px;text-align:right;'
                f'flex-shrink:0;font-family:var(--mono)">#{_t5_rank+1}</span>'
                f'<a href="https://sorare.com/fr/mlb/players/{_t5_slug}" target="_blank" class="sorare-link"'
                f' style="font-size:10px;font-weight:600;white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis;font-family:var(--mono)">{_t5_name}</a>'
                f'</div>'
                f'<div style="display:flex;align-items:center;justify-content:center">{_t5_spark}</div>'
                f'<div style="text-align:center;font-size:11px;font-weight:700;color:var(--pos);'
                f'font-variant-numeric:tabular-nums;font-family:var(--mono)">{_t5_val}</div>'
                f'{_t5_reg_cell}'
                f'<div style="display:flex;justify-content:center">{_t5_match_cell(_t5_ts)}</div>'
                f'{_pp_cell}'
                f'</div>'
            )
        _t5_mode_pill = (
            f'<span style="font-size:9px;padding:1px 5px;border:1px solid var(--line-2);color:var(--fg-2)">'
            f'{"vs Pitcher" if _pitcher_mode else "tous joueurs"}</span>'
        )
        _top5_panel_html = (
            f'<div style="padding:12px 16px;min-width:0;overflow:hidden;'
            f'display:flex;flex-direction:column;align-items:flex-end">'
            f'<div style="border-left:1px solid var(--line);padding-left:14px">'
            f'<div style="font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:var(--fg-3);'
            f'margin-bottom:6px;display:flex;align-items:center;gap:6px;font-family:var(--mono)">'
            f'TOP 5 {_t5_mode_pill}</div>'
            f'{_rows_html}'
            f'</div>'
            f'</div>'
        )

    # ── Filtre rareté tasks ───────────────────────────────────────────────────
    _RARITY_OPTS = {"Limited": "limited", "Rare": "rare", "Super Rare": "super_rare", "Unique": "unique"}
    _rar_label   = st.radio("Rareté défis", list(_RARITY_OPTS.keys()),
                             horizontal=True, key="tab1_task_rarity")
    _rar_val     = _RARITY_OPTS[_rar_label]
    _tasks       = load_sorare_tasks(_rar_val)

    # Filtre df_view par rareté sélectionnée
    if not df_prices.empty and sel_manager:
        _rar_slugs = set(
            df_prices[
                (df_prices["gallery_manager"] == sel_manager) &
                (df_prices["card_display_rarity"] == _rar_label)
            ]["player_slug"]
        )
        df_view = df_view[df_view["player_slug"].isin(_rar_slugs)]

    # ── Tasks HTML ────────────────────────────────────────────────────────────
    _SCORE_STATUS_COLOR = {
        "DONE": "var(--pos)", "COMPLETED": "var(--pos)",
        "REVIEWING": "#f7b100", "LIVE": "#f7b100",
        "PENDING": "var(--fg-3)", "MISSED": "var(--neg)",
    }
    _RAR_BORDER = {
        "limited": "#f7b100", "rare": "var(--r-rare)",
        "super_rare": "var(--r-superrare)", "unique": "var(--r-unique)",
    }

    def _slot_html(ap: dict | None, slot_idx: int) -> str:
        if ap is None:
            return (
                f'<div title="Slot {slot_idx+1}" style="width:30px;height:30px;border-radius:50%;'
                f'border:1px dashed var(--line-2);display:flex;align-items:center;justify-content:center">'
                f'<span style="font-size:9px;color:var(--fg-3)">{slot_idx+1}</span></div>'
            )
        border_col = _RAR_BORDER.get(ap["rarity"], "var(--line-2)")
        sc_col     = _SCORE_STATUS_COLOR.get(ap["score_status"], "var(--fg-3)")
        check      = "✓" if ap["reached"] else ("⏳" if ap["score_status"] == "PENDING" else "")
        stats_tip  = "/".join(ap["stats"]) if ap["stats"] else ""
        tip        = f'{ap["player_name"]} · {stats_tip}' if stats_tip else ap["player_name"]
        img        = (f'<img src="{ap["avatar_url"]}" style="width:28px;height:28px;'
                      f'border-radius:50%;object-fit:cover;display:block">'
                      if ap["avatar_url"] else
                      f'<span style="font-size:8px;font-weight:700;color:var(--fg-1)">'
                      f'{ap["player_name"][:3].upper()}</span>')
        badge      = (f'<span style="position:absolute;bottom:-3px;right:-3px;'
                      f'font-size:8px;color:{sc_col};line-height:1">{check}</span>'
                      if check else "")
        return (
            f'<div title="{tip}" style="position:relative;width:30px;height:30px;border-radius:50%;'
            f'border:1.5px solid {border_col};overflow:visible;'
            f'display:flex;align-items:center;justify-content:center;flex-shrink:0">'
            f'{img}{badge}</div>'
        )

    def _task_html(task: dict) -> str:
        typename  = task["typename"]
        title     = task["title"]
        desc      = task["description"] or ""
        progress  = task["progress"]
        tgt       = task["target"]
        icon      = task["reward_icon"]
        max_slots = task["max_slots"]
        aps_map   = {ap.get("index", i): ap for i, ap in enumerate(task["appearances"])}

        icon_html = (f'<img src="{icon}" style="height:14px;width:14px;object-fit:contain;flex-shrink:0">'
                     if icon else "")

        # Streak task
        if typename == "ThresholdsStreakTask":
            live   = task.get("live_score") or 0
            stgt   = task.get("streak_target") or tgt
            state  = task.get("streak_state") or ""
            pct    = min(live / stgt * 100, 100) if stgt else 0
            bar_c  = "var(--pos)" if pct >= 100 else ("var(--info)" if task.get("engaged") else "var(--fg-3)")
            return (
                f'<div style="padding:6px 0;border-bottom:1px solid var(--line)">'
                f'<div style="display:flex;align-items:center;gap:5px;margin-bottom:3px">'
                f'{icon_html}'
                f'<span style="font-size:10px;font-weight:600;color:var(--fg-0)">{title}</span>'
                f'</div>'
                f'<div style="height:3px;background:var(--bg-3);border-radius:2px">'
                f'<div style="height:3px;width:{pct:.0f}%;background:{bar_c};border-radius:2px"></div>'
                f'</div>'
                f'</div>'
            )

        # Decisive player picker task
        prog_col = "var(--pos)" if progress >= tgt else "var(--fg-3)"
        return (
            f'<div style="padding:6px 0;border-bottom:1px solid var(--line)">'
            f'<div style="display:flex;align-items:center;gap:5px;margin-bottom:2px">'
            f'{icon_html}'
            f'<span style="font-size:10px;font-weight:600;color:var(--fg-0)">{title}</span>'
            f'</div>'
            f'<div style="font-size:9px;color:var(--fg-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
            f'{desc}</div>'
            f'</div>'
        )

    _daily_tasks  = [t for t in _tasks
                     if t.get("periodicity") == "DAILY" and t.get("genre") == "FANTASY"
                     and "Champions" not in (t.get("title") or "")]
    _streak_tasks = [t for t in _tasks if t.get("typename") == "ThresholdsStreakTask"
                     and "Champion" not in (t.get("title") or "")]
    _all_show_tasks = _daily_tasks + _streak_tasks
    _hs_t = "font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:var(--fg-3);font-family:var(--mono)"

    # ── Panel principal ───────────────────────────────────────────────────────
    _tasks_col_html = ""
    _grid_cols = "auto 1fr"
    if _all_show_tasks:
        _ti_html = "".join(_task_html(t) for t in _all_show_tasks)
        _tasks_col_html = (
            f'<div class="t1-tasks-col" style="padding:10px 14px;max-width:550px;overflow-y:auto;border-right:1px solid var(--line)">'
            f'<div style="{_hs_t};margin-bottom:6px">Défis du jour</div>'
            f'{_ti_html}'
            f'</div>'
        )
        _grid_cols = "auto 1fr"
    else:
        _grid_cols = "1fr"
    st.markdown(
        f'<div class="panel"><div class="panel__hd">'
        f'<span class="title">Défis journaliers</span>'
        f'<span class="pill accent">{_tab1_day_label}</span>'
        f'<span class="right">{fenetre} · {categorie}</span>'
        f'</div>'
        f'<div class="t1-grid" style="display:grid;grid-template-columns:{_grid_cols};border-top:1px solid var(--line)">'
        f'{_tasks_col_html}'
        f'<div style="display:flex;min-width:0">'
        f'{_top5_panel_html}'
        f'</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    # Ligne stat + compteur joueurs disponibles
    _n_rar_gallery = (
        df_prices[
            (df_prices["gallery_manager"] == sel_manager) &
            (df_prices["card_display_rarity"] == _rar_label)
        ]["player_slug"].nunique()
        if (not df_prices.empty and sel_manager) else len(df)
    )
    st.markdown(
        f'<div style="display:flex;align-items:baseline;gap:10px;padding:5px 0 0">'
        f'<span style="font-size:12px;font-weight:700;color:var(--fg-0);font-family:var(--mono)">'
        f'{len(df_view)} joueurs disponibles pour les défis</span>'
        f'<span style="font-size:9px;color:var(--fg-3);font-family:var(--mono)">'
        f'{_n_rar_gallery} en galerie ({_rar_label})</span>'
        f'<span style="font-size:9px;color:var(--fg-3);margin-left:auto;font-family:var(--mono)">'
        f'{sel_stat_display} · {fenetre} · {categorie}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if df_view.empty:
        if sel_day is not None:
            st.info(f"Aucun joueur de ta galerie ne joue le {_tab1_day_label}.")
        else:
            st.info("Aucun joueur de ta galerie ne correspond aux filtres sélectionnés.")
        return

    # ── session state exclusions (keyed par jour + slug) ──────────────────────
    _day_key  = str(sel_day or now_paris.date())
    _excl_key = f"tab1_excl_{_day_key}"
    if _excl_key not in st.session_state:
        st.session_state[_excl_key] = []
    _excl_set: set = set(st.session_state[_excl_key])

    st.markdown(
        f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none;margin-top:8px">'
        f'<span class="title">Suggestion d\'alignement</span>'
        f'<span class="pill">TOP 3</span>'
        f'<span class="right" style="color:var(--fg-3);font-size:9px">tri par {sel_stat_display}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    _spark_map = load_stat_sparklines(
        tuple(df_view["player_slug"].tolist()), sel_stat_label,
        n_games=fenetre_int,
        include_all_games=_tab1_all_games,
    )

    if target > 0:
        df_view = df_view.copy()
        df_view["nb_objectif"] = df_view["player_slug"].map(
            lambda slug: sum(1 for v in _spark_map.get(slug, []) if v >= target)
        )
        df_view = df_view.sort_values("nb_objectif", ascending=False).reset_index(drop=True)

    # ── Mode "vs Pitcher" — mapping joueur → factor (nécessite df_view final) ──
    if _pitcher_mode:
        for _, _prow in df_view.iterrows():
            _ps = (_prow.get("opp_pitcher_slug") or "")
            if _ps and _ps in _pf_factors:
                _pf_slug_map[_prow["player_slug"]] = (_ps, _pf_factors[_ps])
        df_view = df_view.copy()
        df_view["_pf_factor"] = df_view["player_slug"].map(
            {slug: f for slug, (_, f) in _pf_slug_map.items()}
        )
        df_view["_adj_score"] = df_view["moyenne"] * df_view["_pf_factor"].fillna(1.0)
        df_view = df_view.sort_values("_adj_score", ascending=False).reset_index(drop=True)


    # _card_info_map construit en premier : nécessaire pour l'exclusion par carte
    # _excl_set stocke des card IDs "slug|season|serial" (plus des slugs bruts)
    _card_info_map: dict = {}
    if not df_prices.empty and sel_manager:
        for _, _cr in df_prices[df_prices["gallery_manager"] == sel_manager].iterrows():
            _cname = _cr.get("card_name") or ""
            _sm  = re.search(r'(\d+/\d+)', _cname)
            _ssm = re.search(r'(\d{4}-\d{2})', _cname)
            _serial = _sm.group(1)  if _sm  else ""
            _season = _ssm.group(1) if _ssm else ""
            _rarity     = _cr.get("card_display_rarity") or ""
            _is_elig    = bool(_cr.get("in_season_eligible"))
            _card_info_map.setdefault(_cr["player_slug"], []).append(
                (_season, _serial, _rarity, _is_elig)
            )

    # Un joueur est "actif" si au moins une de ses cartes n'est pas exclue
    def _has_active_card(slug):
        cards = _card_info_map.get(slug)
        if not cards:
            return True
        return any(f"{slug}|{sea}|{ser}" not in _excl_set for sea, ser, *_ in cards)

    df_active = df_view[df_view["player_slug"].apply(_has_active_card)]

    _rar_rank = {"Unique": 0, "Super Rare": 1, "Rare": 2, "Limited": 3}
    _top3_pic_map: dict = {}
    if not df_prices.empty and sel_manager:
        _mgr_cards = df_prices[df_prices["gallery_manager"] == sel_manager].copy()
        _mgr_cards["_rar_rank"] = _mgr_cards["card_display_rarity"].map(_rar_rank).fillna(99)
        _mgr_cards = _mgr_cards.sort_values(
            ["in_season_eligible", "_rar_rank"], ascending=[False, True]
        )
        _top3_pic_map = (
            _mgr_cards.dropna(subset=["picture_url"])
            .drop_duplicates("player_slug")
            .set_index("player_slug")["picture_url"]
            .to_dict()
        )

    top3      = df_active.head(3)
    top3_cols = st.columns(max(len(top3), 1))
    for i, ((_, row), col) in enumerate(zip(top3.iterrows(), top3_cols)):
        with col:
            pic_url    = _top3_pic_map.get(row["player_slug"])
            spark_vals = _spark_map.get(row["player_slug"])
            # Suffix carte : première carte du joueur (saison · serial)
            _t3_sea, _t3_ser = "", ""
            _t3_cards = _card_info_map.get(row["player_slug"])
            if _t3_cards:
                _t3_sea, _t3_ser, *_ = _t3_cards[0]
            _t3_sfx_style = "font-weight:normal;color:#ffffff;opacity:0.65;font-size:0.82em"
            if _t3_sea and _t3_ser:
                _t3_suffix = f' <span style="{_t3_sfx_style}">· {_t3_sea} · #{_t3_ser}</span>'
            elif _t3_ser:
                _t3_suffix = f' <span style="{_t3_sfx_style}">· #{_t3_ser}</span>'
            elif _t3_sea:
                _t3_suffix = f' <span style="{_t3_sfx_style}">· {_t3_sea}</span>'
            else:
                _t3_suffix = ""
            st.markdown(
                render_terminal_card(i, row, sel_stat_display,
                                     spark_values=spark_vals,
                                     picture_url=pic_url,
                                     target=target,
                                     show_pred=False,
                                     card_suffix=_t3_suffix),
                unsafe_allow_html=True,
            )

    st.markdown('<div class="divider-h"></div>', unsafe_allow_html=True)

    # ── section classement — grille 6 colonnes (Excl. aligné avec Match) ──────────

    _view_slugs = set(df_view["player_slug"])
    _n_excl   = sum(1 for cid in _excl_set if cid.split("|")[0] in _view_slugs)
    _has_excl = bool(_n_excl)
    _excl_pill = (f'<span class="pill" style="color:var(--fg-3)">{_n_excl} exclus</span>'
                  if _n_excl else "")
    st.markdown(
        f'<div class="panel__hd" style="border:none;padding:4px 0 6px">'
        f'<span class="title">Classement du jour</span>'
        f'<span class="pill">{len(df_view)} joueurs</span>'
        f'{_excl_pill}'
        f'</div>',
        unsafe_allow_html=True,
    )

    _RAR_COLOR = {"limited": "var(--r-limited)", "rare": "var(--r-rare)",
                  "super_rare": "var(--r-superrare)", "unique": "var(--r-unique)"}

    _df_table = pd.concat([
        df_view[df_view["player_slug"].apply(_has_active_card)],
        df_view[~df_view["player_slug"].apply(_has_active_card)],
    ]).reset_index(drop=True)

    # Expansion : 1 ligne par carte (un joueur avec 2 cartes → 2 lignes)
    _expanded_rows = []
    for _, _prow in _df_table.iterrows():
        _pcards = _card_info_map.get(_prow["player_slug"]) or [("", "", "", None)]
        for _sea, _ser, _rar, _is_el in _pcards:
            _r = _prow.to_dict()
            _r["_card_season"]        = _sea
            _r["_card_serial"]        = _ser
            _r["_card_rarity"]        = _rar or _prow.get("card_display_rarity", "")
            _r["in_season_eligible"]  = _is_el if _is_el is not None else _prow.get("in_season_eligible")
            _expanded_rows.append(_r)
    _df_expanded = (pd.DataFrame(_expanded_rows).reset_index(drop=True)
                    if _expanded_rows else _df_table)

    st.markdown("""
<style>
/* Bouton excl. */
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button {
  width:20px!important; height:20px!important; min-height:20px!important;
  padding:0!important; border-radius:50%!important;
  background:rgba(160,30,30,0.13)!important;
  border:1px solid rgba(200,60,60,0.28)!important;
  color:rgba(220,70,70,0.75)!important;
  font-size:10px!important; line-height:1!important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button:hover {
  background:rgba(200,40,40,0.22)!important;
  border-color:rgba(220,70,70,0.5)!important;
  color:rgba(240,90,90,0.95)!important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button p {
  margin:0!important; padding:0!important; line-height:1!important;
}
/* Mobile */
@media (max-width: 640px) {
  .t1-hide-mobile { display:none !important; }
  .t1-grid { grid-template-columns:1fr !important; }
  .t1-tasks-col { max-width:100% !important; border-right:none !important; border-bottom:1px solid var(--line) !important; }
}
</style>
""", unsafe_allow_html=True)

    # 2 colonnes : bloc responsive HTML | bouton excl.
    _stat_hdr  = "Atteint" if target > 0 else sel_stat_display
    if _pitcher_mode:
        _stat_hdr = f"{_stat_hdr}·Adj"
    _hdr_style = ("font-family:var(--mono);font-size:9px;letter-spacing:0.12em;"
                  "text-transform:uppercase;color:var(--fg-3);padding:5px 0 4px;"
                  "border-bottom:1px solid var(--line)")
    _hdr_c     = _hdr_style + ";text-align:center"

    _hh0, _hh1 = st.columns([6, 0.7], gap="small")
    _pit_lbl   = f" · Pitcher" if _pitcher_mode else ""
    _hh0.markdown(
        f'<div style="{_hdr_style}">Carte · <span class="t1-hide-mobile">Tendance · </span>'
        f'{_stat_hdr}<span class="t1-hide-mobile"> · M</span> · Match{_pit_lbl}</div>',
        unsafe_allow_html=True,
    )
    with _hh1:
        st.markdown(f'<div style="{_hdr_c}">Excl.</div>', unsafe_allow_html=True)
        if _has_excl:
            if st.button("↺", key=f"tab1_excl_reset_{_day_key}",
                         help="Réinitialiser les exclusions", use_container_width=True):
                st.session_state[_excl_key] = []
                st.rerun()

    for _, row in _df_expanded.iterrows():
        _slug  = row["player_slug"]
        _sea   = row.get("_card_season", "")
        _ser     = row.get("_card_serial", "")
        _card_id = f"{_slug}|{_sea}|{_ser}"
        _excl    = _card_id in _excl_set
        _alpha   = "0.35" if _excl else "1"
        _rar_raw = (row.get("_card_rarity") or "").lower().replace(" ", "_")
        _rar_col = _RAR_COLOR.get(_rar_raw, "var(--fg-3)")
        _rar_lbl = (row.get("_card_rarity") or "").upper()
        _pos     = row.get("position_agg") or "?"
        _is_tag  = ('<span class="tag is" style="margin:0">IS</span>'
                    if row.get("in_season_eligible") is True
                    else ('<span class="tag classic" style="margin:0">CLASSIC</span>'
                          if row.get("in_season_eligible") is False else ""))
        _pp_tag  = '<span class="tag pp" style="margin:0">PP</span>' if row.get("is_pp") else ""
        _spark_vals = _spark_map.get(_slug, [])
        _spark   = gen_bar_sparkline_svg(_spark_vals, target=target)
        if target > 0:
            _moy = str(int(row.get("nb_objectif", 0)))
        elif _spark_vals:
            _sv1 = [v for v in _spark_vals if v is not None and v == v]
            _moy = f'{sum(_sv1) / len(_sv1):.2f}' if _sv1 else f'{row["moyenne"]:.2f}'
        else:
            _moy = f'{row["moyenne"]:.2f}'
        _matchs  = int(row["nb_matchs"])
        _heure     = row.get("coup_envoi") or "—"
        _home_slug = row.get("home_slug") or ""
        _away_slug = row.get("away_slug") or ""

        # Suffixe carte sur la même ligne que le nom : "· 2026-27 · #200/100"
        _sfx_style = "color:#ffffff;opacity:0.65;font-weight:normal;letter-spacing:0.03em"
        _card_suffix = ""
        if _sea and _ser:
            _card_suffix = f' <span style="{_sfx_style}">· {_sea} · #{_ser}</span>'
        elif _ser:
            _card_suffix = f' <span style="{_sfx_style}">· #{_ser}</span>'
        elif _sea:
            _card_suffix = f' <span style="{_sfx_style}">· {_sea}</span>'

        def _match_card(slug):
            url  = _tlogos.get(slug, "")
            code = _tcodes.get(slug) or (slug[:3].upper() if slug else "?")
            logo = (f'<img src="{url}" style="height:18px;width:18px;object-fit:contain;display:block">'
                    if url else f'<span style="font-size:10px;font-weight:700">{code}</span>')
            return (f'<span class="ticker__team" style="padding:2px 4px;min-width:30px">'
                    f'{logo}<span class="ticker__abbr">{code}</span></span>')

        _match_html = (
            f'<span style="display:inline-flex;align-items:center;gap:2px;opacity:{_alpha}">'
            f'{_match_card(_home_slug) if _home_slug else ""}'
            f'<span class="ticker__score" style="padding:2px 4px;min-width:30px">'
            f'<span class="ticker__vs">VS</span>'
            f'<span class="ticker__time">{_heure}</span>'
            f'</span>'
            f'{_match_card(_away_slug) if _away_slug else ""}'
            f'</span>'
        )
        _name_style = "text-decoration:line-through;color:var(--fg-3)" if _excl else ""

        # Stat + pitcher (mode pitcher)
        if _pitcher_mode:
            _adj_val  = row.get("_adj_score")
            _base_moy = f'{row["moyenne"]:.2f}'
            _adj_str  = f'{float(_adj_val):.2f}' if (_adj_val is not None and _adj_val == _adj_val) else _base_moy
            _stat_html = (
                f'<span style="font-size:11px;color:var(--pos);font-weight:600">{_adj_str}</span>'
                f'<span style="font-size:9px;color:var(--fg-3);margin-left:2px">{_base_moy}</span>'
            )
            _pf_info2 = _pf_slug_map.get(_slug)
            if _pf_info2:
                _pp_slug2, _pp_factor2 = _pf_info2
                _pit_html = (
                    f'<span style="font-size:9px;color:var(--fg-1);font-family:var(--mono)">'
                    f'{_pitcher_short(_pp_slug2)}</span>'
                    f'{_factor_html(_pp_factor2)}'
                )
            else:
                _pit_html = '<span style="font-size:9px;color:var(--fg-3)">—</span>'
        else:
            _stat_html = f'<span style="font-size:11px;color:var(--pos);font-weight:600;font-family:var(--mono)">{_moy}</span>'
            _pit_html  = ""

        _c_main, _c5 = st.columns([6, 0.7], vertical_alignment="center", gap="small")

        with _c_main:
            st.markdown(
                f'<div style="opacity:{_alpha};padding:3px 0;display:flex;flex-wrap:wrap;'
                f'align-items:center;gap:3px 10px">'
                # Bloc nom + meta (flex:1 → prend l'espace disponible)
                f'<div style="flex:1;min-width:110px">'
                f'<a href="https://sorare.com/fr/mlb/players/{_slug}" target="_blank"'
                f' class="sorare-link t1-name" style="{_name_style}">{row["player_name"]}{_card_suffix}</a>'
                f'<div class="t1-meta">'
                f'<span style="color:{_rar_col}">{_rar_lbl}</span>'
                f'<span style="color:var(--fg-3)">·</span><span>{_pos}</span>'
                f'{_is_tag}{_pp_tag}'
                f'</div>'
                f'</div>'
                # Sparkline (masqué sur mobile)
                f'<div class="t1-hide-mobile" style="flex:0 0 auto">{_spark}</div>'
                # Stat
                f'<div style="flex:0 0 auto;text-align:right">{_stat_html}</div>'
                # Nb matchs (masqué sur mobile)
                f'<div class="t1-hide-mobile" style="flex:0 0 22px;text-align:center;'
                f'font-family:var(--mono);font-size:10px;color:var(--fg-3)">{_matchs}</div>'
                # Match
                f'<div style="flex:0 0 auto">{_match_html}</div>'
                # Pitcher (mode pitcher)
                + (f'<div style="flex:0 0 auto;text-align:center">{_pit_html}</div>' if _pitcher_mode else "")
                + f'</div>',
                unsafe_allow_html=True,
            )

        with _c5:
            _btn_lbl  = "↩" if _excl else "✕"
            _btn_help = "Réintégrer" if _excl else "Exclure"
            _btn_key  = f"excl_{_slug}_{_sea}_{_ser}_{_day_key}"
            if st.button(_btn_lbl, key=_btn_key, help=_btn_help):
                if _excl:
                    st.session_state[_excl_key] = [s for s in st.session_state[_excl_key]
                                                   if s != _card_id]
                else:
                    st.session_state[_excl_key] = list(_excl_set | {_card_id})
                st.rerun()
