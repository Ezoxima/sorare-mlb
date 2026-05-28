import streamlit as st
import pandas as pd  # noqa: F401 — utilisé pour pd.notna

from data_loaders import (
    load_db_stats, load_db_sparklines, load_team_codes,
    gen_bar_sparkline_svg, FENETRE_OPTIONS, POSITION_AGG,
)


def render(ctx: dict) -> None:
    sel_stat       = ctx["sel_stat"]
    sel_stat_label = ctx["sel_stat_label"]
    fenetre        = ctx["fenetre"]
    target         = ctx["target"]

    fenetre_int = FENETRE_OPTIONS[fenetre]
    df_db       = load_db_stats(sel_stat, fenetre_int, target)
    team_codes  = load_team_codes()

    # ── Filtres ───────────────────────────────────────────────────────────────
    _fc1, _fc2, _fc3 = st.columns([3, 1, 1])
    with _fc1:
        _pos_opts = sorted(df_db["agg_position"].dropna().unique())
        _sel_pos  = st.multiselect("Position", _pos_opts, default=_pos_opts, key="pos_db")
    with _fc2:
        _top_n = st.number_input("Top N", min_value=5, max_value=500, value=50, step=5)
    with _fc3:
        _max_m    = int(df_db["nb_matchs"].max()) if not df_db.empty else fenetre_int
        _min_m    = st.slider("Matchs min.", 1, _max_m, min(3, _max_m), key="min_m_db")

    df_f = (
        df_db[
            df_db["agg_position"].isin(_sel_pos) &
            (df_db["nb_matchs"] >= _min_m)
        ]
        .head(int(_top_n))
        .reset_index(drop=True)
    )

    # ── En-tête panel ─────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none;margin-top:4px">'
        f'<span class="title">Base de données</span>'
        f'<span class="pill accent">{sel_stat_label}</span>'
        f'<span class="pill">{fenetre}</span>'
        f'<span class="right" style="color:var(--fg-3);font-size:9px">'
        f'{len(df_f)} / {len(df_db)} joueurs</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if df_f.empty:
        st.info("Aucun joueur ne correspond aux filtres.")
        return

    # ── Sparklines ────────────────────────────────────────────────────────────
    _slugs     = tuple(df_f["player_slug"].tolist())
    _spark_map = load_db_sparklines(_slugs, sel_stat_label, n_games=fenetre_int)

    # ── Grille ────────────────────────────────────────────────────────────────
    _COL_W    = [3, 0.6, 0.7, 1.2, 1, 0.6]
    _hdr_base = ("font-family:var(--mono);font-size:9px;letter-spacing:0.12em;"
                 "text-transform:uppercase;color:var(--fg-3);padding:5px 0 4px;"
                 "border-bottom:1px solid var(--line)")
    _hdr_c    = _hdr_base + ";text-align:center"

    _h0, _h1, _h2, _h3, _h4, _h5 = st.columns(_COL_W, gap="small")
    _h0.markdown(f'<div style="{_hdr_base}">Joueur</div>',              unsafe_allow_html=True)
    _h1.markdown(f'<div style="{_hdr_c}">Poste</div>',                  unsafe_allow_html=True)
    _h2.markdown(f'<div style="{_hdr_c}">Équipe</div>',                 unsafe_allow_html=True)
    _h3.markdown(f'<div style="{_hdr_c}">Tendance</div>',               unsafe_allow_html=True)
    _stat_hdr = "Objectif" if target > 0 else sel_stat_label
    _h4.markdown(f'<div style="{_hdr_c}">{_stat_hdr}</div>',           unsafe_allow_html=True)
    _h5.markdown(f'<div style="{_hdr_c}">M</div>',                      unsafe_allow_html=True)

    _RANK_COLOR = ["#f7b100", "#aab4c2", "#cd7f32"]  # or, argent, bronze
    _POS_COLOR  = {
        "SP": "var(--r-rare)", "RP": "var(--r-limited)",
        "OF": "var(--accent)",
        "CI": "#22c55e", "MI": "#3b82f6",
    }

    for rank, (_, row) in enumerate(df_f.iterrows()):
        _slug   = row["player_slug"]
        _name   = row["display_name"] or _slug
        _pos    = row.get("position_exact") or row.get("agg_position") or "?"
        _agg    = row.get("agg_position") or "?"
        _tslug  = str(row.get("team_slug") or "") if pd.notna(row.get("team_slug")) else ""
        _team   = team_codes.get(_tslug) or (_tslug[:3].upper() if _tslug else "—")
        _nb     = int(row["nb_matchs"])
        _spark  = gen_bar_sparkline_svg(_spark_map.get(_slug, []), target=target)
        if target > 0:
            _stat_val = f'{int(row.get("nb_success", 0))}/{_nb}'
        else:
            _stat_val = f'{row["moyenne"]:.2f}'

        _rank_n   = rank + 1
        _rank_col = _RANK_COLOR[rank] if rank < 3 else "var(--fg-3)"
        _pos_col  = _POS_COLOR.get(_agg, "var(--fg-2)")

        _c0, _c1, _c2, _c3, _c4, _c5 = st.columns(_COL_W, vertical_alignment="center", gap="small")

        with _c0:
            st.markdown(
                f'<div style="padding:4px 0;display:flex;align-items:center;gap:6px">'
                f'<span style="font-family:var(--mono);font-size:9px;color:{_rank_col};'
                f'min-width:20px;text-align:right">#{_rank_n}</span>'
                f'<span style="font-size:12px;font-weight:600;color:var(--fg)">{_name}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _c1:
            st.markdown(
                f'<div style="text-align:center;padding:4px 0;font-family:var(--mono);'
                f'font-size:10px;color:{_pos_col}">{_pos}</div>',
                unsafe_allow_html=True,
            )
        with _c2:
            st.markdown(
                f'<div style="text-align:center;padding:4px 0;font-family:var(--mono);'
                f'font-size:10px;color:var(--fg-3)">{_team}</div>',
                unsafe_allow_html=True,
            )
        with _c3:
            st.markdown(
                f'<div style="padding:4px 0;text-align:center">{_spark}</div>',
                unsafe_allow_html=True,
            )
        with _c4:
            st.markdown(
                f'<div style="text-align:center;padding:4px 0;font-family:var(--mono);'
                f'font-size:12px;font-weight:700;color:var(--pos)">{_stat_val}</div>',
                unsafe_allow_html=True,
            )
        with _c5:
            st.markdown(
                f'<div style="text-align:center;padding:4px 0;font-family:var(--mono);'
                f'font-size:10px;color:var(--fg-3)">{_nb}</div>',
                unsafe_allow_html=True,
            )
