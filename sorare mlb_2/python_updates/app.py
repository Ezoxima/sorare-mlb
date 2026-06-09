import pandas as pd
import streamlit as st

from data_loaders import (
    load_data, load_calendar, load_card_prices, load_ml_predictions,
    load_leaderboard_rewards, load_all_players_market,
    load_upcoming_pitchers, load_injured_players, load_today_games, load_team_codes,
    load_team_logos, _team_logo_html,
    render_ticker, render_statusbar, compact_multiselect,
    _matchup, _game_date_str, _team_abbr, _load_pp_today,
    load_data_freshness,
    PARIS_TZ, FENETRE_OPTIONS, RARITY_ORDER, _DATA_DIR,
)
from tabs import (
    tab1_defis, tab2_cartes, tab3_database, tab4_visavis, tab5_projections,
    tab6_equipe, tab7_competitions, tab8_lineups, tab9_marche, tab10_docs, tab11_lancers,
)

_STAT_DISPLAY: dict[str, str] = {
    "1B":  "1B - Single",
    "2B":  "2B - Double",
    "3B":  "3B - Triple",
    "BB":  "BB - Walks",
    "CS":  "CS - Caught Stealing",
    "HBP": "HBP - Hit By Pitch",
    "HR":  "HR - Home Runs",
    "RBI": "RBI - Runs Batted In",
    "RUN": "R - Runs",
    "SB":  "SB - Stolen Bases",
    "SO":  "SO - Strikeouts",
    "APP": "APP - Appearances",
    "ER":  "ER - Earned Runs",
    "HA":  "HA - Hits Allowed",
    "HB":  "HB - Hit Batsmen",
    "HLD": "HLD - Holds",
    "IP":  "IP - Innings Pitched",
    "NOH": "NOH - No Hitters",
    "SAV": "SAV - Saves",
    "WIN": "WIN - Wins",
}

st.set_page_config(layout="wide", page_title="Sorare MLB", page_icon="⚾")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

/* ══════════════════════════════════════════════════════
   TOKENS — alignés avec le prototype HTML
   ══════════════════════════════════════════════════════ */
:root {
  --bg-0:#0a0d12; --bg-1:#0e131a; --bg-2:#121823; --bg-3:#1a2230; --bg-4:#1f2a38;
  --line:#1b2330; --line-2:#283242; --line-3:#3a4654;
  --fg-0:#e9eef4; --fg-1:#c0cad6; --fg-2:#8b95a4; --fg-3:#5c6675;
  --pos:#2fd98e; --neg:#e5484d; --warn:#f4b740; --info:#4a9eff;
  --accent:#2fd98e; --accent-2:#a855f7;
  --pos-bg:rgba(47,217,142,.13); --pos-bd:rgba(47,217,142,.5);
  --r-unique:#ac11ff; --r-superrare:#179eff; --r-rare:#ea000c; --r-limited:#f7b100;
  --mono:'JetBrains Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
}

/* ══════════════════════════════════════════════════════
   STREAMLIT RESET
   ══════════════════════════════════════════════════════ */
html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg-0) !important;
  color: var(--fg-0) !important;
  font-family: var(--mono) !important;
  font-size: 12px; line-height: 1.45;
}
[data-testid="stHeader"]     { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stSidebar"] {
  background: var(--bg-1) !important;
  border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebar"] > div > div { padding-top: 0 !important; }
.block-container { padding: 0.75rem 1.25rem 3rem !important; max-width: none !important; }

/* Scrollbars */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-1); }
::-webkit-scrollbar-thumb { background: var(--line-2); border-radius: 0; }

/* ══════════════════════════════════════════════════════
   TABS NAVIGATION
   ══════════════════════════════════════════════════════ */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: var(--bg-1) !important;
  border-bottom: 1px solid var(--line) !important;
  gap: 0 !important;
}
[data-testid="stTabs"] button[role="tab"] {
  font-family: var(--mono) !important; font-size: 10px !important;
  font-weight: 500 !important; letter-spacing: 0.08em !important;
  text-transform: uppercase !important; color: var(--fg-3) !important;
  border-right: 1px solid var(--line) !important; border-radius: 0 !important;
  padding: 9px 14px !important; background: transparent !important;
  transition: color 120ms, background 120ms !important;
}
[data-testid="stTabs"] button[role="tab"]:hover {
  color: var(--fg-0) !important; background: var(--bg-2) !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  color: var(--pos) !important; background: var(--bg-2) !important;
  border-bottom: 2px solid var(--pos) !important;
}

