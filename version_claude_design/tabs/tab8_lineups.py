import json

import pandas as pd
import streamlit as st

from data_loaders import (
    load_saved_lineups, _delete_lineup, _LINEUPS_FILE, load_game_scores_all,
)


def render(ctx: dict) -> None:
    df_prices   = ctx["df_prices"]
    sel_manager = ctx["sel_manager"]

    _saved = load_saved_lineups()
    _saved_mgr = [l for l in _saved if l.get("manager") == sel_manager]

    if not _saved_mgr:
        st.info("Aucun lineup sauvegardé. Crée une équipe dans l'onglet 🏗️ Équipe puis clique sur 💾 Sauvegarder.")
    else:
        _gs_all = load_game_scores_all()

        _gws_saved   = sorted({l["gw_int"] for l in _saved_mgr}, reverse=True)
        _modes_saved = sorted({l["mode"]   for l in _saved_mgr})

        _fc1, _fc2, _fc3, _fc4 = st.columns([2, 2, 2, 1.5])
        with _fc1:
            _sel_gw10 = st.selectbox(
                "Game Week", _gws_saved,
                format_func=lambda g: f"GW{g}",
                key="l10_gw",
            )
        with _fc2:
            _sel_mode10 = st.selectbox(
                "Mode", ["Tous"] + _modes_saved, key="l10_mode"
            )
        with _fc3:
            _sel_rar10 = st.selectbox(
                "Rareté", ["Toutes", "limited", "rare", "super_rare", "unique"],
                key="l10_rar",
            )
        with _fc4:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("🗑️ Tout supprimer", key="l10_del_all", use_container_width=True):
                st.session_state["l10_confirm_del"] = True
        if st.session_state.get("l10_confirm_del"):
            st.warning(f"Supprimer **tous les {len(_saved_mgr)} lineups** de {sel_manager} ? Cette action est irréversible.")
            _conf1, _conf2 = st.columns([1, 4])
            with _conf1:
                if st.button("✅ Confirmer", key="l10_del_confirm"):
                    _ids_to_del = {l["lineup_id"] for l in _saved_mgr}
                    _remaining  = [l for l in load_saved_lineups() if l.get("lineup_id") not in _ids_to_del]
                    with open(_LINEUPS_FILE, "w", encoding="utf-8") as _f:
                        json.dump(_remaining, _f, ensure_ascii=False, indent=2)
                    st.session_state.pop("l10_confirm_del", None)
                    st.rerun()
            with _conf2:
                if st.button("❌ Annuler", key="l10_del_cancel"):
                    st.session_state.pop("l10_confirm_del", None)
                    st.rerun()

        _lineups10 = [
            l for l in _saved_mgr
            if l["gw_int"] == _sel_gw10
            and (_sel_mode10 == "Tous"    or l["mode"]   == _sel_mode10)
            and (_sel_rar10  == "Toutes"  or l["rarity"] == _sel_rar10)
        ]

        if not _lineups10:
            st.info("Aucun lineup correspond aux filtres.")
        else:
            _gs_gw10 = (
                _gs_all[_gs_all["gw_int"] == _sel_gw10]
                .groupby("player_slug", as_index=False)["score"]
                .sum()
                .set_index("player_slug")["score"]
                .to_dict()
                if not _gs_all.empty else {}
            )
            _has_real = bool(_gs_gw10)

            _pic_map10 = (
                df_prices.drop_duplicates("player_slug")
                .set_index("player_slug")["picture_url"]
                .to_dict()
            )

            def _card10(pdata, real_sc, border_color="#334155"):
                _BG = "#1e293b"
                if not pdata:
                    return (
                        f'<div style="background:{_BG};border:2px dashed #334155;border-radius:12px;'
                        f'padding:12px;text-align:center;min-height:390px;display:flex;'
                        f'align-items:center;justify-content:center;">'
                        f'<span style="color:#475569;font-size:20px">—</span></div>'
                    )
                _slug  = pdata.get("player_slug", "")
                _name  = pdata.get("player_name", "—")
                _pred  = pdata.get("proj_score_eff")
                _pic   = pdata.get("picture_url") or _pic_map10.get(_slug, "")
                _real  = real_sc
                _diff  = round(_real - _pred, 1) if (_real is not None and _pred is not None) else None
                _dc    = "#22c55e" if (_diff is not None and _diff >= 0) else "#ef4444"
                _parts = _name.split()
                _short = _name if len(_name) <= 13 else (f"{_parts[0][0]}. {_parts[-1]}" if len(_parts) > 1 else _name[:13])
                _img   = (
                    f'<img src="{_pic}" style="width:200px;height:auto;border-radius:8px;margin-bottom:8px;display:block;margin-left:auto;margin-right:auto">'
                    if _pic else
                    f'<div style="width:200px;height:267px;background:#334155;border-radius:8px;margin:0 auto 8px"></div>'
                )
                _pred_str = f"{_pred:.1f}" if _pred is not None else "—"
                _real_str = f"{_real:.1f}" if _real is not None else "—"
                _diff_str = f"{_diff:+.1f}" if _diff is not None else "—"
                _real_color = "#e2e8f0" if _real is not None else "#475569"
                return (
                    f'<div style="background:{_BG};border:2px solid {border_color};border-radius:12px;'
                    f'padding:12px 8px;text-align:center">'
                    f'{_img}'
                    f'<div style="display:flex;justify-content:center;gap:16px;margin-top:6px">'
                    f'  <div><div style="font-size:10px;color:#64748b">Prédit</div>'
                    f'       <div style="font-size:16px;color:#94a3b8;font-weight:600">{_pred_str}</div></div>'
                    f'  <div><div style="font-size:10px;color:#64748b">Réel</div>'
                    f'       <div style="font-size:16px;color:{_real_color};font-weight:600">{_real_str}</div></div>'
                    f'  <div><div style="font-size:10px;color:#64748b">Diff</div>'
                    f'       <div style="font-size:16px;color:{_dc};font-weight:700">{_diff_str}</div></div>'
                    f'</div>'
                    f'</div>'
                )

            for _l10 in _lineups10:
                _lid        = _l10["lineup_id"]
                _ldate      = _l10["saved_at"][:16].replace("T", " ")
                _src_label  = _l10.get("score_src", "—")
                _sug_auto10   = (_l10.get("suggested_slots_auto")
                                 or _l10.get("suggested_slots") or {})
                _sug_sorare10 = _l10.get("suggested_slots_sorare") or {}
                _title      = (
                    f"{_l10['mode']} · {_l10['rarity']} · GW{_l10['gw_int']} "
                    f"· {_src_label} — sauvegardé le {_ldate}"
                )

                with st.expander(_title, expanded=True):
                    _rows10 = []
                    for _slot, _sdata in _l10["slots"].items():
                        _sug10  = _sug_auto10.get(_slot)
                        _modif  = bool(
                            _sdata and _sug10 and
                            _sdata.get("card_name") != _sug10.get("card_name")
                        )
                        if not _sdata:
                            _rows10.append({
                                "Slot": _slot, "Joueur": "—",
                                "Prédit": None, "Réel": None, "Diff": None, "✏️": "",
                            })
                            continue
                        _pslug = _sdata.get("player_slug")
                        _pred  = _sdata.get("proj_score_eff")
                        _real  = _gs_gw10.get(_pslug) if _pslug else None
                        _diff  = round(_real - _pred, 1) if (_real is not None and _pred is not None) else None
                        _rows10.append({
                            "Slot":    _slot,
                            "Joueur":  _sdata.get("player_name", "—"),
                            "Prédit":  round(float(_pred), 1) if _pred is not None else None,
                            "Réel":    round(float(_real), 1) if _real is not None else None,
                            "Diff":    _diff,
                            "✏️":      "✏️" if _modif else "",
                        })

                    _df10 = pd.DataFrame(_rows10)

                    _tot_pred = _df10["Prédit"].sum() if _df10["Prédit"].notna().any() else None
                    _tot_real = _df10["Réel"].sum()   if _df10["Réel"].notna().any()   else None
                    _tot_diff = round(_tot_real - _tot_pred, 1) if (_tot_pred is not None and _tot_real is not None) else None

                    _mc = st.columns(3)
                    _mc[0].metric("Score prédit", f"{_tot_pred:.1f} pts" if _tot_pred is not None else "—")
                    _mc[1].metric(
                        "Score réel",
                        f"{_tot_real:.1f} pts" if _tot_real is not None else ("En attente" if not _has_real else "—"),
                    )
                    _mc[2].metric(
                        "Différence",
                        f"{_tot_diff:+.1f} pts" if _tot_diff is not None else "—",
                        delta=f"{_tot_diff:+.1f}" if _tot_diff is not None else None,
                    )

                    if not _has_real:
                        st.caption("Les résultats de cette GW ne sont pas encore disponibles.")

                    _slot_keys10 = list(_l10["slots"].keys())
                    _nc10 = len(_slot_keys10)
                    _col_ratios10 = [0.65] + [1] * _nc10

                    _hdr10 = st.columns(_col_ratios10)
                    _hdr10[0].markdown("")
                    for _ci, _sk in enumerate(_slot_keys10):
                        _hdr10[_ci + 1].markdown(
                            f'<div style="text-align:center;font-size:11px;color:#64748b;font-weight:600">{_sk}</div>',
                            unsafe_allow_html=True,
                        )

                    def _row_label(label, color, proj_total):
                        _pts = f'<div style="font-size:13px;color:{color};font-weight:700;margin-top:4px">{proj_total:.1f} pts</div>' if proj_total is not None else ""
                        return (
                            f'<div style="padding-top:148px;font-weight:600;color:{color};font-size:14px">'
                            f'{label}{_pts}</div>'
                        )

                    _proj_my   = sum(float(v.get("proj_score_eff") or 0) for v in _l10["slots"].values() if v)
                    _proj_ml   = sum(float(v.get("proj_score_eff") or 0) for v in _sug_auto10.values()   if v) if _sug_auto10   else None
                    _proj_gw   = sum(float(v.get("proj_score_eff") or 0) for v in _sug_sorare10.values() if v) if _sug_sorare10 else None

                    _row_a = st.columns(_col_ratios10)
                    _row_a[0].markdown(_row_label("Mon équipe", "#94a3b8", _proj_my), unsafe_allow_html=True)
                    for _ci, _sk in enumerate(_slot_keys10):
                        _pd10 = _l10["slots"].get(_sk)
                        _rl10 = _gs_gw10.get(_pd10.get("player_slug", "")) if _pd10 else None
                        _sug_card10 = (_sug_auto10.get(_sk) or {}).get("card_name") if _sug_auto10 else None
                        _border10 = "#334155" if (not _sug_card10 or not _pd10 or _pd10.get("card_name") == _sug_card10) else "#f59e0b"
                        _row_a[_ci + 1].markdown(_card10(_pd10, _rl10, _border10), unsafe_allow_html=True)

                    _row_b = st.columns(_col_ratios10)
                    _row_b[0].markdown(_row_label("ML", "#60a5fa", _proj_ml), unsafe_allow_html=True)
                    if _sug_auto10:
                        _tot_ml_real = 0.0; _tot_act_ml = 0.0; _n_cmp_ml = 0
                        for _ci, _sk in enumerate(_slot_keys10):
                            _pd10 = _sug_auto10.get(_sk)
                            _rl10 = _gs_gw10.get(_pd10.get("player_slug", "")) if _pd10 else None
                            _play_card10 = (_l10["slots"].get(_sk) or {}).get("card_name")
                            _border10 = "#334155" if (not _pd10 or _pd10.get("card_name") == _play_card10) else "#60a5fa"
                            _row_b[_ci + 1].markdown(_card10(_pd10, _rl10, _border10), unsafe_allow_html=True)
                            if _pd10 and _rl10 is not None and _play_card10 and _pd10.get("card_name") != _play_card10:
                                _tot_ml_real += _rl10
                                _n_cmp_ml += 1
                                _act_rl = _gs_gw10.get((_l10["slots"].get(_sk) or {}).get("player_slug"))
                                if _act_rl is not None:
                                    _tot_act_ml += _act_rl
                        if _has_real and _n_cmp_ml:
                            _delta_ml = round(_tot_act_ml - _tot_ml_real, 1)
                            st.caption(f"Sur les slots différents : **{_delta_ml:+.1f} pts** vs suggestion ML")
                    else:
                        _row_b[1].caption("Suggestion ML non disponible pour ce lineup.")

                    _row_c = st.columns(_col_ratios10)
                    _row_c[0].markdown(_row_label("GW+", "#a78bfa", _proj_gw), unsafe_allow_html=True)
                    if _sug_sorare10:
                        _tot_gw_real = 0.0; _tot_act_gw = 0.0; _n_cmp_gw = 0
                        for _ci, _sk in enumerate(_slot_keys10):
                            _pd10 = _sug_sorare10.get(_sk)
                            _rl10 = _gs_gw10.get(_pd10.get("player_slug", "")) if _pd10 else None
                            _play_card10 = (_l10["slots"].get(_sk) or {}).get("card_name")
                            _border10 = "#334155" if (not _pd10 or _pd10.get("card_name") == _play_card10) else "#a78bfa"
                            _row_c[_ci + 1].markdown(_card10(_pd10, _rl10, _border10), unsafe_allow_html=True)
                            if _pd10 and _rl10 is not None and _play_card10 and _pd10.get("card_name") != _play_card10:
                                _tot_gw_real += _rl10
                                _n_cmp_gw += 1
                                _act_rl = _gs_gw10.get((_l10["slots"].get(_sk) or {}).get("player_slug"))
                                if _act_rl is not None:
                                    _tot_act_gw += _act_rl
                        if _has_real and _n_cmp_gw:
                            _delta_gw = round(_tot_act_gw - _tot_gw_real, 1)
                            st.caption(f"Sur les slots différents : **{_delta_gw:+.1f} pts** vs suggestion GW+")
                    else:
                        _row_c[1].caption("Suggestion GW+ non disponible pour ce lineup.")

                    if st.button("🗑️ Supprimer ce lineup", key=f"del10_{_lid}"):
                        _delete_lineup(_lid)
                        st.rerun()
