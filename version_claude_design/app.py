import pandas as pd
import streamlit as st

from data_loaders import (
    load_data, load_calendar, load_card_prices, load_ml_predictions,
    load_leaderboard_rewards, load_all_players_market,
    load_upcoming_pitchers, load_injured_players, load_today_games, load_team_codes,
    render_ticker, render_statusbar, compact_multiselect,
    _matchup, _game_date_str, _team_abbr, _load_pp_today,
    PARIS_TZ, FENETRE_OPTIONS, RARITY_ORDER, _DATA_DIR,
)
from tabs import (
    tab1_defis, tab2_cartes, tab3_database, tab4_visavis, tab5_projections,
    tab6_equipe, tab7_competitions, tab8_lineups, tab9_marche, tab10_docs, tab11_lancers,
)

st.set_page_config(layout="wide", page_title="Sorare MLB", page_icon="⚾")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg-0:#07090c; --bg-1:#0c1014; --bg-2:#11161d; --bg-3:#161d26; --bg-4:#1b232e;
  --line:#1f2935; --line-2:#2a3543; --line-3:#3a4654;
  --fg-0:#e6ebf2; --fg-1:#aab4c2; --fg-2:#6b7585; --fg-3:#4a5260;
  --pos:#4ade80; --neg:#ff5d5d; --warn:#fbbf24; --info:#5fb3ff;
  --accent:#6ff0c8; --accent-2:#a78bfa;
  --r-unique:#ac11ff; --r-superrare:#179eff; --r-rare:#de000b; --r-limited:#f7b100;
  --mono:'JetBrains Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  --sans:'Inter',system-ui,-apple-system,sans-serif;
}

/* ── Streamlit reset ── */
html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg-0) !important;
  color: var(--fg-0) !important;
  font-family: var(--mono) !important;
  font-size: 12px; line-height: 1.45;
}
[data-testid="stHeader"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stSidebar"] {
  background: var(--bg-1) !important;
  border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebar"] > div > div { padding-top: 0 !important; }
.block-container { padding: 0.75rem 1.25rem 3rem !important; max-width: none !important; }

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-1); }
::-webkit-scrollbar-thumb { background: var(--line-2); border-radius: 0; }

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: var(--bg-1) !important; border-bottom: 1px solid var(--line) !important; gap: 0 !important;
}
[data-testid="stTabs"] button[role="tab"] {
  font-family: var(--mono) !important; font-size: 10px !important; font-weight: 500 !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important;
  color: var(--fg-2) !important; border-right: 1px solid var(--line) !important;
  border-radius: 0 !important; padding: 9px 14px !important;
  background: transparent !important; transition: color 120ms, background 120ms !important;
}
[data-testid="stTabs"] button[role="tab"]:hover { color: var(--fg-0) !important; background: var(--bg-2) !important; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  color: var(--fg-0) !important; background: var(--bg-2) !important;
  border-bottom: 2px solid var(--accent) !important;
}

/* ── Radios → segmented control ── */
[data-testid="stRadio"] > div { display: flex !important; flex-direction: row !important; gap: 0 !important; border: 1px solid var(--line-2) !important; }
[data-testid="stRadio"] label {
  flex: 1 !important; padding: 5px 8px !important; font-family: var(--mono) !important;
  font-size: 10px !important; letter-spacing: 0.06em !important; text-transform: uppercase !important;
  text-align: center !important; border-right: 1px solid var(--line-2) !important;
  margin: 0 !important; color: var(--fg-2) !important; white-space: nowrap !important;
}
[data-testid="stRadio"] label:last-child { border-right: none !important; }
[data-testid="stRadio"] label:has(input:checked) { background: var(--bg-3) !important; color: var(--accent) !important; }

/* ── Selectbox ── */
[data-baseweb="select"] > div {
  background: var(--bg-2) !important; border: 1px solid var(--line-2) !important;
  border-radius: 0 !important; font-family: var(--mono) !important; font-size: 11px !important; color: var(--fg-0) !important;
}
[data-baseweb="select"] svg { color: var(--fg-2) !important; }

/* ── Inputs ── */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
  background: var(--bg-2) !important; border: 1px solid var(--line-2) !important;
  border-radius: 0 !important; font-family: var(--mono) !important; font-size: 11px !important;
  color: var(--fg-0) !important; padding: 6px 10px !important;
}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {
  border-color: var(--accent) !important; box-shadow: none !important;
}