/* ══════════════════════════════════════════════════════
   ST.PILLS — chip style identique au prototype HTML
   ══════════════════════════════════════════════════════ */
[data-testid="stPills"] button {
  border: 1px solid var(--line-2) !important;
  background: var(--bg-2) !important;
  color: var(--fg-2) !important;
  border-radius: 6px !important;
  font-family: var(--mono) !important;
  font-size: 11px !important;
  font-weight: 500 !important;
  text-transform: none !important;
  padding: 7px 12px !important;
  min-height: 0 !important;
  transition: border-color .12s, color .12s, background .12s !important;
  letter-spacing: 0 !important;
}
[data-testid="stPills"] button:hover {
  border-color: var(--fg-3) !important;
  color: var(--fg-1) !important;
}
/* Pill sélectionné → vert */
[data-testid="stPills"] button[aria-checked="true"],
[data-testid="stPills"] [data-testid="stBaseButton-pillsActive"] {
  border-color: var(--pos-bd) !important;
  color: var(--pos) !important;
  background: var(--pos-bg) !important;
}
/* Labels des groupes de filtres */
[data-testid="stPills"] label p,
div[data-testid="stWidgetLabel"] p,
div[data-testid="stWidgetLabel"] label,
div[data-testid="stWidgetLabel"] span {
  font-family: var(--mono) !important;
  font-size: 9px !important; font-weight: 600 !important;
  letter-spacing: .16em !important; text-transform: uppercase !important;
  color: var(--fg-3) !important; margin-bottom: 7px !important;
}

/* ══════════════════════════════════════════════════════
   SELECTBOX
   ══════════════════════════════════════════════════════ */
[data-baseweb="select"] > div {
  background: var(--bg-2) !important;
  border: 1px solid var(--line-2) !important;
  border-radius: 6px !important;
  font-family: var(--mono) !important;
  font-size: 12px !important;
  color: var(--fg-0) !important;
  min-height: 34px !important;
  transition: border-color .12s !important;
}
[data-baseweb="select"] > div:hover { border-color: var(--fg-3) !important; }
[data-baseweb="select"] svg { color: var(--fg-2) !important; }
/* Menu déroulant */
[data-baseweb="popover"] [data-baseweb="menu"] {
  background: var(--bg-1) !important;
  border: 1px solid var(--line-2) !important;
  border-radius: 7px !important;
}
[data-baseweb="option"] {
  background: transparent !important;
  color: var(--fg-1) !important;
  font-family: var(--mono) !important; font-size: 11px !important;
}
[data-baseweb="option"]:hover { background: var(--bg-3) !important; }
[aria-selected="true"] [data-baseweb="option"] {
  color: var(--pos) !important; background: var(--pos-bg) !important;
}

/* ══════════════════════════════════════════════════════
   NUMBER INPUT (Objectif)
   ══════════════════════════════════════════════════════ */
div[data-testid="stNumberInput"] input {
  background: var(--bg-2) !important;
  border: 1px solid var(--line-2) !important;
  border-radius: 6px 0 0 6px !important;
  font-family: var(--mono) !important; font-size: 12px !important;
  color: var(--fg-0) !important;
  text-align: center !important;
  padding: 6px 8px !important;
}
div[data-testid="stNumberInput"] input:focus {
  border-color: var(--pos-bd) !important;
  box-shadow: none !important;
}
div[data-testid="stNumberInput"] button {
  background: var(--bg-2) !important;
  border: 1px solid var(--line-2) !important;
  color: var(--fg-2) !important;
  transition: all .12s !important;
}
div[data-testid="stNumberInput"] button:hover {
  background: var(--bg-3) !important;
  color: var(--fg-0) !important;
}

/* ══════════════════════════════════════════════════════
   INPUTS / TEXT
   ══════════════════════════════════════════════════════ */
[data-testid="stTextInput"] input {
  background: var(--bg-2) !important;
  border: 1px solid var(--line-2) !important;
  border-radius: 6px !important;
  font-family: var(--mono) !important; font-size: 11px !important;
  color: var(--fg-0) !important; padding: 6px 10px !important;
}
[data-testid="stTextInput"] input:focus {
  border-color: var(--pos-bd) !important; box-shadow: none !important;
}

/* ══════════════════════════════════════════════════════
   BUTTONS
   ══════════════════════════════════════════════════════ */
