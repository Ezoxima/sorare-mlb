import streamlit as st
import pandas as pd

from data_loaders import (
    render_terminal_card, gen_bar_sparkline_svg, show_player_chart,
    load_stat_sparklines,
)


def render(ctx: dict) -> None:
    df_today     = ctx["df_today"]
    df_prices    = ctx["df_prices"]
    sel_manager  = ctx["sel_manager"]
    sel_stat     = ctx["sel_stat"]
    sel_stat_label = ctx["sel_stat_label"]
    fenetre      = ctx["fenetre"]
    categorie    = ctx["categorie"]
    target       = ctx["target"]
    sel_day      = ctx["sel_day"]
    now_paris    = ctx["now_paris"]
    df           = ctx["df"]

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
        f'<span class="pill live">LIVE</span>'
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

    df_active = df_view[~df_view["player_slug"].isin(_excl_set)]

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
            st.markdown(
                render_terminal_card(i, row, sel_stat_label,
                                     spark_values=spark_vals,
                                     picture_url=pic_url,
                                     target=target),
                unsafe_allow_html=True,
            )

    st.markdown('<div class="divider-h"></div>', unsafe_allow_html=True)

    # ── en-tête classement + reset ─────────────────────────────────────────────
    _hd_left, _hd_right = st.columns([10, 0.5], vertical_alignment="center")
    with _hd_left:
        _n_excl = len(_excl_set & set(df_view["player_slug"]))
        _excl_pill = (f'<span class="pill" style="color:var(--fg-3)">{_n_excl} exclus</span>'
                      if _n_excl else "")
        st.markdown(
            f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
            f'<span class="title">Classement du jour</span>'
            f'<span class="pill">{len(df_view)} joueurs</span>'
            f'{_excl_pill}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _hd_right:
        if _excl_set:
            st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
            if st.button("↺ Réinitialiser", key=f"tab1_excl_reset_{_day_key}",
                         use_container_width=True):
                st.session_state[_excl_key] = []
                st.rerun()

    # ── tableau : actifs d'abord, exclus en bas ────────────────────────────────
    _RAR_COLOR = {"limited": "var(--r-limited)", "rare": "var(--r-rare)",
                  "super_rare": "var(--r-superrare)", "unique": "var(--r-unique)"}

    _df_table = pd.concat([
        df_view[~df_view["player_slug"].isin(_excl_set)],
        df_view[df_view["player_slug"].isin(_excl_set)],
    ]).reset_index(drop=True)

    st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button,
div[data-testid="stHorizontalBlock"] div[data-testid="column"]:last-of-type button {
  width:22px!important; height:22px!important; min-height:22px!important;
  padding:0!important; border-radius:50%!important;
  background:rgba(160,30,30,0.13)!important;
  border:1px solid rgba(200,60,60,0.28)!important;
  color:rgba(220,70,70,0.75)!important;
  font-size:11px!important; line-height:1!important;
  margin-top:15px!important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button:hover,
div[data-testid="stHorizontalBlock"] div[data-testid="column"]:last-of-type button:hover {
  background:rgba(200,40,40,0.22)!important;
  border-color:rgba(220,70,70,0.5)!important;
  color:rgba(240,90,90,0.95)!important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type button p,
div[data-testid="stHorizontalBlock"] div[data-testid="column"]:last-of-type button p {
  margin:0!important; padding:0!important; line-height:1!important;
}
</style>
""", unsafe_allow_html=True)

    _COL_W = [4, 2, 1, 1, 2, 0.5]
    _stat_hdr = "Atteint" if target > 0 else sel_stat_label
    _h0, _h1, _h2, _h3, _h4, _h5 = st.columns(_COL_W, gap="small")
    _hdr_style = "font-family:var(--mono);font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:var(--fg-3);padding:5px 0 4px;border-bottom:1px solid var(--line)"
    _h0.markdown(f'<div style="{_hdr_style}">Joueur</div>', unsafe_allow_html=True)
    _h1.markdown(f'<div style="{_hdr_style}">Tendance</div>', unsafe_allow_html=True)
    _h2.markdown(f'<div style="{_hdr_style};text-align:right">{_stat_hdr}</div>', unsafe_allow_html=True)
    _h3.markdown(f'<div style="{_hdr_style};text-align:right">M</div>', unsafe_allow_html=True)
    _h4.markdown(f'<div style="{_hdr_style}">Match</div>', unsafe_allow_html=True)
    _h5.markdown('<div></div>', unsafe_allow_html=True)

    for _, row in _df_table.iterrows():
        _slug  = row["player_slug"]
        _excl  = _slug in _excl_set
        _alpha = "0.35" if _excl else "1"
        _rar_raw = (row.get("card_display_rarity") or "").lower().replace(" ", "_")
        _rar_col = _RAR_COLOR.get(_rar_raw, "var(--fg-3)")
        _rar_lbl = (row.get("card_display_rarity") or "").upper()
        _pos     = row.get("position_agg") or "?"
        _is_tag  = ('<span class="tag is" style="margin:0">IS</span>'
                    if row.get("in_season_eligible") is True
                    else ('<span class="tag classic" style="margin:0">OOS</span>'
                          if row.get("in_season_eligible") is False else ""))
        _pp_tag  = '<span class="tag pp" style="margin:0">PP</span>' if row.get("is_pp") else ""
        _spark   = gen_bar_sparkline_svg(_spark_map.get(_slug, []), target=target)
        _moy     = (str(int(row.get("nb_objectif", 0))) if target > 0
                    else f'{row["moyenne"]:.2f}')
        _matchs  = int(row["nb_matchs"])
        _heure   = row.get("coup_envoi") or "—"
        _matchup = row.get("matchup") or "—"
        _name_style = "text-decoration:line-through;color:var(--fg-3)" if _excl else ""

        _c0, _c1, _c2, _c3, _c4, _c5 = st.columns(_COL_W, vertical_alignment="center", gap="small")
        with _c0:
            st.markdown(
                f'<div style="opacity:{_alpha};padding:4px 0">'
                f'<div class="t1-name" style="{_name_style}">{row["player_name"]}</div>'
                f'<div class="t1-meta">'
                f'<span style="color:{_rar_col}">{_rar_lbl}</span>'
                f'<span style="color:var(--fg-3)">·</span>'
                f'<span>{_pos}</span>'
                f'{_is_tag}{_pp_tag}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with _c1:
            st.markdown(
                f'<div style="opacity:{_alpha};padding:6px 0">{_spark}</div>',
                unsafe_allow_html=True,
            )
        with _c2:
            st.markdown(
                f'<div style="opacity:{_alpha};text-align:right;padding:8px 0;'
                f'font-family:var(--mono);font-size:11px;color:var(--pos)">{_moy}</div>',
                unsafe_allow_html=True,
            )
        with _c3:
            st.markdown(
                f'<div style="opacity:{_alpha};text-align:right;padding:8px 0;'
                f'font-family:var(--mono);font-size:10px;color:var(--fg-3)">{_matchs}</div>',
                unsafe_allow_html=True,
            )
        with _c4:
            st.markdown(
                f'<div style="opacity:{_alpha};padding:8px 0;'
                f'font-family:var(--mono);font-size:10px;color:var(--fg-2)">'
                f'{_heure} · {_matchup}</div>',
                unsafe_allow_html=True,
            )
        with _c5:
            _btn_lbl  = "↩" if _excl else "✕"
            _btn_help = "Réintégrer" if _excl else "Exclure"
            if st.button(_btn_lbl, key=f"excl_{_slug}_{_day_key}",
                         help=_btn_help):
                if _excl:
                    st.session_state[_excl_key] = [s for s in st.session_state[_excl_key]
                                                   if s != _slug]
                else:
                    st.session_state[_excl_key] = list(_excl_set | {_slug})
                st.rerun()

    _hist_names = df_view["player_name"].tolist()
    _hist_sel = st.selectbox(
        "📊 Historique", ["—"] + _hist_names,
        key="tab1_hist_sel", label_visibility="collapsed",
    )
    if _hist_sel and _hist_sel != "—":
        _hist_row = df_view[df_view["player_name"] == _hist_sel].iloc[0]
        show_player_chart(_hist_row["player_slug"], _hist_row["player_name"],
                          sel_stat, sel_stat_label, target)