/* ── Buttons ── */
[data-testid="stButton"] > button {
  font-family: var(--mono) !important; font-size: 10px !important; font-weight: 500 !important;
  letter-spacing: 0.06em !important; text-transform: uppercase !important;
  border-radius: 0 !important; border: 1px solid var(--line-2) !important;
  background: var(--bg-2) !important; color: var(--fg-1) !important;
  padding: 5px 12px !important; transition: all 120ms !important;
}
[data-testid="stButton"] > button:hover { border-color: var(--line-3) !important; background: var(--bg-3) !important; color: var(--fg-0) !important; }
[data-testid="stButton"] > button[kind="primary"] { background: rgba(111,240,200,0.08) !important; border-color: rgba(111,240,200,0.4) !important; color: var(--accent) !important; }

/* ── Metrics ── */
[data-testid="stMetric"] {
  background: var(--bg-1) !important; border: 1px solid var(--line) !important;
  border-radius: 0 !important; padding: 10px 12px !important;
}
[data-testid="stMetricLabel"] {
  font-family: var(--mono) !important; font-size: 9px !important; font-weight: 500 !important;
  text-transform: uppercase !important; letter-spacing: 0.14em !important; color: var(--fg-3) !important;
}
[data-testid="stMetricValue"] { font-family: var(--mono) !important; font-size: 20px !important; font-weight: 600 !important; color: var(--fg-0) !important; }

/* ── DataFrames ── */
[data-testid="stDataFrame"] { border: 1px solid var(--line) !important; border-radius: 0 !important; }
[data-testid="stDataFrame"] thead th {
  background: var(--bg-2) !important; color: var(--fg-3) !important;
  font-family: var(--mono) !important; font-size: 9px !important;
  text-transform: uppercase !important; letter-spacing: 0.14em !important; font-weight: 500 !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] { border: 1px solid var(--line) !important; border-radius: 0 !important; background: var(--bg-1) !important; }
[data-testid="stExpander"] summary { font-family: var(--mono) !important; font-size: 10px !important; letter-spacing: 0.06em !important; color: var(--fg-1) !important; padding: 8px 12px !important; }

/* ── Dividers / Captions / Alerts ── */
hr { border-color: var(--line) !important; margin: 10px 0 !important; }
[data-testid="stCaptionContainer"] p { font-family: var(--mono) !important; font-size: 9px !important; color: var(--fg-3) !important; letter-spacing: 0.06em !important; }
[data-testid="stAlert"] { border-radius: 0 !important; border: 1px solid var(--line) !important; font-family: var(--mono) !important; font-size: 11px !important; }

/* ═══ TERMINAL COMPONENTS ═══ */

/* ── Ticker ── */
.ticker {
  display: flex; align-items: center;
  background: var(--bg-1); border-bottom: 1px solid var(--line);
  font-size: 11px; font-family: var(--mono);
  overflow: hidden; height: 34px;
  margin: -0.75rem -1.25rem 1rem;
}
.ticker__brand {
  display: flex; align-items: center; gap: 10px;
  padding: 0 16px; height: 100%; border-right: 1px solid var(--line);
  letter-spacing: 0.08em; font-weight: 600; background: var(--bg-1); flex-shrink: 0; z-index: 2;
}
.ticker__brand-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--accent); box-shadow: 0 0 8px var(--accent);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.ticker__feed { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; }
.ticker__feed-inner {
  display: inline-flex; align-items: center; gap: 28px;
  white-space: nowrap; padding: 0 20px;
  animation: scroll-feed 70s linear infinite;
}
.ticker__feed:hover .ticker__feed-inner { animation-play-state: paused; }
@keyframes scroll-feed { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
.ticker__item { display: inline-flex; align-items: center; gap: 5px; color: var(--fg-1); }
.ticker__item .sym { font-weight: 600; color: var(--fg-0); font-size: 10px; }
.ticker__item .val.pos { color: var(--pos); }
.ticker__item .val.neg { color: var(--neg); }
.ticker__item .val.warn { color: var(--warn); }
.ticker__item .val.info { color: var(--info); }
.ticker__sep { display: inline-flex; align-items: center; padding: 0 18px; color: var(--accent); font-size: 8px; opacity: 0.5; }
.ticker__clock {
  display: flex; align-items: center; gap: 12px;
  padding: 0 14px; height: 100%; border-left: 1px solid var(--line);
  color: var(--fg-2); font-size: 10px; background: var(--bg-1); flex-shrink: 0; z-index: 2;
}
.ticker__clock .live { display: inline-flex; align-items: center; gap: 5px; color: var(--pos); }
.ticker__clock .live::before {
  content: ""; width: 5px; height: 5px; border-radius: 50%;
  background: var(--pos); box-shadow: 0 0 6px var(--pos);
  animation: pulse 1.5s ease-in-out infinite;
}

/* ── Panel ── */
.panel { background: var(--bg-1); border: 1px solid var(--line); margin-bottom: 12px; }
.panel__hd {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; border-bottom: 1px solid var(--line);
  font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--fg-2);
}
.panel__hd .title { color: var(--fg-0); font-weight: 600; font-size: 11px; letter-spacing: 0.06em; }
.panel__hd .pill { font-size: 9px; padding: 1px 6px; border: 1px solid var(--line-2); color: var(--fg-1); }
.panel__hd .pill.live { color: var(--pos); border-color: rgba(74,222,128,0.4); }
.panel__hd .pill.accent { color: var(--accent); border-color: rgba(111,240,200,0.3); }
.panel__hd .right { margin-left: auto; display: flex; align-items: center; gap: 8px; color: var(--fg-2); white-space: nowrap; }
.panel__bd { padding: 12px 14px; }