[data-testid="stButton"] > button {
  font-family: var(--mono) !important; font-size: 10px !important;
  font-weight: 500 !important; letter-spacing: 0.06em !important;
  text-transform: uppercase !important; border-radius: 6px !important;
  border: 1px solid var(--line-2) !important;
  background: var(--bg-2) !important; color: var(--fg-1) !important;
  padding: 5px 12px !important; transition: all 120ms !important;
}
[data-testid="stButton"] > button:hover {
  border-color: var(--line-3) !important;
  background: var(--bg-3) !important; color: var(--fg-0) !important;
}
[data-testid="stButton"] > button[kind="primary"] {
  background: var(--pos-bg) !important;
  border-color: var(--pos-bd) !important; color: var(--pos) !important;
}

/* ══════════════════════════════════════════════════════
   METRICS
   ══════════════════════════════════════════════════════ */
[data-testid="stMetric"] {
  background: var(--bg-1) !important; border: 1px solid var(--line) !important;
  border-radius: 0 !important; padding: 10px 12px !important;
}
[data-testid="stMetricLabel"] {
  font-family: var(--mono) !important; font-size: 9px !important;
  font-weight: 500 !important; text-transform: uppercase !important;
  letter-spacing: 0.14em !important; color: var(--fg-3) !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important; font-size: 20px !important;
  font-weight: 600 !important; color: var(--fg-0) !important;
}

/* ══════════════════════════════════════════════════════
   DATAFRAMES
   ══════════════════════════════════════════════════════ */
[data-testid="stDataFrame"] { border: 1px solid var(--line) !important; border-radius: 0 !important; }
[data-testid="stDataFrame"] thead th {
  background: var(--bg-2) !important; color: var(--fg-3) !important;
  font-family: var(--mono) !important; font-size: 9px !important;
  text-transform: uppercase !important; letter-spacing: 0.14em !important;
  font-weight: 500 !important;
}

/* ══════════════════════════════════════════════════════
   EXPANDERS
   ══════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
  border: 1px solid var(--line) !important; border-radius: 0 !important;
  background: var(--bg-1) !important;
}
[data-testid="stExpander"] summary {
  font-family: var(--mono) !important; font-size: 10px !important;
  letter-spacing: 0.06em !important; color: var(--fg-1) !important;
  padding: 8px 12px !important;
}

/* ══════════════════════════════════════════════════════
   MISC
   ══════════════════════════════════════════════════════ */
hr { border-color: var(--line) !important; margin: 10px 0 !important; }
[data-testid="stCaptionContainer"] p {
  font-family: var(--mono) !important; font-size: 9px !important;
  color: var(--fg-3) !important; letter-spacing: 0.06em !important;
}
[data-testid="stAlert"] {
  border-radius: 0 !important; border: 1px solid var(--line) !important;
  font-family: var(--mono) !important; font-size: 11px !important;
}

/* ══════════════════════════════════════════════════════
   BORDERED CONTAINER → panel look (sans border-radius)
   ══════════════════════════════════════════════════════ */
[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--line) !important;
  border-color: var(--line) !important;
  background: var(--bg-1) !important;
  border-radius: 0 !important;
  padding: 4px 14px 14px !important;
}

/* ══════════════════════════════════════════════════════
   TERMINAL COMPONENTS
   ══════════════════════════════════════════════════════ */

