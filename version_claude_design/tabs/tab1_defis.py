import re
import streamlit as st
import pandas as pd

from data_loaders import (
    render_terminal_card, gen_bar_sparkline_svg,
    load_stat_sparklines, load_top_db_players, load_db_sparklines,
    _team_logo_html, load_team_codes,
)


def render(ctx: dict) -> None:
    df_today     = ctx["df_today"]
    df_prices    = ctx["df_prices"]
    sel_manager  = ctx["sel_manager"]
    sel_stat     = ctx["sel_stat"]
    sel_stat_label = ctx["sel_stat_label"]
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

    _f1, _f2 = st.columns(2)
    _postes_dispo = sorted(df_today["position_agg"].dropna().unique())
    _tab1_saison = _f1.selectbox(
        "Saison", ["Tous", "IS", "Classic"], key="tab1_saison"
    )
    _tab1_poste = _f2.selectbox(
        "Poste", ["Tous"] + _postes_dispo, key="tab1_poste"
    )

    df_view = df_today.copy()
    if _tab1_saison == "IS":
        df_view = df_view[df_view["in_season_eligible"] == True]
    elif _tab1_saison == "Classic":
        df_view = df_view[df_view["in_season_eligible"] == False]
    if _tab1_poste != "Tous":
        df_view = df_view[df_view["position_agg"] == _tab1_poste]

    st.markdown(
        f'<div class="panel"><div class="panel__hd">'
        f'<span class="title">Défis journaliers</span>'
f'<span class="pill accent">{_tab1_day_label}</span>'
        f'<span class="right">{fenetre} · {categorie}</span>'
        f'</div>'
        f'<div class="lineup-summary">'
        f'<div class="ls-cell"><div class="k">Statistique</div>'
        f'<div class="headline"><div class="big" style="color:var(--r-limited)">{sel_stat_label}</div></div>'
        f'<div class="sub">{fenetre} · {categorie}</div></div>'
        f'<div class="ls-cell"><div class="k">Joueurs ce jour</div>'
        f'<div class="v">{len(df_view)}</div><div class="sub">de {len(df)} en galerie</div></div>'
        f'</div></div>',
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

    # ── Top 5 tous joueurs DB ─────────────────────────────────────────────────
    _df_top5 = load_top_db_players(sel_stat_label, sel_stat, fenetre_int,
                                   team_slugs_today=(), n=5, target=target,
                                   min_matchs=max(3, fenetre_int // 2))

    if not _df_top5.empty:
        _top5_title = "Objectif atteint" if target > 0 else sel_stat_label
        st.markdown(
            f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none;margin-top:8px">'
            f'<span class="title">Top 5 — tous joueurs</span>'
            f'<span class="pill">{sel_stat_label}</span>'
            f'<span class="right" style="color:var(--fg-3);font-size:9px">{fenetre} · tous joueurs MLB</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        _t5_slugs   = tuple(_df_top5["player_slug"].tolist())
        _t5_sparks  = load_db_sparklines(_t5_slugs, sel_stat_label, n_games=fenetre_int)
        _t5_hdr     = ("font-family:var(--mono);font-size:9px;letter-spacing:0.12em;"
                       "text-transform:uppercase;color:var(--fg-3);padding:4px 0 3px;"
                       "border-bottom:1px solid var(--line)")
        _t5_col_w   = [3.5, 1.2, 1]
        _t5h0, _t5h1, _t5h2 = st.columns(_t5_col_w, gap="small")
        _t5h0.markdown(f'<div style="{_t5_hdr}">Joueur</div>',           unsafe_allow_html=True)
        _t5h1.markdown(f'<div style="{_t5_hdr};text-align:center">Tendance</div>', unsafe_allow_html=True)
        _t5h2.markdown(f'<div style="{_t5_hdr};text-align:center">{_top5_title}</div>', unsafe_allow_html=True)

        _T5_RANK_COL = ["#f7b100", "#aab4c2", "#cd7f32"]
        for _t5_rank, (_, _t5_row) in enumerate(_df_top5.iterrows()):
            _t5_slug  = _t5_row["player_slug"]
            _t5_name  = _t5_row.get("display_name") or _t5_slug
            _t5_spark = gen_bar_sparkline_svg(_t5_sparks.get(_t5_slug, []), target=target)
            _t5_rc    = _T5_RANK_COL[_t5_rank] if _t5_rank < 3 else "var(--fg-3)"
            if target > 0:
                _t5_val = f'{int(_t5_row["nb_success"])}/{int(_t5_row["nb_matchs"])}'
            else:
                _t5_val = f'{_t5_row["moyenne"]:.2f}'

            _t5c0, _t5c1, _t5c2 = st.columns(_t5_col_w, vertical_alignment="center", gap="small")
            with _t5c0:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:6px;padding:3px 0">'
                    f'<span style="font-family:var(--mono);font-size:9px;color:{_t5_rc};min-width:18px;text-align:right">#{_t5_rank+1}</span>'
                    f'<span style="font-size:11px;font-weight:600;color:var(--fg)">{_t5_name}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _t5c1:
                st.markdown(
                    f'<div style="text-align:center;padding:3px 0">{_t5_spark}</div>',
                    unsafe_allow_html=True,
                )
            with _t5c2:
                st.markdown(
                    f'<div style="text-align:center;padding:3px 0;font-family:var(--mono);'
                    f'font-size:11px;font-weight:700;color:var(--pos)">{_t5_val}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="divider-h"></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none;margin-top:8px">'
        f'<span class="title">Suggestion d\'alignement</span>'
        f'<span class="pill">TOP 3</span>'
        f'<span class="right" style="color:var(--fg-3);font-size:9px">tri par {sel_stat_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    _spark_map = load_stat_sparklines(
        tuple(df_view["player_slug"].tolist()), sel_stat_label
    )

    if target > 0:
        df_view = df_view.copy()
        df_view["nb_objectif"] = df_view["player_slug"].map(
            lambda slug: sum(1 for v in _spark_map.get(slug, []) if v >= target)
        )
        df_view = df_view.sort_values("nb_objectif", ascending=False).reset_index(drop=True)

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
            _rarity = _cr.get("card_display_rarity") or ""
            _card_info_map.setdefault(_cr["player_slug"], []).append(
                (_season, _serial, _rarity)
            )

    # Un joueur est "actif" si au moins une de ses cartes n'est pas exclue
    def _has_active_card(slug):
        cards = _card_info_map.get(slug)
        if not cards:
            return True
        return any(f"{slug}|{sea}|{ser}" not in _excl_set for sea, ser, _ in cards)

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
                _t3_sea, _t3_ser, _ = _t3_cards[0]
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
                render_terminal_card(i, row, sel_stat_label,
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
        _pcards = _card_info_map.get(_prow["player_slug"]) or [("", "", "")]
        for _sea, _ser, _rar in _pcards:
            _r = _prow.to_dict()
            _r["_card_season"]  = _sea
            _r["_card_serial"]  = _ser
            _r["_card_rarity"]  = _rar or _prow.get("card_display_rarity", "")
            _expanded_rows.append(_r)
    _df_expanded = (pd.DataFrame(_expanded_rows).reset_index(drop=True)
                    if _expanded_rows else _df_table)

    st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button {
  width:20px!important; height:20px!important; min-height:20px!important;
  padding:0!important; border-radius:50%!important;
  background:rgba(160,30,30,0.13)!important;
  border:1px solid rgba(200,60,60,0.28)!important;
  color:rgba(220,70,70,0.75)!important;
  font-size:10px!important; line-height:1!important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button:hover {
  background:rgba(200,40,40,0.22)!important;
  border-color:rgba(220,70,70,0.5)!important;
  color:rgba(240,90,90,0.95)!important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button p {
  margin:0!important; padding:0!important; line-height:1!important;
}
</style>
""", unsafe_allow_html=True)

    # Grille 6 colonnes : Joueur | Tendance | Stat | M | Match | Excl.
    _COL_W     = [2, 1, 1, 1, 1, 1]
    _stat_hdr  = "Atteint" if target > 0 else sel_stat_label
    _hdr_style = ("font-family:var(--mono);font-size:9px;letter-spacing:0.12em;"
                  "text-transform:uppercase;color:var(--fg-3);padding:5px 0 4px;"
                  "border-bottom:1px solid var(--line)")
    _hdr_c     = _hdr_style + ";text-align:center"

    _h0, _h1, _h2, _h3, _h4, _h5 = st.columns(_COL_W, gap="small")
    _h0.markdown(f'<div style="{_hdr_style}">Carte</div>',        unsafe_allow_html=True)
    _h1.markdown(f'<div style="{_hdr_c}">Tendance</div>',         unsafe_allow_html=True)
    _h2.markdown(f'<div style="{_hdr_c}">{_stat_hdr}</div>',      unsafe_allow_html=True)
    _h3.markdown(f'<div style="{_hdr_c}">M</div>',                unsafe_allow_html=True)
    _h4.markdown(f'<div style="{_hdr_c}">Match</div>',            unsafe_allow_html=True)
    with _h5:
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
        _spark   = gen_bar_sparkline_svg(_spark_map.get(_slug, []), target=target)
        _moy     = (str(int(row.get("nb_objectif", 0))) if target > 0
                    else f'{row["moyenne"]:.2f}')
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

        _c0, _c1, _c2, _c3, _c4, _c5 = st.columns(_COL_W, vertical_alignment="center", gap="small")
        with _c0:
            st.markdown(
                f'<div style="opacity:{_alpha};padding:4px 0">'
                f'<div class="t1-name" style="{_name_style}">{row["player_name"]}{_card_suffix}</div>'
                f'<div class="t1-meta">'
                f'<span style="color:{_rar_col}">{_rar_lbl}</span>'
                f'<span style="color:var(--fg-3)">·</span>'
                f'<span>{_pos}</span>'
                f'{_is_tag}{_pp_tag}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _c1:
            st.markdown(
                f'<div style="opacity:{_alpha};padding:6px 0;text-align:center">{_spark}</div>',
                unsafe_allow_html=True,
            )
        with _c2:
            st.markdown(
                f'<div style="opacity:{_alpha};text-align:center;padding:8px 0;'
                f'font-family:var(--mono);font-size:11px;color:var(--pos)">{_moy}</div>',
                unsafe_allow_html=True,
            )
        with _c3:
            st.markdown(
                f'<div style="opacity:{_alpha};text-align:center;padding:8px 0;'
                f'font-family:var(--mono);font-size:10px;color:var(--fg-3)">{_matchs}</div>',
                unsafe_allow_html=True,
            )
        with _c4:
            st.markdown(
                f'<div style="display:flex;justify-content:center">{_match_html}</div>',
                unsafe_allow_html=True,
            )
        with _c5:
            # Colonne imbriquée pour que le CSS cible ce bouton (stHorizontalBlock > stHorizontalBlock)
            _, _cbx = st.columns([1, 1], vertical_alignment="center")
            with _cbx:
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