/* ── Metrics ── */
.metrics {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  border-top: 1px solid var(--line); border-left: 1px solid var(--line);
  background: var(--bg-1); margin-bottom: 12px;
}
.metric { padding: 10px 12px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.metric .k { font-size: 9px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--fg-3); margin-bottom: 4px; }
.metric .v { font-size: 20px; font-weight: 600; color: var(--fg-0); letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }
.metric .v.pos { color: var(--pos); }
.metric .v.neg { color: var(--neg); }
.metric .v.warn { color: var(--warn); }
.metric .v.accent { color: var(--accent); }
.metric .v.info { color: var(--info); }
.metric .big { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; }
.metric .sub { font-size: 10px; color: var(--fg-2); margin-top: 3px; }

/* ── Lineup summary (5 cells) ── */
.lineup-summary { display: grid; grid-template-columns: 1.4fr 1fr 1fr 1fr 1fr; border-left: 1px solid var(--line); }
.ls-cell { padding: 12px 14px; border-right: 1px solid var(--line); }
.ls-cell .k { font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--fg-3); margin-bottom: 6px; }
.ls-cell .v { font-size: 22px; font-weight: 600; color: var(--fg-0); font-variant-numeric: tabular-nums; }
.ls-cell .v.pos { color: var(--pos); } .ls-cell .v.warn { color: var(--warn); } .ls-cell .v.accent { color: var(--accent); }
.ls-cell .sub { font-size: 10px; color: var(--fg-2); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ls-cell .headline { display: flex; align-items: baseline; gap: 10px; }
.ls-cell .headline .big { font-size: 26px; font-weight: 700; color: var(--fg-0); letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }

/* ── Player card (pcard) ── */
.pcard {
  background: var(--bg-1); border: 1px solid var(--line);
  position: relative; cursor: pointer; display: flex; flex-direction: column;
  transition: border-color 120ms;
}
.pcard:hover { border-color: var(--line-3); }
.pcard.rank-1 { border-left: 2px solid #FFD700; }
.pcard.rank-2 { border-left: 2px solid #C0C0C0; }
.pcard.rank-3 { border-left: 2px solid #CD7F32; }
.pcard__hd { display: flex; align-items: center; gap: 8px; padding: 9px 11px; border-bottom: 1px solid var(--line); }
.pcard__rank { font-size: 16px; font-weight: 700; color: var(--fg-0); min-width: 24px; }
.pcard__rank.r1 { color: #FFD700; } .pcard__rank.r2 { color: #C0C0C0; } .pcard__rank.r3 { color: #CD7F32; }
.pcard__head-info { flex: 1; line-height: 1.2; min-width: 0; }
.pcard__name { color: var(--fg-0); font-weight: 600; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pcard__sub { color: var(--fg-2); font-size: 10px; margin-top: 2px; letter-spacing: 0.03em; }
.pcard__rarity-dot { width: 7px; height: 7px; display: inline-block; flex-shrink: 0; }
.pcard__art {
  height: 113px;
  background: repeating-linear-gradient(135deg, rgba(255,255,255,0.02) 0 6px, transparent 6px 12px),
    var(--team-grad, linear-gradient(135deg,#1b232e,#11161d));
  border-bottom: 1px solid var(--line);
  display: flex; align-items: center; justify-content: center;
  position: relative; overflow: hidden;
}
.pcard__art::before { content:""; position:absolute; inset:0; background:linear-gradient(180deg,transparent 50%,rgba(0,0,0,0.5)); }
.pcard__art-body { display:flex; align-items:center; justify-content:center; gap:10px; z-index:1; position:relative; width:100%; height:100%; padding:8px 12px; box-sizing:border-box; }
.pcard__monogram { font-weight: 700; font-size: 30px; color: rgba(255,255,255,0.8); letter-spacing: -0.04em; text-shadow: 0 2px 8px rgba(0,0,0,0.4); flex-shrink:0; }
.pcard__art-tag { position: absolute; top: 7px; right: 7px; font-size: 8px; letter-spacing: 0.1em; padding: 1px 5px; background: rgba(0,0,0,0.55); color: rgba(255,255,255,0.85); border: 1px solid rgba(255,255,255,0.15); z-index: 2; white-space: nowrap; }
.pcard__card-img { height: 100%; width: auto; max-width: 42%; object-fit: contain; object-position: top center; opacity: 0.78; flex-shrink: 0; }
.pcard__art-spark-wrap { flex:1; display:flex; align-items:center; justify-content:center; min-width:0; }
.pcard__row { display: grid; grid-template-columns: 1fr 1fr 1fr; border-top: 1px solid var(--line); }
.pcard__row .cell { padding: 7px 9px; border-right: 1px solid var(--line); }
.pcard__row .cell:last-child { border-right: none; }
.pcard__row .k { font-size: 8px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--fg-3); margin-bottom: 2px; }
.pcard__row .v { font-size: 13px; font-weight: 600; color: var(--fg-0); font-variant-numeric: tabular-nums; }
.pcard__row .v.pos { color: var(--pos); } .pcard__row .v.dim { color: var(--fg-2); }
.pcard__spark { height: 32px; padding: 5px 9px; border-top: 1px solid var(--line); display: flex; align-items: center; gap: 6px; }
.pcard__spark svg { flex: 1; }
.pcard__meta { display: flex; align-items: center; gap: 5px; padding: 7px 9px; border-top: 1px solid var(--line); font-size: 10px; color: var(--fg-2); flex-wrap: wrap; }
.tag { font-size: 9px; padding: 1px 5px; border: 1px solid var(--line-2); color: var(--fg-1); letter-spacing: 0.04em; white-space: nowrap; }
.tag.is { color: var(--pos); border-color: rgba(74,222,128,0.35); }
.tag.classic { color: var(--info); border-color: rgba(95,179,255,0.35); }
.tag.pp { color: var(--warn); border-color: rgba(251,191,36,0.35); }
.tag.rarity-unique     { color: var(--r-unique);    border-color: rgba(172,17,255,0.35); }
.tag.rarity-super_rare { color: var(--r-superrare); border-color: rgba(23,158,255,0.35); }
.tag.rarity-rare       { color: var(--r-rare);      border-color: rgba(222,0,11,0.35); }
.tag.rarity-limited    { color: var(--r-limited);   border-color: rgba(247,177,0,0.35); }

/* ── Lineup 7-slot grid ── */
.lineup-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; margin-bottom: 12px; }
.slot { background: var(--bg-1); border: 1px solid var(--line); display: flex; flex-direction: column; }
.slot__label { display: flex; align-items: center; justify-content: space-between; padding: 5px 9px; font-size: 9px; letter-spacing: 0.14em; color: var(--fg-2); border-bottom: 1px solid var(--line); background: var(--bg-2); text-transform: uppercase; }
.slot__label .num { color: var(--fg-3); font-weight: 500; }
.pred-strip { display: grid; grid-template-columns: 1fr 1fr 1fr; border-top: 1px solid var(--line); }
.pred-strip .cell { padding: 7px 5px; text-align: center; border-right: 1px solid var(--line); }
.pred-strip .cell:last-child { border-right: none; }
.pred-strip .k { font-size: 8px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--fg-3); margin-bottom: 2px; }
.pred-strip .v { font-size: 13px; font-weight: 600; color: var(--fg-0); font-variant-numeric: tabular-nums; }
.pred-strip .v.pos { color: var(--pos); } .pred-strip .v.neg { color: var(--neg); } .pred-strip .v.dim { color: var(--fg-3); }

/* ── Position pills ── */
.pos-pill { display: inline-block; padding: 2px 5px; font-size: 10px; letter-spacing: 0.04em; background: var(--bg-3); border: 1px solid var(--line-2); color: var(--fg-0); min-width: 28px; text-align: center; }
.pos-pill.sp, .pos-pill.rp { color: var(--info); border-color: rgba(95,179,255,0.35); }
.pos-pill.ci, .pos-pill.mi { color: var(--accent); border-color: rgba(111,240,200,0.35); }
.pos-pill.of { color: var(--warn); border-color: rgba(251,191,36,0.35); }
.pos-pill.flex { color: var(--accent-2); border-color: rgba(167,139,250,0.4); }

/* ── Manager row (sidebar) ── */
.manager-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-bottom: 1px solid var(--line); background: var(--bg-2); }
.manager-avatar { width: 28px; height: 28px; flex-shrink: 0; background: linear-gradient(135deg,var(--accent),var(--accent-2)); color: var(--bg-0); font-weight: 700; font-size: 11px; display: flex; align-items: center; justify-content: center; }
.manager-info { line-height: 1.2; min-width: 0; }
.manager-info .name { color: var(--fg-0); font-weight: 600; font-size: 12px; }
.manager-info .sub  { color: var(--fg-2); font-size: 10px; }

/* ── Statusbar ── */
.statusbar { position: fixed; bottom: 0; left: 0; right: 0; z-index: 200; display: flex; align-items: center; background: var(--bg-1); border-top: 1px solid var(--line); font-size: 10px; font-family: var(--mono); height: 24px; }
.statusbar__cell { padding: 0 12px; height: 100%; display: flex; align-items: center; gap: 5px; border-right: 1px solid var(--line); }
.statusbar__cell:last-child { border-right: none; }
.statusbar__cell .k { color: var(--fg-3); }
.statusbar__cell .v { color: var(--fg-1); }
.statusbar__spacer { flex: 1; }

/* ── Dots ── */
.dot { width: 5px; height: 5px; border-radius: 50%; background: var(--fg-3); display: inline-block; }
.dot.live { background: var(--pos); box-shadow: 0 0 5px var(--pos); animation: pulse 1.5s ease-in-out infinite; }
.dot.warn { background: var(--warn); }

/* ── Toolbar ── */
.toolbar { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: var(--bg-2); border: 1px solid var(--line); border-bottom: none; font-size: 10px; }
.toolbar__sep { width: 1px; height: 14px; background: var(--line-2); }
.toolbar .lbl { color: var(--fg-3); font-size: 9px; text-transform: uppercase; letter-spacing: 0.12em; }

/* ── Misc ── */
.divider-h { height: 1px; background: var(--line); margin: 12px 0; }

/* ── Tab1 ranking table ── */
.t1-table { width: 100%; border-collapse: collapse; font-family: var(--mono); font-size: 11px; }
.t1-table thead th { font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--fg-3); padding: 7px 10px; border-bottom: 1px solid var(--line); text-align: left; font-weight: 400; white-space: nowrap; }
.t1-table thead th.r { text-align: right; }
.t1-table tbody tr { border-bottom: 1px solid rgba(255,255,255,0.03); }
.t1-table tbody tr:hover { background: var(--bg-2); }
.t1-table td { padding: 7px 10px; vertical-align: middle; }
.t1-player { min-width: 130px; }
.t1-name { color: var(--fg-0); font-weight: 600; font-size: 11px; white-space: nowrap; }
.t1-meta { color: var(--fg-3); font-size: 9px; margin-top: 2px; display: flex; gap: 5px; align-items: center; }
.t1-spark { width: 92px; padding-right: 4px; }
.t1-num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.t1-heure { text-align: right; color: var(--fg-2); white-space: nowrap; }
.t1-adv { color: var(--fg-2); white-space: nowrap; }
.t1-hist { padding: 2px 6px; background: transparent; border: 1px solid var(--line-2); color: var(--fg-3); font-family: var(--mono); font-size: 9px; cursor: pointer; letter-spacing: 0.06em; }
.t1-hist:hover { border-color: var(--accent); color: var(--accent); }
.t1-col-hdr { display:flex; align-items:center; padding:5px 0 4px; border-bottom:1px solid var(--line); font-family:var(--mono); font-size:9px; letter-spacing:0.12em; text-transform:uppercase; color:var(--fg-3); font-weight:400; }
.empty-state { padding: 40px 20px; text-align: center; color: var(--fg-2); font-size: 11px; }
.spark-line { stroke: var(--accent); stroke-width: 1.2; fill: none; }
.spark-fill { fill: var(--accent); opacity: 0.1; }
</style>
""", unsafe_allow_html=True)


def _check_password() -> bool:
    try:
        pwd = st.secrets["APP_PASSWORD"]
    except Exception:
        return True
    if st.session_state.get("_authenticated"):
        return True
    with st.form("login"):
        st.markdown("### ⚾ Sorare MLB")
        entered = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Connexion")
    if submitted:
        if entered == pwd:
            st.session_state["_authenticated"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    return False


if not _check_password():
    st.stop()

# ── Chargement ─────────────────────────────────────────────────────────────────

df_all      = load_data()
df_calendar = load_calendar()
df_prices   = load_card_prices()
df_ml       = load_ml_predictions()
df_lb       = load_leaderboard_rewards()
df_market   = load_all_players_market()

_slug_name_map: dict = (
    df_all.drop_duplicates("player_slug")
    .set_index("player_slug")["player_name"]
    .to_dict()
)

now_utc    = pd.Timestamp.now(tz="UTC")
now_paris  = now_utc.astimezone(PARIS_TZ)
today_paris = now_paris.date()

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        '<div style="padding:10px 12px;border-bottom:1px solid var(--line);'
        'background:var(--bg-1);font-family:var(--mono);margin:-1rem -1rem 0">'
        '<div style="font-size:11px;font-weight:700;letter-spacing:0.14em;'
        'text-transform:uppercase;color:var(--fg-0)">SORARE·MLB</div>'
        '<div style="font-size:9px;color:var(--fg-3);letter-spacing:0.12em;margin-top:1px">TERMINAL v2.4</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    managers = sorted(df_all["gallery_manager"].dropna().unique())
    if len(managers) > 1:
        sel_manager = st.selectbox("Manager", managers)
        initials = "".join(p[0].upper() for p in sel_manager.split()[:2])
    else:
        sel_manager = managers[0] if managers else None
        initials = "".join(p[0].upper() for p in (sel_manager or "??").split()[:2])

    ncards_mgr = len(df_all[df_all["gallery_manager"] == sel_manager]) if sel_manager else 0
    st.markdown(
        f'<div class="manager-row">'
        f'<div class="manager-avatar">{initials}</div>'
        f'<div class="manager-info">'
        f'<div class="name">{sel_manager or "—"}</div>'
        f'<div class="sub">{ncards_mgr} cartes</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:9px;letter-spacing:0.14em;text-transform:uppercase;'
                'color:var(--fg-3);padding:6px 0 4px">Filtres galerie</div>', unsafe_allow_html=True)

    categorie = st.radio("Catégorie", ["HITTING", "PITCHING"], horizontal=True)

    stats_dispo   = (
        df_all[df_all["category"] == categorie][["stat_short_name", "stat"]]
        .drop_duplicates()
        .sort_values("stat_short_name")
    )
    stat_labels_list = stats_dispo["stat_short_name"].tolist()
    stat_keys_list   = stats_dispo["stat"].tolist()
    sel_stat_label   = st.selectbox("Statistique", stat_labels_list)
    sel_stat         = stat_keys_list[stat_labels_list.index(sel_stat_label)]

    fenetre = st.radio("Fenêtre", list(FENETRE_OPTIONS.keys()), index=1, horizontal=True)

    target = st.number_input(
        "🎯 Objectif", min_value=0, value=0, step=1,
        format="%d",
        help="Seuil visuel dans le graphique historique",
    )

    st.divider()

    df_manager = df_all[df_all["gallery_manager"] == sel_manager]
    positions_dispo = sorted(df_manager["position_agg"].dropna().unique())
    sel_positions   = compact_multiselect("Positions", positions_dispo, key="filter_pos")
    raretés_dispo   = sorted(
        df_manager["card_display_rarity"].dropna().unique(),
        key=lambda r: RARITY_ORDER.get(r.lower() if r else "", 99),
    )
    sel_raretés = compact_multiselect("Raretés", raretés_dispo, key="filter_rar")

    st.divider()
    st.caption("Filtre calendrier")
    _days_cal = set(
        df_calendar[
            (df_calendar["gallery_manager"] == sel_manager) &
            (df_calendar["next_game_date"].dt.date >= today_paris)
        ]["next_game_date"].dt.date.unique()
    )
    _games_all = pd.read_parquet(_DATA_DIR / "games.parquet")
    _games_all["game_date"] = pd.to_datetime(_games_all["game_date"], utc=True, errors="coerce")
    _days_games = set(_games_all[_games_all["game_date"].dt.date >= today_paris]["game_date"].dt.date.unique())
    _avail_days = sorted(_days_cal | _days_games)
    _day_labels = ["Tous les jours"] + [d.strftime("%a %d %b") for d in _avail_days]
    _today_label = today_paris.strftime("%a %d %b")
    _default_idx = _day_labels.index(_today_label) if _today_label in _day_labels else 0
    _sel_day_label = st.selectbox("Jour de match", _day_labels, index=_default_idx, key="sel_day")
    sel_day = (
        _avail_days[_day_labels.index(_sel_day_label) - 1]
        if _sel_day_label != "Tous les jours" else None
    )

    st.divider()
    if st.button("⟳ Rafraîchir", use_container_width=True, key="sidebar_rerun"):
        st.cache_data.clear()
        st.rerun()

# ── Filtrage galerie ────────────────────────────────────────────────────────────

df = df_all[
    (df_all["gallery_manager"] == sel_manager) &
    (df_all["fenetre"] == fenetre) &
    (df_all["stat"] == sel_stat) &
    (df_all["position_agg"].isin(sel_positions)) &
    (df_all["card_display_rarity"].str.lower().isin([r.lower() for r in sel_raretés]))
].copy()

df = (
    df.sort_values("moyenne", ascending=False)
    .drop_duplicates(subset=["player_name", "card_display_rarity"])
    .reset_index(drop=True)
)
df["matchup"]    = df.apply(_matchup, axis=1)
df["coup_envoi"] = df.apply(_game_date_str, axis=1)

stat_avg_map = (
    df_all[(df_all["fenetre"] == fenetre) & (df_all["stat"] == sel_stat)]
    .groupby("player_slug")["moyenne"]
    .first()
    .to_dict()
)

_day_filter    = sel_day if sel_day is not None else today_paris
_injured_slugs = set(load_injured_players())

_games_day = load_today_games(str(_day_filter))
_cal_mgr   = df_calendar[df_calendar["gallery_manager"] == sel_manager][
    ["player_slug", "active_club_slug"]
].drop_duplicates("player_slug")
_slug_club = dict(zip(_cal_mgr["player_slug"], _cal_mgr["active_club_slug"]))

if not _games_day.empty:
    _teams_day = (
        set(_games_day["home_team_slug"].dropna()) |
        set(_games_day["away_team_slug"].dropna())
    )
    _tcodes = load_team_codes()
    _tgi: dict = {}
    for _, _g in _games_day.iterrows():
        _t  = _g["game_date"].astimezone(PARIS_TZ).strftime("%H:%M")
        _ht = _g.get("home_team_slug") or ""
        _at = _g.get("away_team_slug") or ""
        if _ht:
            _tgi[_ht] = {"heure": _t, "home_away": "home", "opp": _team_abbr(_at, _tcodes)}
        if _at:
            _tgi[_at] = {"heure": _t, "home_away": "away", "opp": _team_abbr(_ht, _tcodes)}
    _slugs_today = {s for s, c in _slug_club.items() if c in _teams_day}
else:
    _cal_today   = df_calendar[
        (df_calendar["gallery_manager"] == sel_manager) &
        (df_calendar["next_game_date"].dt.date == _day_filter)
    ]
    _slugs_today = set(_cal_today["player_slug"])
    _tgi         = {}

df_today = (
    df[df["player_slug"].isin(_slugs_today) & ~df["player_slug"].isin(_injured_slugs)]
    .copy().reset_index(drop=True)
)

if _tgi:
    def _matchup_live(row):
        gi = _tgi.get(_slug_club.get(row["player_slug"], ""))
        if gi:
            return f"vs {gi['opp']}" if gi["home_away"] == "home" else f"@ {gi['opp']}"
        return row.get("matchup") or "—"
    def _coup_envoi_live(row):
        gi = _tgi.get(_slug_club.get(row["player_slug"], ""))
        return gi["heure"] if gi else (row.get("coup_envoi") or "—")
    df_today["matchup"]    = df_today.apply(_matchup_live, axis=1)
    df_today["coup_envoi"] = df_today.apply(_coup_envoi_live, axis=1)

_is_map = (
    df_calendar[df_calendar["gallery_manager"] == sel_manager]
    .drop_duplicates("player_slug")
    .set_index("player_slug")["in_season_eligible"]
)
df_today["in_season_eligible"] = df_today["player_slug"].map(_is_map)

_pp_slugs = set(_load_pp_today(str(today_paris)))

try:
    _df_pp_gw, _ = load_upcoming_pitchers()
    if not _df_pp_gw.empty:
        _df_pp_today = _df_pp_gw[_df_pp_gw["game_date"].dt.date == today_paris]
        _pp_slugs.update(_df_pp_today["home_pitcher_slug"].dropna())
        _pp_slugs.update(_df_pp_today["away_pitcher_slug"].dropna())
except Exception:
    pass

df_today["is_pp"] = df_today["player_slug"].isin(_pp_slugs)

if not df_ml.empty:
    _ml_mgr = df_ml[df_ml["gallery_manager"] == sel_manager].drop_duplicates("player_slug")
    _ml_map = _ml_mgr.set_index("player_slug")[["pred_median", "pred_lo", "pred_hi"]]
    df_today["pred_median"] = df_today["player_slug"].map(_ml_map["pred_median"])
    df_today["pred_lo"]     = df_today["player_slug"].map(_ml_map["pred_lo"])
    df_today["pred_hi"]     = df_today["player_slug"].map(_ml_map["pred_hi"])
else:
    df_today["pred_median"] = float("nan")
    df_today["pred_lo"]     = float("nan")
    df_today["pred_hi"]     = float("nan")

# ── Ticker ──────────────────────────────────────────────────────────────────────
render_ticker(df_all, sel_manager, _day_filter)

# ── Tabs ────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
    "🏆 Défis journaliers",
    "💰 Mes cartes",
    "🔍 Base de données",
    "⚔️ Vis-à-vis",
    "📈 Projections GW",
    "🏗️ Équipe",
    "🎖️ Compétitions",
    "📋 Mes lineups",
    "🛒 Marché",
    "📖 Documentation",
    "⚾ Lancers",
])

ctx = {
    "df_all":         df_all,
    "df_today":       df_today,
    "df_prices":      df_prices,
    "df_calendar":    df_calendar,
    "df_ml":          df_ml,
    "df_lb":          df_lb,
    "df_market":      df_market,
    "sel_manager":    sel_manager,
    "sel_stat":       sel_stat,
    "sel_stat_label": sel_stat_label,
    "fenetre":        fenetre,
    "categorie":      categorie,
    "target":         target,
    "sel_day":        sel_day,
    "now_paris":      now_paris,
    "df":             df,
    "_injured_slugs": _injured_slugs,
    "_slug_name_map": _slug_name_map,
}

with tab1:
    tab1_defis.render(ctx)

with tab2:
    tab2_cartes.render(ctx)

with tab3:
    tab3_database.render(ctx)

with tab4:
    tab4_visavis.render(ctx)

with tab5:
    tab5_projections.render(ctx)

with tab6:
    tab6_equipe.render(ctx)

with tab7:
    tab7_competitions.render(ctx)

with tab8:
    tab8_lineups.render(ctx)

with tab9:
    tab9_marche.render(ctx)

with tab10:
    tab10_docs.render(ctx)

with tab11:
    tab11_lancers.render(ctx)

# ── Statusbar ────────────────────────────────────────────────────────────────────
_last_upd = now_paris.strftime("%d %b %Y — %H:%M")
_filters_summary = f"{categorie} · {sel_stat_label} · {fenetre}"
render_statusbar(_last_upd, _filters_summary)