/* ── Ticker ── */
.ticker {
  display: flex; align-items: center;
  background: var(--bg-1); border-bottom: 1px solid var(--line);
  font-family: var(--mono); overflow: hidden; height: 46px;
  margin: -0.75rem -1.25rem 1rem;
}
.ticker__brand {
  display: flex; align-items: center; gap: 10px;
  padding: 0 16px; height: 100%; border-right: 1px solid var(--line);
  letter-spacing: 0.08em; font-size: 10px; font-weight: 600;
  background: var(--bg-1); flex-shrink: 0; z-index: 2;
}
.ticker__brand-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--pos); box-shadow: 0 0 8px var(--pos);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.ticker__feed { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; }
.ticker__feed-inner {
  display: inline-flex; align-items: center; gap: 12px;
  white-space: nowrap; padding: 0 16px;
  animation: scroll-feed 80s linear infinite;
}
.ticker__feed:hover .ticker__feed-inner { animation-play-state: paused; }
@keyframes scroll-feed { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
.ticker__item { display: inline-flex; align-items: center; gap: 3px; }
.ticker__team {
  display: inline-flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 3px 6px; min-width: 40px;
}
.ticker__team img { display: block; }
.ticker__abbr { font-size: 8px; font-weight: 700; color: var(--fg-2); letter-spacing: 0.08em; }
.ticker__score {
  display: inline-flex; flex-direction: column; align-items: center; gap: 1px;
  padding: 3px 5px; min-width: 38px;
}
.ticker__vs   { font-size: 7px; color: var(--fg-3); letter-spacing: 0.12em; }
.ticker__time { font-size: 10px; font-weight: 700; color: var(--info); letter-spacing: 0.04em; }
.ticker__sep  { display: inline-block; width: 1px; height: 24px; background: var(--fg-3); margin: 0 14px; opacity: 1; vertical-align: middle; flex-shrink: 0; }
.ticker__sep--day { display: inline-flex; align-items: center; margin: 0 16px; vertical-align: middle; flex-shrink: 0; }
.ticker__sep--day span { width: 5px; height: 5px; border-radius: 50%; background: var(--pos); box-shadow: 0 0 6px var(--pos); display: inline-block; }
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
.panel__hd .pill { font-size: 9px; padding: 2px 7px; border: 1px solid var(--line-2); color: var(--fg-1); border-radius: 4px; }
.panel__hd .pill.live   { color: var(--pos); border-color: var(--pos-bd); }
.panel__hd .pill.accent { color: var(--pos); border-color: var(--pos-bd); }
.panel__hd .right { margin-left: auto; display: flex; align-items: center; gap: 8px; color: var(--fg-2); white-space: nowrap; }
.panel__bd { padding: 12px 14px; }

/* ── Metrics grid ── */
.metrics {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  border-top: 1px solid var(--line); border-left: 1px solid var(--line);
  background: var(--bg-1); margin-bottom: 12px;
}
.metric { padding: 10px 12px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.metric .k { font-size: 9px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--fg-3); margin-bottom: 4px; }
.metric .v { font-size: 20px; font-weight: 600; color: var(--fg-0); letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }
.metric .v.pos    { color: var(--pos); }
.metric .v.neg    { color: var(--neg); }
.metric .v.warn   { color: var(--warn); }
.metric .v.accent { color: var(--pos); }
.metric .v.info   { color: var(--info); }
.metric .big { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; }
.metric .sub { font-size: 10px; color: var(--fg-2); margin-top: 3px; }

/* ── Player card ── */
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
.pcard__sub  { color: var(--fg-2); font-size: 10px; margin-top: 2px; letter-spacing: 0.03em; }
.pcard__rarity-dot { width: 7px; height: 7px; display: inline-block; flex-shrink: 0; }
.pcard__art {
  height: 113px;
  background: repeating-linear-gradient(135deg,rgba(255,255,255,.02) 0 6px,transparent 6px 12px), var(--team-grad,linear-gradient(135deg,#1b232e,#11161d));
  border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: center;
  position: relative; overflow: hidden;
}
.pcard__art::before { content:""; position:absolute; inset:0; background:linear-gradient(180deg,transparent 50%,rgba(0,0,0,.5)); }
.pcard__art-body { display:flex; align-items:center; justify-content:center; gap:10px; z-index:1; position:relative; width:100%; height:100%; padding:8px 12px; }
.pcard__monogram { font-weight:700; font-size:30px; color:rgba(255,255,255,.8); letter-spacing:-0.04em; text-shadow:0 2px 8px rgba(0,0,0,.4); flex-shrink:0; }
.pcard__art-tag  { position:absolute; top:7px; right:7px; font-size:8px; letter-spacing:.1em; padding:1px 5px; background:rgba(0,0,0,.55); color:rgba(255,255,255,.85); border:1px solid rgba(255,255,255,.15); z-index:2; }
.pcard__card-img { height:100%; width:auto; max-width:42%; object-fit:contain; object-position:top center; opacity:.78; flex-shrink:0; }
.pcard__art-spark-wrap { flex:1; display:flex; align-items:center; justify-content:center; min-width:0; }
.pcard__row { display:grid; grid-template-columns:1fr 1fr 1fr; border-top:1px solid var(--line); }
.pcard__row .cell { padding:7px 9px; border-right:1px solid var(--line); }
.pcard__row .cell:last-child { border-right:none; }
.pcard__row .k   { font-size:8px; letter-spacing:.1em; text-transform:uppercase; color:var(--fg-3); margin-bottom:2px; }
.pcard__row .v   { font-size:13px; font-weight:600; color:var(--fg-0); font-variant-numeric:tabular-nums; }
.pcard__row .v.pos { color:var(--pos); } .pcard__row .v.dim { color:var(--fg-2); }
.pcard__spark { height:32px; padding:5px 9px; border-top:1px solid var(--line); display:flex; align-items:center; gap:6px; }
.pcard__meta  { display:flex; align-items:center; gap:5px; padding:7px 9px; border-top:1px solid var(--line); font-size:10px; color:var(--fg-2); flex-wrap:wrap; }

/* ── Tags ── */
.tag { font-size:9px; padding:1px 5px; border:1px solid var(--line-2); color:var(--fg-1); letter-spacing:.04em; white-space:nowrap; border-radius:3px; }
.tag.is      { color:var(--pos);  border-color:var(--pos-bd); }
.tag.classic { color:var(--info); border-color:rgba(74,158,255,.35); }
.tag.pp      { color:var(--warn); border-color:rgba(244,183,64,.35); }
.tag.rarity-unique     { color:var(--r-unique);    border-color:rgba(172,17,255,.35); }
.tag.rarity-super_rare { color:var(--r-superrare); border-color:rgba(23,158,255,.35); }
.tag.rarity-rare       { color:var(--r-rare);      border-color:rgba(234,0,12,.35); }
.tag.rarity-limited    { color:var(--r-limited);   border-color:rgba(247,177,0,.35); }

/* ── Statusbar ── */
.statusbar { position:fixed; bottom:0; left:0; right:0; z-index:200; display:flex; align-items:center; background:var(--bg-1); border-top:1px solid var(--line); font-size:10px; font-family:var(--mono); height:24px; }
.statusbar__cell { padding:0 12px; height:100%; display:flex; align-items:center; gap:5px; border-right:1px solid var(--line); }
.statusbar__cell:last-child { border-right:none; }
.statusbar__cell .k { color:var(--fg-3); }
.statusbar__cell .v { color:var(--fg-1); }
.statusbar__spacer  { flex:1; }
.dot { width:5px; height:5px; border-radius:50%; background:var(--fg-3); display:inline-block; }
.dot.live { background:var(--pos); box-shadow:0 0 5px var(--pos); animation:pulse 1.5s ease-in-out infinite; }
.dot.warn { background:var(--warn); }

/* ── Filtre header ── */
.filt-head {
  display:flex; align-items:center; gap:8px;
  padding:11px 0 12px; border-bottom:1px solid var(--line); margin-bottom:14px;
}
.filt-head .t {
  font-family:var(--mono)!important; font-size:12px!important; font-weight:700!important;
  letter-spacing:.1em!important; text-transform:uppercase!important; color:var(--fg-1)!important;
}
.filt-head .r {
  margin-left:auto; font-family:var(--mono)!important; font-size:9px!important;
  letter-spacing:.1em!important; text-transform:uppercase!important; color:var(--fg-3)!important;
}

/* ── Séparateur vertical entre groupes ── */
.vsep { width:1px; height:52px; background:var(--line); margin:26px auto 0; }

/* ── Dividers ── */
.divider-h { height:1px; background:var(--line); margin:12px 0; }
a.sorare-link { color:inherit; text-decoration:none; border-bottom:1px dotted var(--fg-3); }
a.sorare-link:hover { border-bottom-color:var(--pos); color:var(--pos); }

/* ── Tab1 ranking table ── */
.t1-name { color:var(--fg-0); font-weight:600; font-size:11px; white-space:nowrap; }
.t1-meta { color:var(--fg-3); font-size:9px; margin-top:2px; display:flex; gap:5px; align-items:center; }

/* ── Lineup grid ── */
.lineup-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:10px; margin-bottom:12px; }
.slot { background:var(--bg-1); border:1px solid var(--line); display:flex; flex-direction:column; }
.slot__label { display:flex; align-items:center; justify-content:space-between; padding:5px 9px; font-size:9px; letter-spacing:.14em; color:var(--fg-2); border-bottom:1px solid var(--line); background:var(--bg-2); text-transform:uppercase; }

/* ── Manager sidebar ── */
.manager-row { display:flex; align-items:center; gap:10px; padding:10px 12px; border-bottom:1px solid var(--line); background:var(--bg-2); }
.manager-avatar { width:28px; height:28px; flex-shrink:0; background:linear-gradient(135deg,var(--pos),var(--accent-2)); color:var(--bg-0); font-weight:700; font-size:11px; display:flex; align-items:center; justify-content:center; border-radius:2px; }
.manager-info .name { color:var(--fg-0); font-weight:600; font-size:12px; }
.manager-info .sub  { color:var(--fg-2); font-size:10px; }

/* ── Position pills ── */
.pos-pill { display:inline-block; padding:2px 5px; font-size:10px; letter-spacing:.04em; background:var(--bg-3); border:1px solid var(--line-2); color:var(--fg-0); min-width:28px; text-align:center; border-radius:3px; }
.pos-pill.sp, .pos-pill.rp  { color:var(--info); border-color:rgba(74,158,255,.35); }
.pos-pill.ci, .pos-pill.mi  { color:var(--pos);  border-color:var(--pos-bd); }
.pos-pill.of  { color:var(--warn); border-color:rgba(244,183,64,.35); }
.pos-pill.flex { color:var(--accent-2); border-color:rgba(168,85,247,.4); }

/* ── Rareté : couleurs des 4 boutons du segmented control ── */
[data-testid="stSegmentedControl"]:has(button:nth-child(4)) button:nth-child(1) { color:#f7b100!important; }
[data-testid="stSegmentedControl"]:has(button:nth-child(4)) button:nth-child(2) { color:#ea000c!important; }
[data-testid="stSegmentedControl"]:has(button:nth-child(4)) button:nth-child(3) { color:#179eff!important; }
[data-testid="stSegmentedControl"]:has(button:nth-child(4)) button:nth-child(4) { color:#ac11ff!important; }
[data-testid="stSegmentedControl"] button { font-size:12px!important; padding:5px 14px!important; min-height:34px; }

/* ── Rareté : couleurs des pills quand il y en a 4 ── */
[data-testid="stPills"]:has(button:nth-child(4)) button:nth-child(1):not([aria-checked="true"]) { color:var(--r-limited)!important; }
[data-testid="stPills"]:has(button:nth-child(4)) button:nth-child(2):not([aria-checked="true"]) { color:var(--r-rare)!important; }
[data-testid="stPills"]:has(button:nth-child(4)) button:nth-child(3):not([aria-checked="true"]) { color:var(--r-superrare)!important; }
[data-testid="stPills"]:has(button:nth-child(4)) button:nth-child(4):not([aria-checked="true"]) { color:var(--r-unique)!important; }

/* ── Spark SVG ── */
.spark-line { stroke:var(--pos); stroke-width:1.2; fill:none; }
.spark-fill { fill:var(--pos); opacity:.1; }
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
        '<div style="padding:10px 12px;border-bottom:1px solid var(--line);"
        "background:var(--bg-1);font-family:var(--mono);margin:-1rem -1rem 0">'
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

    st.markdown(
        f'<div class="manager-row">'
        f'<div class="manager-avatar">{initials}</div>'
        f'<div class="manager-info">'
        f'<div class="name">{sel_manager or "—"}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
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

    _freshness = load_data_freshness()

    def _fmt_freshness(tables: list) -> str:
        dates = [_freshness[t] for t in tables if t in _freshness]
        if not dates:
            return "—"
        return min(dates).astimezone(PARIS_TZ).strftime("%d/%m %H:%M")

    _freshness_groups = [
        ("Prix joueurs",  ["card_prices"]),
        ("Infos joueurs", ["players", "player_injuries"]),
        ("Galerie",       ["gallery_players"]),
        ("Matchs",        ["games", "pitcher_game_pitches", "pitcher_season_stats"]),
        ("Météo",         ["game_weather"]),
        ("Scores",        ["game_scores", "game_score_details"]),
    ]
    _rows_html = "".join(
        f'<tr>'
        f'<td style="color:var(--fg-2);padding:1px 6px 1px 0;white-space:nowrap">{label}</td>'
        f'<td style="color:var(--fg-0);text-align:right;font-variant-numeric:tabular-nums">'
        f'{_fmt_freshness(tables)}</td>'
        f'</tr>'
        for label, tables in _freshness_groups
    )
    st.markdown(
        f'<div style="font-size:10px;margin-bottom:6px">'
        f'<div style="font-size:9px;font-weight:700;letter-spacing:0.12em;color:var(--fg-3);'
        f'text-transform:uppercase;margin-bottom:4px">Données</div>'
        f'<table style="width:100%;border-collapse:collapse;font-family:var(--mono)">'
        f'{_rows_html}</table></div>',
        unsafe_allow_html=True,
    )

    if st.button("⟳ Rafraîchir", use_container_width=True, key="sidebar_rerun"):
        st.cache_data.clear()
        st.rerun()

# ── Jours disponibles ──────────────────────────────────────────────────────────
_days_cal = set(
    df_calendar[
        (df_calendar["gallery_manager"] == sel_manager) &
        (df_calendar["next_game_date"].dt.date >= today_paris)
    ]["next_game_date"].dt.date.unique()
)
_games_all = pd.read_parquet(_DATA_DIR / "games.parquet")
_games_all["game_date"] = pd.to_datetime(_games_all["game_date"], utc=True, errors="coerce")
_days_games  = set(_games_all[_games_all["game_date"].dt.date >= today_paris]["game_date"].dt.date.unique())
_avail_days  = sorted(_days_cal | _days_games)
_day_labels  = ["Tous les jours"] + [d.strftime("%a %d %b") for d in _avail_days]
_today_label = today_paris.strftime("%a %d %b")
_default_idx = _day_labels.index(_today_label) if _today_label in _day_labels else 0

# ── Ticker ─────────────────────────────────────────────────────────────────────
_sess_day = st.session_state.get("sel_day")
if _sess_day and _sess_day != "Tous les jours" and _sess_day in _day_labels:
    _ticker_day = _avail_days[_day_labels.index(_sess_day) - 1]
else:
    _ticker_day = today_paris
render_ticker(df_all, sel_manager, _ticker_day)

# ── Filtres principaux ─────────────────────────────────────────────────────────
_prev_cat = st.session_state.get("filter_cat", "HITTING") or "HITTING"
_prev_fen = st.session_state.get("filter_fen", "10 matchs") or "10 matchs"

with st.container(border=True):
    st.markdown(
        f'<div class="filt-head">'
        f'<span style="color:var(--fg-3);font-size:10px">∧</span>'
        f'<span class="t">⚙ FILTRES</span>'
        f'<span class="r">{_prev_fen.split()[0]} MATCHS · {_prev_cat}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    cat_c, s1, stat_c, s2, fen_c, s3, day_c, s4, obj_c = st.columns(
        [1.5, 0.08, 3.0, 0.08, 1.3, 0.08, 1.8, 0.08, 1.9]
    )
    for _sp in (s1, s2, s3, s4):
        _sp.markdown('<div class="vsep"></div>', unsafe_allow_html=True)

    _cat = cat_c.pills(
        "Catégorie", ["HITTING", "PITCHING"],
        format_func=lambda x: ("● " if x == "HITTING" else "⚡ ") + x,
        default="HITTING", key="filter_cat",
    )
    categorie = _cat or "HITTING"

    stats_dispo = (
        df_all[df_all["category"] == categorie][["stat_short_name", "stat"]]
        .drop_duplicates().sort_values("stat_short_name")
    )
    stat_labels_list  = stats_dispo["stat_short_name"].tolist()
    stat_keys_list    = stats_dispo["stat"].tolist()
    stat_display_list = [_STAT_DISPLAY.get(s, s) for s in stat_labels_list]
    _sel_display     = stat_c.selectbox("Statistique", stat_display_list, key="filter_stat")
    _sel_idx         = stat_display_list.index(_sel_display)
    sel_stat_label   = stat_labels_list[_sel_idx]
    sel_stat         = stat_keys_list[_sel_idx]
    sel_stat_display = _sel_display

    fenetre = fen_c.pills(
        "Fenêtre", list(FENETRE_OPTIONS.keys()),
        format_func=lambda x: x.split()[0],
        default="10 matchs", key="filter_fen",
    ) or "10 matchs"

    _sel_day_label = day_c.selectbox(
        "Jour de match", _day_labels, index=_default_idx, key="sel_day"
    )

    with obj_c:
        _oi, _or, _oh = st.columns([3, 1, 1])
        target = int(_oi.number_input(
            "Objectif / match", min_value=0, value=0, step=1, format="%d",
            key="filter_target",
        ))
        _or.markdown('<div style="padding-top:28px"></div>', unsafe_allow_html=True)
        if _or.button("↺", key="target_reset", help="Réinitialiser à 0"):
            st.session_state["filter_target"] = 0
            st.rerun()
        _oh.markdown('<div style="padding-top:28px"></div>', unsafe_allow_html=True)
        _oh.button("ⓘ", key="target_info",
                   help="Seuil visuel dans le graphique historique", disabled=True)

if _sel_day_label != "Tous les jours" and _sel_day_label in _day_labels:
    sel_day = _avail_days[_day_labels.index(_sel_day_label) - 1]
else:
    sel_day = None

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
    _tlogos = load_team_logos()
    _tgi: dict = {}
    for _, _g in _games_day.iterrows():
        _t  = _g["game_date"].astimezone(PARIS_TZ).strftime("%H:%M")
        _ht = _g.get("home_team_slug") or ""
        _at = _g.get("away_team_slug") or ""
        _hp = _g.get("home_probable_pitcher") or ""
        _ap = _g.get("away_probable_pitcher") or ""
        if _ht:
            _tgi[_ht] = {"heure": _t, "home_away": "home", "opp": _team_abbr(_at, _tcodes),
                          "opp_slug": _at, "own_slug": _ht, "home_slug": _ht, "away_slug": _at,
                          "opp_pitcher_slug": _ap}
        if _at:
            _tgi[_at] = {"heure": _t, "home_away": "away", "opp": _team_abbr(_ht, _tcodes),
                          "opp_slug": _ht, "own_slug": _at, "home_slug": _ht, "away_slug": _at,
                          "opp_pitcher_slug": _hp}
    _slugs_today = {s for s, c in _slug_club.items() if c in _teams_day}
else:
    _cal_today   = df_calendar[
        (df_calendar["gallery_manager"] == sel_manager) &
        (df_calendar["next_game_date"].dt.date == _day_filter)
    ]
    _slugs_today = set(_cal_today["player_slug"])
    _teams_day   = set()
    _tgi         = {}
    _tlogos      = load_team_logos()

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
    def _gi(row):
        return _tgi.get(_slug_club.get(row["player_slug"], ""))
    df_today["matchup"]          = df_today.apply(lambda r: _matchup_live(r), axis=1)
    df_today["coup_envoi"]       = df_today.apply(lambda r: _coup_envoi_live(r), axis=1)
    df_today["home_slug"]        = df_today.apply(lambda r: (_gi(r) or {}).get("home_slug", ""), axis=1)
    df_today["away_slug"]        = df_today.apply(lambda r: (_gi(r) or {}).get("away_slug", ""), axis=1)
    df_today["opp_pitcher_slug"] = df_today.apply(lambda r: (_gi(r) or {}).get("opp_pitcher_slug", ""), axis=1)
else:
    df_today["home_slug"]        = ""
    df_today["away_slug"]        = ""
    df_today["opp_pitcher_slug"] = ""

_is_map = (
    df_calendar[df_calendar["gallery_manager"] == sel_manager]
    .groupby("player_slug")["in_season_eligible"]
    .any()
)
df_today["in_season_eligible"] = df_today["player_slug"].map(_is_map)

_pp_slugs = set(_load_pp_today(str(today_paris)))

try:
    _df_pp_gw, _ = load_upcoming_pitchers()
    if not _df_pp_gw.empty:
        _pp_ws = pd.Timestamp(str(_day_filter) + " 16:00").tz_localize(PARIS_TZ)
        _pp_we = (pd.Timestamp(str(_day_filter) + " 08:00") + pd.Timedelta(days=1)).tz_localize(PARIS_TZ)
        _df_pp_today = _df_pp_gw[
            (_df_pp_gw["game_date"] >= _pp_ws) & (_df_pp_gw["game_date"] < _pp_we)
        ]
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
    "df_all":           df_all,
    "df_today":         df_today,
    "df_prices":        df_prices,
    "df_calendar":      df_calendar,
    "df_ml":            df_ml,
    "df_lb":            df_lb,
    "df_market":        df_market,
    "sel_manager":      sel_manager,
    "sel_stat":         sel_stat,
    "sel_stat_label":   sel_stat_label,
    "sel_stat_display": sel_stat_display,
    "fenetre":          fenetre,
    "categorie":        categorie,
    "target":           target,
    "sel_day":          sel_day,
    "now_paris":        now_paris,
    "df":               df,
    "_injured_slugs":   _injured_slugs,
    "_slug_name_map":   _slug_name_map,
    "_tlogos":          _tlogos,
    "_teams_day":       tuple(sorted(_teams_day)),
    "_tgi":             _tgi,
}

with tab1:  tab1_defis.render(ctx)
with tab2:  tab2_cartes.render(ctx)
with tab3:  tab3_database.render(ctx)
with tab4:  tab4_visavis.render(ctx)
with tab5:  tab5_projections.render(ctx)
with tab6:  tab6_equipe.render(ctx)
with tab7:  tab7_competitions.render(ctx)
with tab8:  tab8_lineups.render(ctx)
with tab9:  tab9_marche.render(ctx)
with tab10: tab10_docs.render(ctx)
with tab11: tab11_lancers.render(ctx)

_last_upd        = now_paris.strftime("%d %b %Y — %H:%M")
_filters_summary = f"{categorie} · {sel_stat_display} · {fenetre}"
render_statusbar(_last_upd, _filters_summary)
