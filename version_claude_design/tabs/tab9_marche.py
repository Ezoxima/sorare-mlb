import pandas as pd
import streamlit as st

from data_loaders import load_upcoming_pitchers, load_game_scores_all, POSITION_AGG


def render(ctx: dict) -> None:
    df_ml    = ctx["df_ml"]
    df_market = ctx["df_market"]

    if df_ml.empty:
        st.info("Aucune prédiction ML disponible. Lancez `update_data.py` pour générer les données.")
        return

    try:
        _df_p11, _gw11 = load_upcoming_pitchers()
    except Exception:
        _df_p11, _gw11 = pd.DataFrame(), 0

    _ml11 = df_ml[["player_slug", "player_name", "position", "team_slug",
                    "n_games_gw", "pred_median",
                    "gallery_manager"]].copy()
    _ml11["n_games_gw"]  = pd.to_numeric(_ml11["n_games_gw"],  errors="coerce").fillna(0).astype(int)
    _ml11["pred_median"] = pd.to_numeric(_ml11["pred_median"], errors="coerce")
    _ml11["position_agg"] = _ml11["position"].map(lambda x: POSITION_AGG.get(x, x) if x else x)

    _price_cols11 = ["price_limited_is", "price_limited_oos",
                     "price_rare_is", "price_rare_oos",
                     "price_sr_is", "price_sr_oos",
                     "price_unique_is", "price_unique_oos",
                     "sealable_limited", "sealable_rare", "sealable_sr", "sealable_unique"]

    if not df_market.empty:
        _ml11 = _ml11.merge(
            df_market[["player_slug"] + [c for c in _price_cols11 if c in df_market.columns]],
            on="player_slug", how="left",
        )
    else:
        for c in _price_cols11:
            _ml11[c] = float("nan")

    _gs_hist11 = load_game_scores_all()

    _gw_lbl11 = f"GW{_gw11}" if _gw11 else "prochaine GW"
    st.subheader(f"{_gw_lbl11} — Marché ({len(_ml11)} joueurs)")

    if df_market.empty:
        st.warning(
            "Aucun prix disponible. Lancez `python update_data.py --prices-all` "
            "pour récupérer les prix de tous les joueurs GW (~10k appels API)."
        )
    elif _ml11["price_limited_is"].notna().sum() < len(_ml11) * 0.5:
        st.info(
            f"Prix disponibles pour {_ml11['price_limited_is'].notna().sum()} joueurs sur {len(_ml11)}. "
            "Lancez `python update_data.py --prices-all` pour étendre la couverture."
        )

    _c11a, _c11b, _c11c = st.columns([3, 2, 2])
    with _c11a:
        _pos_filter11 = st.multiselect(
            "Position", ["SP", "RP", "CI", "MI", "OF"],
            default=[], key="mkt11_pos",
        )
    with _c11b:
        _season11 = st.radio(
            "Saison", ["In Season", "Classic"],
            horizontal=True, key="mkt11_season",
        )
    with _c11c:
        _rar11 = st.radio(
            "Rareté", ["Limited", "Rare", "Super Rare", "Unique"],
            horizontal=True, key="mkt11_rar",
        )
    _c11d, _c11e, _c11f, _c11g = st.columns([2, 2, 3, 3])
    with _c11d:
        _only_priced11 = st.checkbox("Avec prix uniquement", value=False, key="mkt11_priced")
    with _c11e:
        _only_gw11 = st.checkbox("En GW uniquement", value=True, key="mkt11_gw")
    with _c11f:
        _n_last11 = st.slider("Derniers matchs (pts)", min_value=1, max_value=20, value=10, key="mkt11_nlast")

    _sfx11  = "is" if _season11 == "In Season" else "oos"
    _slbl11 = "IS" if _season11 == "In Season" else "Classic"

    _RAR_KEY11 = {"Limited": "limited", "Rare": "rare", "Super Rare": "sr", "Unique": "unique"}
    _rar11_key = _RAR_KEY11[_rar11]

    if not _gs_hist11.empty:
        _avg_map11 = (
            _gs_hist11[_gs_hist11["played_in_game"] == True]
            .sort_values("game_date", ascending=False)
            .groupby("player_slug")
            .head(_n_last11)
            .groupby("player_slug")["score"]
            .mean()
            .round(2)
        )
        _ml11["avg_last_x"] = _ml11["player_slug"].map(_avg_map11)
    else:
        _ml11["avg_last_x"] = float("nan")

    _seal_col11 = {"Limited": "sealable_limited", "Rare": "sealable_rare",
                   "Super Rare": "sealable_sr", "Unique": "sealable_unique"}[_rar11]
    _ml11["seal_value"] = pd.to_numeric(
        _ml11[_seal_col11] if _seal_col11 in _ml11.columns else float("nan"),
        errors="coerce",
    )

    _p_is11  = f"price_{_rar11_key}_is"
    _p_oos11 = f"price_{_rar11_key}_oos"
    _min_p11 = _ml11[[c for c in [_p_is11, _p_oos11] if c in _ml11.columns]].min(axis=1)
    _ml11["seal_ratio"] = (
        (_ml11["seal_value"] / _min_p11).replace([float("inf"), float("-inf")], None).round(3)
    )

    _RARS11 = [("Limited", "limited"), ("Rare", "rare"), ("SR", "sr"), ("Unique", "unique")]
    for _rl, _rk in _RARS11:
        _pc = f"price_{_rk}_{_sfx11}"
        _rc = f"ratio_{_rk}"
        if _pc in _ml11.columns:
            _ml11[_rc] = (_ml11["avg_last_x"] / _ml11[_pc]).replace(
                [float("inf"), float("-inf")], None
            ).round(3)

    _RAR11_DISP = [(_rar11, _rar11_key)]

    _sort_opts11 = [f"pts/€ {_rar11}", f"Prix {_rar11}", "Seal ratio"]
    with _c11f:
        _sort11 = st.selectbox("Trier par", _sort_opts11, key="mkt11_sort")

    _sort_map11 = {
        f"pts/€ {_rar11}": f"ratio_{_rar11_key}",
        f"Prix {_rar11}":  f"price_{_rar11_key}_{_sfx11}",
        "Seal ratio":      "seal_ratio",
    }

    _df11 = _ml11.copy()
    if _only_gw11:
        _df11 = _df11[_df11["n_games_gw"] > 0]
    if _pos_filter11:
        _pos_to_raw11 = {
            "SP":  ["SP", "baseball_starting_pitcher"],
            "RP":  ["RP", "baseball_relief_pitcher"],
            "CI":  ["CI", "baseball_first_base", "baseball_third_base", "baseball_designated_hitter"],
            "MI":  ["MI", "baseball_second_base", "baseball_shortstop", "baseball_catcher"],
            "OF":  ["OF", "baseball_outfield"],
        }
        _allowed11 = set()
        for _p in _pos_filter11:
            _allowed11.update(_pos_to_raw11.get(_p, [_p]))
        _df11 = _df11[_df11["position"].isin(_allowed11) | _df11["position_agg"].isin(_pos_filter11)]
    if _only_priced11:
        _price_col11 = f"price_{_rar11_key}_{_sfx11}"
        if _price_col11 in _df11.columns:
            _df11 = _df11[_df11[_price_col11].notna()]

    _sort_key11 = _sort_map11.get(_sort11, f"ratio_{_rar11_key}")
    if _sort_key11 in _df11.columns:
        _df11 = _df11.sort_values(_sort_key11, ascending=False, na_position="last")

    _show_cols11 = ["player_name", "position_agg", "team_slug", "avg_last_x"]
    _display_rename11 = {
        "player_name":    "Joueur",
        "position_agg":   "Pos",
        "team_slug":      "Équipe",
        "avg_last_x":     f"Moy. {_n_last11} matchs",
        "seal_value":     "Seal (€)",
        "seal_ratio":     "Seal ratio",
    }
    _col_cfg11 = {
        "Joueur":              st.column_config.TextColumn(),
        f"Moy. {_n_last11} matchs": st.column_config.NumberColumn(format="%.2f"),
        "Seal (€)":            st.column_config.NumberColumn(format="%.0f"),
        "Seal ratio":          st.column_config.NumberColumn(format="%.3f"),
    }
    for _rl, _rk in _RAR11_DISP:
        _pc = f"price_{_rk}_{_sfx11}"
        _rc = f"ratio_{_rk}"
        _plbl = f"{_rl} {_slbl11} (€)"
        _rlbl = f"pts/€ {_rl}"
        if _pc in _df11.columns:
            _show_cols11.extend([_pc, _rc])
            _display_rename11[_pc] = _plbl
            _display_rename11[_rc] = _rlbl
            _col_cfg11[_plbl] = st.column_config.NumberColumn(format="%.2f")
            _col_cfg11[_rlbl] = st.column_config.NumberColumn(format="%.4f")
    _show_cols11.extend(["seal_value", "seal_ratio"])
    _show_cols11 = [c for c in _show_cols11 if c in _df11.columns]

    st.dataframe(
        _df11[_show_cols11].rename(columns=_display_rename11),
        use_container_width=True,
        column_config=_col_cfg11,
        hide_index=True,
    )
    st.caption(f"{len(_df11)} joueurs · {_slbl11}")
