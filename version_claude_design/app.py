import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(layout="wide", page_title="Sorare MLB", page_icon="⚾")

# ── CSS — Terminal Design System ─────────────────────────────────────────────

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
  margin: 0 !important; color: var(--fg-2) !important;
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
.pcard.rank-1 { border-left: 2px solid var(--r-unique); }
.pcard.rank-2 { border-left: 2px solid var(--accent); }
.pcard.rank-3 { border-left: 2px solid var(--info); }
.pcard__hd { display: flex; align-items: center; gap: 8px; padding: 9px 11px; border-bottom: 1px solid var(--line); }
.pcard__rank { font-size: 16px; font-weight: 700; color: var(--fg-0); min-width: 24px; }
.pcard__rank.r1 { color: var(--r-unique); } .pcard__rank.r2 { color: var(--accent); } .pcard__rank.r3 { color: var(--info); }
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
.empty-state { padding: 40px 20px; text-align: center; color: var(--fg-2); font-size: 11px; }
.spark-line { stroke: var(--accent); stroke-width: 1.2; fill: none; }
.spark-fill { fill: var(--accent); opacity: 0.1; }
</style>
""", unsafe_allow_html=True)

# ── Constantes ─────────────────────────────────────────────────────────────────

POSITION_EXACT = {
    "baseball_starting_pitcher":  "SP",
    "baseball_relief_pitcher":    "RP",
    "baseball_outfield":          "OF",
    "baseball_first_base":        "1B",
    "baseball_second_base":       "2B",
    "baseball_third_base":        "3B",
    "baseball_shortstop":         "SS",
    "baseball_catcher":           "C",
    "baseball_designated_hitter": "DH",
}
POSITION_AGG = {
    "baseball_starting_pitcher":  "SP",
    "baseball_relief_pitcher":    "RP",
    "baseball_outfield":          "OF",
    "baseball_first_base":        "CI",
    "baseball_second_base":       "MI",
    "baseball_third_base":        "CI",
    "baseball_shortstop":         "MI",
    "baseball_catcher":           "MI",
    "baseball_designated_hitter": "CI",
}
RARITY_ORDER = {"unique": 0, "super_rare": 1, "rare": 2, "limited": 3}
RARITY_COLOR = {
    "unique":     "#ac11ff",
    "super_rare": "#179eff",
    "rare":       "#de000b",
    "limited":    "#f7b100",
}
FENETRE_OPTIONS = {"5 matchs": 5, "10 matchs": 10, "20 matchs": 20}
PARIS_TZ = ZoneInfo("Europe/Paris")

MOIS_FR = ["", "jan", "fév", "mar", "avr", "mai", "jun",
           "jul", "aoû", "sep", "oct", "nov", "déc"]


# ── Data ───────────────────────────────────────────────────────────────────────

_DATA_DIR      = Path(__file__).parent.parent / "data"
_LINEUPS_FILE  = _DATA_DIR / "saved_lineups.json"


def _api_key() -> str:
    """Retourne l'API key Sorare — st.secrets en cloud, .env en local."""
    try:
        return st.secrets["API_KEY"]
    except Exception:
        env_path = Path(__file__).parent / ".." / ".env"
        load_dotenv(dotenv_path=env_path)
        return os.getenv("API_KEY", "")


@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    df = pd.read_parquet(_DATA_DIR / "gallery_stats.parquet")
    df["position_exact"] = df["card_display_position"].map(POSITION_EXACT)
    df["position_agg"]   = df["card_display_position"].map(POSITION_AGG)
    df["next_game_date"] = pd.to_datetime(df["next_game_date"], utc=True, errors="coerce")
    df["moyenne"]        = pd.to_numeric(df["moyenne"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_calendar() -> pd.DataFrame:
    df = pd.read_parquet(_DATA_DIR / "calendar.parquet")
    df["next_game_date"] = pd.to_datetime(df["next_game_date"], utc=True, errors="coerce")
    df["position_exact"] = df["card_display_position"].map(POSITION_EXACT)
    df["position_agg"]   = df["card_display_position"].map(POSITION_AGG)
    df["pct_played"]     = pd.to_numeric(df["pct_played"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_card_prices() -> pd.DataFrame:
    df = pd.read_parquet(_DATA_DIR / "card_prices.parquet")
    df["position_exact"]   = df["card_display_position"].map(POSITION_EXACT)
    df["position_agg"]     = df["card_display_position"].map(POSITION_AGG)
    df["price_in_season"]  = pd.to_numeric(df["price_in_season"],  errors="coerce")
    df["price_out_season"] = pd.to_numeric(df["price_out_season"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_leaderboard_rewards() -> pd.DataFrame:
    p = _DATA_DIR / "leaderboard_rewards.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    for col in ("score_threshold", "reward_quantity", "reward_usd_cents"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "gw_int" in df.columns:
        df["gw_int"] = pd.to_numeric(df["gw_int"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_ml_predictions() -> pd.DataFrame:
    p = _DATA_DIR / "ml_predictions.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["pred_median"] = pd.to_numeric(df["pred_median"], errors="coerce")
    df["pred_lo"]     = pd.to_numeric(df["pred_lo"],     errors="coerce")
    df["pred_hi"]     = pd.to_numeric(df["pred_hi"],     errors="coerce")
    if "n_games_gw" not in df.columns:
        df["n_games_gw"] = None
    else:
        df["n_games_gw"] = pd.to_numeric(df["n_games_gw"], errors="coerce")
    for _col in ("pred_A", "pred_B", "pred_C",
                 "platoon_factor_A", "platoon_factor_B", "platoon_factor_C"):
        if _col not in df.columns:
            df[_col] = None
        else:
            df[_col] = pd.to_numeric(df[_col], errors="coerce")
    for _col in ("pred_contextual", "park_factor", "weather_factor",
                 "opp_quality_factor", "day_night_factor", "rest_factor", "home_away_factor"):
        if _col not in df.columns:
            df[_col] = None
        else:
            df[_col] = pd.to_numeric(df[_col], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_all_players_market() -> pd.DataFrame:
    p = _DATA_DIR / "all_players_market.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    for col in ["price_limited_is", "price_limited_oos", "price_rare_is", "price_rare_oos",
                "price_sr_is", "price_sr_oos", "price_unique_is", "price_unique_oos"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


_SORARE_API = "https://api.sorare.com/graphql"


@st.cache_data(ttl=3600)
def load_upcoming_pitchers() -> tuple[pd.DataFrame, int]:
    """Retourne (df_games, gw_int) pour le prochain fixture CLASSIC composable."""
    headers = {
        "Content-Type": "application/json",
        "APIKEY": _api_key(),
    }

    r1 = requests.post(_SORARE_API, json={"query": """{
      so5 {
        featuredSo5Fixtures(sport: BASEBALL, first: 20, eventType: CLASSIC) {
          slug gameWeek canCompose
        }
      }
    }"""}, headers=headers, timeout=30)
    r1.raise_for_status()
    fixtures = r1.json()["data"]["so5"]["featuredSo5Fixtures"]
    composable = [f for f in fixtures if f["canCompose"]]
    if not composable:
        return pd.DataFrame(), 0

    target = composable[0]
    gw_int = target["gameWeek"]

    r2 = requests.post(_SORARE_API, json={"query": """{
      so5 {
        so5Fixture(sport: BASEBALL, slug: "%s", eventType: CLASSIC) {
          anyGames {
            ... on GameOfBaseball {
              id date statusTyped
              homeTeam { slug name }
              awayTeam { slug name }
              homeProbablePitcher { slug displayName }
              awayProbablePitcher  { slug displayName }
            }
          }
        }
      }
    }""" % target["slug"]}, headers=headers, timeout=30)
    r2.raise_for_status()
    games = r2.json()["data"]["so5"]["so5Fixture"]["anyGames"]

    rows = []
    for g in games:
        if not g:
            continue
        hp = g.get("homeProbablePitcher") or {}
        ap = g.get("awayProbablePitcher")  or {}
        rows.append({
            "game_date":          g.get("date"),
            "status":             g.get("statusTyped"),
            "home_team_slug":     (g.get("homeTeam") or {}).get("slug"),
            "home_team_name":     (g.get("homeTeam") or {}).get("name"),
            "away_team_slug":     (g.get("awayTeam") or {}).get("slug"),
            "away_team_name":     (g.get("awayTeam") or {}).get("name"),
            "home_pitcher_slug":  hp.get("slug"),
            "home_pitcher_name":  hp.get("displayName"),
            "away_pitcher_slug":  ap.get("slug"),
            "away_pitcher_name":  ap.get("displayName"),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df, gw_int
    df["game_date"] = pd.to_datetime(df["game_date"], utc=True, errors="coerce")
    df = df.sort_values("game_date").reset_index(drop=True)
    return df, gw_int


@st.cache_data(ttl=3600)
def load_pitcher_stats(slugs: tuple, fenetre: int) -> pd.DataFrame:
    if not slugs:
        return pd.DataFrame()
    gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    gs  = gs[gs["player_slug"].isin(slugs) & gs["played_in_game"]].copy()
    gs["game_date"] = pd.to_datetime(gs["game_date"], utc=True, errors="coerce")
    gs["rk"] = gs.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gs = gs[gs["rk"] <= fenetre][["player_slug", "game_date"]]
    gsd = gsd[gsd["category"] == "PITCHING"].copy()
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")
    merged = gs.merge(gsd, on=["player_slug", "game_date"])
    if merged.empty:
        return pd.DataFrame(columns=["player_slug", "stat", "stat_short_name", "avg_val", "nb_matchs"])
    agg = (merged.groupby(["player_slug", "stat", "stat_short_name"])
           .agg(avg_val=("stat_value", "mean"), nb_matchs=("game_date", "nunique"))
           .reset_index())
    agg["avg_val"] = agg["avg_val"].round(2)
    return agg


@st.cache_data(ttl=3600)
def load_injured_players() -> tuple:
    df = pd.read_parquet(_DATA_DIR / "injuries.parquet")
    return tuple(df["player_slug"].tolist())


def load_saved_lineups() -> list:
    if not _LINEUPS_FILE.exists():
        return []
    with open(_LINEUPS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _persist_lineup(entry: dict) -> None:
    lineups = load_saved_lineups()
    lineups.append(entry)
    with open(_LINEUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(lineups, f, ensure_ascii=False, indent=2)


def _delete_lineup(lineup_id: str) -> None:
    lineups = [l for l in load_saved_lineups() if l.get("lineup_id") != lineup_id]
    with open(_LINEUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(lineups, f, ensure_ascii=False, indent=2)


@st.cache_data(ttl=3600)
def load_game_scores_all() -> pd.DataFrame:
    p = _DATA_DIR / "game_scores.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["gw_int"] = pd.to_numeric(df["gw_int"], errors="coerce")
    df["score"]  = pd.to_numeric(df["score"],   errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_pitcher_stats_vv(pitcher_slugs: tuple, pit_hit_pairs: tuple) -> tuple:
    if not pitcher_slugs:
        return pd.DataFrame(), pd.DataFrame()
    _cols = ["player_slug", "stat_short_name", "avg_val", "nb_matchs", "avg_sorare_score"]
    gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    gs["game_date"]  = pd.to_datetime(gs["game_date"],  utc=True, errors="coerce")
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")

    # Last 5 outings
    gs_p = gs[gs["player_slug"].isin(pitcher_slugs) & gs["played_in_game"]].copy()
    gs_p["rk"] = gs_p.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gs5 = gs_p[gs_p["rk"] <= 5][["player_slug", "game_date", "score"]]
    gsd_p = gsd[gsd["player_slug"].isin(pitcher_slugs) & (gsd["category"] == "PITCHING")]
    m5 = gs5.merge(gsd_p, on=["player_slug", "game_date"])
    if m5.empty:
        df_last5 = pd.DataFrame(columns=_cols)
    else:
        df_last5 = (m5.groupby(["player_slug", "stat_short_name"])
                    .agg(avg_val=("stat_value", "mean"), nb_matchs=("game_date", "nunique"), avg_sorare_score=("score", "mean"))
                    .reset_index())
        df_last5[["avg_val", "avg_sorare_score"]] = df_last5[["avg_val", "avg_sorare_score"]].round(2)

    # Vs active hitters (works if hitters are gallery players too)
    if pit_hit_pairs:
        pairs = pd.DataFrame(pit_hit_pairs, columns=["pitcher_slug", "hitter_slug"])
        hit_slugs = set(pairs["hitter_slug"])
        gs_h = gs[gs["player_slug"].isin(hit_slugs) & gs["played_in_game"]][["player_slug", "game_date"]].rename(columns={"player_slug": "hitter_slug"})
        gs_pit = gs_p[["player_slug", "game_date", "score"]].rename(columns={"player_slug": "pitcher_slug"})
        valid = gs_pit.merge(pairs, on="pitcher_slug").merge(gs_h, on=["hitter_slug", "game_date"])
        valid = valid[["pitcher_slug", "game_date", "score"]].drop_duplicates().rename(columns={"pitcher_slug": "player_slug"})
        mvs = valid.merge(gsd_p[["player_slug", "game_date", "stat_short_name", "stat_value"]], on=["player_slug", "game_date"])
        if mvs.empty:
            df_vs = pd.DataFrame(columns=_cols)
        else:
            df_vs = (mvs.groupby(["player_slug", "stat_short_name"])
                     .agg(avg_val=("stat_value", "mean"), nb_matchs=("game_date", "nunique"), avg_sorare_score=("score", "mean"))
                     .reset_index())
            df_vs[["avg_val", "avg_sorare_score"]] = df_vs[["avg_val", "avg_sorare_score"]].round(2)
    else:
        df_vs = pd.DataFrame(columns=_cols)

    return df_last5, df_vs


@st.cache_data(ttl=3600)
def load_all_hitters_for_gw(team_slugs: tuple) -> pd.DataFrame:
    if not team_slugs:
        return pd.DataFrame(columns=["player_slug", "player_name", "team_slug", "position_exact", "agg_position"])
    pl = pd.read_parquet(_DATA_DIR / "players.parquet")
    df = pl[pl["team_slug"].isin(team_slugs) & ~pl["agg_position_1"].isin(["SP", "RP"])].copy()
    return df.rename(columns={"display_name": "player_name", "position_1": "position_exact", "agg_position_1": "agg_position"})[
        ["player_slug", "player_name", "team_slug", "position_exact", "agg_position"]
    ]


@st.cache_data(ttl=3600)
def load_matchup_stats(hitter_slugs: tuple, pitcher_slugs: tuple) -> pd.DataFrame:
    if not hitter_slugs or not pitcher_slugs:
        return pd.DataFrame()
    gs    = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd   = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    games = pd.read_parquet(_DATA_DIR / "games.parquet")
    pl    = pd.read_parquet(_DATA_DIR / "players.parquet")
    gs["game_date"]    = pd.to_datetime(gs["game_date"],    utc=True, errors="coerce")
    gsd["game_date"]   = pd.to_datetime(gsd["game_date"],   utc=True, errors="coerce")
    games["game_date"] = pd.to_datetime(games["game_date"], utc=True, errors="coerce")
    teams = pl[pl["player_slug"].isin(hitter_slugs)][["player_slug", "team_slug"]].rename(columns={"team_slug": "active_club_slug"})
    gs_h = gs[gs["player_slug"].isin(hitter_slugs) & gs["played_in_game"]][["player_slug", "game_date", "score"]].merge(teams, on="player_slug")
    m = gs_h.merge(games[["game_date", "home_team_slug", "away_team_slug", "home_probable_pitcher", "away_probable_pitcher"]], on="game_date")
    m["pitcher_slug"] = m.apply(
        lambda r: r["home_probable_pitcher"] if r["away_team_slug"] == r["active_club_slug"]
                  else (r["away_probable_pitcher"] if r["home_team_slug"] == r["active_club_slug"] else None), axis=1)
    m = m[m["pitcher_slug"].isin(pitcher_slugs)]
    gsd_h = gsd[gsd["player_slug"].isin(hitter_slugs) & (gsd["category"] == "HITTING")]
    final = m[["player_slug", "game_date", "score", "pitcher_slug"]].merge(gsd_h[["player_slug", "game_date", "stat_short_name", "stat_value"]], on=["player_slug", "game_date"])
    if final.empty:
        return pd.DataFrame(columns=["hitter_slug", "pitcher_slug", "stat_short_name", "avg_val", "nb_matchs", "avg_sorare_score"])
    result = (final.groupby(["player_slug", "pitcher_slug", "stat_short_name"])
              .agg(avg_val=("stat_value", "mean"), nb_matchs=("game_date", "nunique"), avg_sorare_score=("score", "mean"))
              .reset_index().rename(columns={"player_slug": "hitter_slug"}))
    result[["avg_val", "avg_sorare_score"]] = result[["avg_val", "avg_sorare_score"]].round(2)
    return result


@st.cache_data(ttl=3600)
def load_player_avg_scores(slugs: tuple, fenetre: int = 10) -> pd.DataFrame:
    if not slugs:
        return pd.DataFrame(columns=["player_slug", "avg_score", "nb_matchs"])
    gs = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gs = gs[gs["player_slug"].isin(slugs) & gs["played_in_game"]].copy()
    gs["game_date"] = pd.to_datetime(gs["game_date"], utc=True, errors="coerce")
    gs["rk"] = gs.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gs = gs[gs["rk"] <= fenetre]
    result = (gs.groupby("player_slug")
              .agg(avg_score=("score", "mean"), nb_matchs=("game_date", "nunique"))
              .reset_index())
    result["avg_score"] = result["avg_score"].round(1)
    return result


@st.cache_data(ttl=3600)
def load_player_history(player_slug: str, stat: str) -> pd.DataFrame:
    gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    gs_p = gs[gs["player_slug"] == player_slug][["game_date", "gw_int", "played_in_game"]].copy()
    gsd_p = gsd[(gsd["player_slug"] == player_slug) & (gsd["stat"] == stat)][["game_date", "stat_value"]]
    df = gs_p.merge(gsd_p, on="game_date", how="left")
    df["stat_value"] = df["stat_value"].fillna(0)
    df["game_date"] = pd.to_datetime(df["game_date"], utc=True, errors="coerce")
    df = df.sort_values("game_date", ascending=False).head(20)
    return df.iloc[::-1].reset_index(drop=True)


@st.cache_data(ttl=3600)
def load_db_stats(stat: str, fenetre: int) -> pd.DataFrame:
    gs  = pd.read_parquet(_DATA_DIR / "game_scores.parquet")
    gsd = pd.read_parquet(_DATA_DIR / "game_score_details.parquet")
    pl  = pd.read_parquet(_DATA_DIR / "players.parquet")
    gs["game_date"]  = pd.to_datetime(gs["game_date"],  utc=True, errors="coerce")
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")
    gs_played = gs[gs["played_in_game"]].copy()
    gs_played["rk"] = gs_played.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gs_f = gs_played[gs_played["rk"] <= fenetre][["player_slug", "game_date"]]
    gsd_f = gsd[gsd["stat"] == stat][["player_slug", "game_date", "stat_value"]]
    merged = gs_f.merge(gsd_f, on=["player_slug", "game_date"])
    if merged.empty:
        return pd.DataFrame(columns=["player_slug", "display_name", "position_exact", "agg_position", "team_slug", "moyenne", "nb_matchs"])
    agg = (merged.groupby("player_slug")
           .agg(moyenne=("stat_value", "mean"), nb_matchs=("game_date", "nunique"))
           .reset_index())
    agg = agg.merge(pl[["player_slug", "display_name", "team_slug", "position_1", "agg_position_1"]], on="player_slug", how="left")
    agg["display_name"]    = agg["display_name"].fillna(agg["player_slug"])
    agg["position_exact"]  = agg["position_1"].map(lambda x: POSITION_EXACT.get(x, x) if x else x)
    agg["agg_position"]    = agg["agg_position_1"].map(lambda x: POSITION_AGG.get(x, x) if x else x)
    agg["moyenne"]         = agg["moyenne"].round(3)
    return agg[["player_slug", "display_name", "position_exact", "agg_position", "team_slug", "moyenne", "nb_matchs"]].sort_values("moyenne", ascending=False)


# ── Composants sidebar ─────────────────────────────────────────────────────────

def compact_multiselect(label: str, options: list, key: str) -> list:
    opts_key = f"{key}__opts"
    prev_options = st.session_state.get(opts_key)
    st.session_state[opts_key] = options

    if key not in st.session_state:
        st.session_state[key] = list(options)
    elif prev_options != options:
        valid = [o for o in options if o in st.session_state[key]]
        st.session_state[key] = valid if valid else list(options)

    current = st.session_state[key]
    n, nc = len(options), len(current)
    if nc == 0:
        summary = "Aucune"
    elif nc >= 2 and nc < n:
        summary = f"Valeurs multiples ({nc})"
    elif nc == n:
        summary = "Toutes" if n > 1 else (current[0] if current else "—")
    else:
        summary = current[0] if current else "—"

    with st.expander(f"{label} · {summary}"):
        if st.button("Sélectionner tout", key=f"{key}__all"):
            st.session_state[key] = list(options)
            st.rerun()
        selected = st.multiselect(label, options, key=key, label_visibility="collapsed")
    return selected


# ── Composants UI ──────────────────────────────────────────────────────────────

def gen_bar_sparkline_svg(values, w=88, h=20, target=0.0) -> str:
    if not values:
        return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}"></svg>'
    n = len(values)
    effective_max = max(max(values), target) if target > 0 else max(values)
    mx = effective_max if effective_max > 0 else 1
    bar_w = max(3, (w - n + 1) // n)
    bars = ""
    for i, v in enumerate(values):
        bh = max(2, round((max(0, v) / mx) * (h - 2)))
        x  = i * (bar_w + 1)
        y  = h - bh
        alpha = round(0.35 + 0.65 * (i / max(1, n - 1)), 2)
        bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="var(--accent)" opacity="{alpha}" rx="1"/>'
    target_line = ""
    if target > 0:
        ty = max(1, min(h - 1, round(h - (target / mx) * (h - 2))))
        target_line = (
            f'<line x1="0" y1="{ty}" x2="{w}" y2="{ty}"'
            f' stroke="#fbbf24" stroke-width="1" stroke-dasharray="3,2" opacity="0.55"/>'
        )
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">{bars}{target_line}</svg>'


def gen_sparkline_svg(values, w=160, h=24, color="var(--accent)") -> str:
    if not values:
        return ""
    mn, mx = min(values), max(values)
    span = max(0.001, mx - mn)
    pts = [(i / max(1, len(values) - 1) * w, h - ((v - mn) / span) * (h - 2) - 1) for i, v in enumerate(values)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    fill = f"{path} L{pts[-1][0]:.1f},{h} L{pts[0][0]:.1f},{h} Z"
    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" preserveAspectRatio="none">'
        f'<path d="{fill}" fill="{color}" opacity="0.1"/>'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.2"/>'
        f"</svg>"
    )


@st.cache_data(ttl=3600)
def load_today_games(today_date: str) -> pd.DataFrame:
    games = pd.read_parquet(_DATA_DIR / "games.parquet")
    games["game_date"] = pd.to_datetime(games["game_date"], utc=True, errors="coerce")
    today = pd.Timestamp(today_date).date()
    g = games[games["game_date"].dt.date == today].copy()
    g = g.sort_values("game_date").reset_index(drop=True)
    return g


@st.cache_data(ttl=3600)
def load_stat_sparklines(player_slugs: tuple, stat_short: str, n_games: int = 10) -> dict:
    p = _DATA_DIR / "game_score_details.parquet"
    if not p.exists() or not player_slugs:
        return {}
    gsd = pd.read_parquet(p, columns=["player_slug", "game_date", "stat_short_name", "stat_value"])
    gsd = gsd[gsd["player_slug"].isin(player_slugs) & (gsd["stat_short_name"] == stat_short)]
    if gsd.empty:
        return {}
    gsd["game_date"] = pd.to_datetime(gsd["game_date"], utc=True, errors="coerce")
    gsd["rk"] = gsd.groupby("player_slug")["game_date"].rank(ascending=False, method="first").astype(int)
    gsd = gsd[gsd["rk"] <= n_games].sort_values(["player_slug", "game_date"])
    return {
        slug: [max(0.0, float(v)) for v in grp["stat_value"].fillna(0).tolist()]
        for slug, grp in gsd.groupby("player_slug")
    }


@st.cache_data(ttl=86400)
def load_team_codes() -> dict:
    p = _DATA_DIR / "teams.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p, columns=["team_slug", "team_code"])
    return dict(zip(df["team_slug"], df["team_code"].fillna("")))


def _team_abbr(slug: str, codes: dict) -> str:
    code = codes.get(slug, "")
    if code:
        return code
    words = (slug or "").replace("-", " ").split()
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(w[0] for w in words[:3]).upper()


def render_ticker(df_all, sel_manager, today_paris) -> None:
    df_games = load_today_games(str(today_paris))
    team_codes = load_team_codes()
    if df_games.empty:
        game_items = '<span class="ticker__item"><span class="sym">MLB</span><span class="val info">Aucun match aujourd\'hui</span></span>'
    else:
        parts = []
        for _, g in df_games.iterrows():
            home = _team_abbr(g.get("home_team_slug", ""), team_codes)
            away = _team_abbr(g.get("away_team_slug", ""), team_codes)
            t = g["game_date"].astimezone(PARIS_TZ).strftime("%H:%M")
            parts.append(
                f'<span class="ticker__item">'
                f'<span class="sym">{home}</span>'
                f'<span style="color:var(--fg-3);font-size:10px">vs</span>'
                f'<span class="sym">{away}</span>'
                f'<span class="val info">{t}</span>'
                f'</span>'
            )
        sep = '<span class="ticker__sep">&#9670;</span>'
        if len(parts) >= 2:
            times = df_games["game_date"].tolist()
            n = len(times)
            gaps = [
                (times[i + 1] - times[i]).total_seconds() if i + 1 < n
                else (times[0] + pd.Timedelta(days=1) - times[i]).total_seconds()
                for i in range(n)
            ]
            start = (gaps.index(max(gaps)) + 1) % n
            parts = parts[start:] + parts[:start]
            game_items = "".join(parts) + sep
        else:
            game_items = "".join(parts)

    st.markdown(
        f'<div class="ticker">'
        f'<div class="ticker__brand"><span class="ticker__brand-dot"></span>SORARE·MLB</div>'
        f'<div class="ticker__feed"><div class="ticker__feed-inner">{game_items}{game_items}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_statusbar(last_upd: str, filters_summary: str) -> None:
    st.markdown(
        f'<div class="statusbar">'
        f'<span class="statusbar__cell"><span class="dot live"></span><span class="k">CONN</span><span class="v">api.sorare.com</span></span>'
        f'<span class="statusbar__cell"><span class="k">CACHE</span><span class="v">ttl 3600s</span></span>'
        f'<span class="statusbar__cell"><span class="k">FILTERS</span><span class="v">{filters_summary}</span></span>'
        f'<span class="statusbar__spacer"></span>'
        f'<span class="statusbar__cell"><span class="k">LAST.UPD</span><span class="v">{last_upd}</span></span>'
        f'<span class="statusbar__cell"><span class="k">v</span><span class="v">2.4.0-mlb</span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _matchup(row) -> str:
    if pd.isna(row["next_game_date"]):
        return "—"
    if row["home_away"] == "home":
        return f"vs {row['away_team_name'] or '?'}"
    if row["home_away"] == "away":
        return f"@ {row['home_team_name'] or '?'}"
    return row["home_team_name"] or row["away_team_name"] or "—"


def _game_date_str(row) -> str:
    if pd.isna(row["next_game_date"]):
        return "—"
    return row["next_game_date"].strftime("%d/%m %H:%M")


def _fmt_date_header(dt: datetime) -> str:
    now_utc = datetime.now(timezone.utc)
    delta   = (dt.date() - now_utc.date()).days
    label   = dt.strftime(f"%d {MOIS_FR[dt.month]}")
    if delta == 0:
        return f"Aujourd'hui — {label}"
    if delta == 1:
        return f"Demain — {label}"
    return label


def render_terminal_card(rank: int, row, stat_label: str, spark_values: list | None = None, picture_url: str | None = None, target: float = 0.0) -> str:
    rar_raw  = (row["card_display_rarity"] or "").lower()
    rar_css  = {"limited": "r-limited", "rare": "r-rare", "super_rare": "r-superrare", "unique": "r-unique"}.get(rar_raw, "")
    rank_css = ["r1", "r2", "r3"][rank] if rank < 3 else ""
    card_cls = f"pcard rank-{rank + 1}" if rank < 3 else "pcard"
    rank_lbl = ["#1", "#2", "#3"][rank] if rank < 3 else f"#{rank + 1}"
    pos      = row.get("position_agg") or row.get("position_exact") or "?"
    matchup  = row.get("matchup", "—")
    coup     = row.get("coup_envoi", "—")
    rar_lbl  = (row["card_display_rarity"] or "").upper()
    is_elig  = row.get("in_season_eligible")
    is_tag   = '<span class="tag is">IS</span>' if is_elig is True else ('<span class="tag classic">OOS</span>' if is_elig is False else "")
    pp_tag   = '<span class="tag pp">PP</span>' if row.get("is_pp") else ""
    rar_tag  = f'<span class="tag rarity-{rar_raw}">{rar_lbl}</span>' if rar_lbl else ""
    monogram = row["player_name"].split()[-1][:3].upper()
    pred     = row.get("pred_median")
    pred_str = f"{pred:.1f}" if pred and not pd.isna(pred) else "—"

    # Indicateur principal : fois où l'objectif est atteint (si objectif défini)
    if target > 0 and spark_values:
        n_reached = sum(1 for v in spark_values if v >= target)
        n_total   = len(spark_values)
        stat_val_html = (
            f'<div class="v pos">{n_reached}'
            f'<span style="font-size:10px;color:var(--fg-2);font-weight:400">/{n_total}</span></div>'
        )
        stat_key = "Objectif"
    else:
        stat_val_html = f'<div class="v pos">{row["moyenne"]:.2f}</div>'
        stat_key = stat_label

    # Sparkline barres dans l'art block
    art_spark = ""
    if spark_values:
        art_spark = (
            f'<div class="pcard__art-spark-wrap">'
            + gen_bar_sparkline_svg(spark_values, w=96, h=82, target=target)
            + f'</div>'
        )

    img_or_mono = (
        f'<img src="{picture_url}" class="pcard__card-img" alt="{monogram}"/>'
        if picture_url else
        f'<div class="pcard__monogram">{monogram}</div>'
    )

    return (
        f'<div class="{card_cls}">'
        f'<div class="pcard__hd">'
        f'<span class="pcard__rank {rank_css}">{rank_lbl}</span>'
        f'<div class="pcard__head-info">'
        f'<div class="pcard__name">{row["player_name"]}</div>'
        f'<div class="pcard__sub">{pos} · {matchup}</div>'
        f'</div>'
        f'<span class="pcard__rarity-dot" style="background:var(--{rar_css},#888)"></span>'
        f'</div>'
        f'<div class="pcard__art">'
        f'<div class="pcard__art-body">{img_or_mono}{art_spark}</div>'
        f'<span class="pcard__art-tag">{rar_lbl}</span>'
        f'</div>'
        f'<div class="pcard__row">'
        f'<div class="cell"><div class="k">{stat_key}</div>{stat_val_html}</div>'
        f'<div class="cell"><div class="k">ML Pred</div><div class="v">{pred_str}</div></div>'
        f'<div class="cell"><div class="k">Matchs</div><div class="v dim">{int(row["nb_matchs"])}</div></div>'
        f'</div>'
        f'<div class="pcard__meta">{rar_tag}{is_tag}{pp_tag}'
        f'<span style="margin-left:auto;font-size:9px;color:var(--fg-3)">{coup}</span></div>'
        f'</div>'
    )


def render_player_card(rank: int, row, stat_label: str) -> str:
    return render_terminal_card(rank, row, stat_label)


# ── Graphique historique ───────────────────────────────────────────────────────

@st.dialog("📊 Historique joueur", width="large")
def show_player_chart(player_slug: str, player_name: str, stat: str, stat_label: str, target: float):
    st.subheader(f"{player_name} — {stat_label}")

    df_hist = load_player_history(player_slug, stat)
    if df_hist.empty:
        st.warning("Aucun historique disponible pour ce joueur.")
        return

    is_dnp = (~df_hist["played_in_game"]).tolist()
    values = [float(v) for v in df_hist["stat_value"]]
    x_labels = df_hist["game_date"].dt.strftime("%d/%m").tolist()

    played_values = [v for v, d in zip(values, is_dnp) if not d]
    ymax = max(
        (max(played_values) * 1.30 if played_values else 0),
        (target * 1.15 if target > 0 else 0),
    ) or 5
    zero_h    = ymax * 0.12
    min_bar_h = zero_h * 1.25

    bar_colors = []
    for v, dnp in zip(values, is_dnp):
        if dnp:
            bar_colors.append("#4b5563")
        elif target > 0:
            bar_colors.append("#22c55e" if v >= target else "#ef4444")
        else:
            bar_colors.append("#3b82f6")

    display_y = []
    for v, dnp in zip(values, is_dnp):
        if dnp:
            display_y.append(zero_h)
        elif v == 0:
            display_y.append(0)
        else:
            display_y.append(max(v, min_bar_h))

    _N_GRAD = 25
    _ALPHA  = 0.052
    _PLOT_H = 480
    _SKIP   = 30 * ymax / _PLOT_H
    _FONT     = dict(size=16, color="rgba(0,0,0,0.88)",
                     family="Arial Black, Impact, Arial Narrow, sans-serif")
    _FONT_DNP = dict(size=12, color="rgba(255,255,255,0.90)",
                     family="Arial Black, Impact, Arial Narrow, sans-serif")

    fig = go.Figure()
    hover_labels = [
        "DNP" if d else (str(int(v)) if v == int(v) else f"{v:.2f}")
        for v, d in zip(values, is_dnp)
    ]
    fig.add_trace(go.Bar(
        x=x_labels, y=display_y,
        marker=dict(color=bar_colors, cornerradius=8, opacity=0.95,
                    line=dict(color="rgba(255,255,255,0.06)", width=1)),
        hovertemplate="%{x} · <b>%{customdata}</b><extra></extra>",
        customdata=hover_labels,
    ))

    if any(not d and v == 0 for v, d in zip(values, is_dnp)):
        fig.add_trace(go.Bar(
            x=x_labels,
            y=[zero_h if (not d and v == 0) else 0 for v, d in zip(values, is_dnp)],
            marker=dict(color="#ef4444", cornerradius=5, opacity=0.92, line_width=0),
            hoverinfo="skip", showlegend=False,
        ))

    for step in range(_N_GRAD):
        frac = (step + 1) / _N_GRAD
        fig.add_trace(go.Bar(
            x=x_labels,
            y=[max(0.0, h - _SKIP) * frac for h in display_y],
            marker=dict(color=f"rgba(10,13,24,{_ALPHA})", cornerradius=0, line_width=0),
            hoverinfo="skip", showlegend=False,
        ))

    for x, value, display_h, dnp in zip(x_labels, values, display_y, is_dnp):
        label = str(int(value)) if value == int(value) else f"{value:.2f}"
        if dnp:
            fig.add_annotation(x=x, y=display_h / 2, text="<b>DNP</b>",
                showarrow=False, yanchor="middle", xanchor="center", font=_FONT_DNP)
        elif value > 0:
            fig.add_annotation(x=x, y=display_h, text=f"<b>{label}</b>",
                showarrow=False, yanchor="top", xanchor="center", font=_FONT)
        else:
            fig.add_annotation(x=x, y=zero_h / 2, text="<b>0</b>",
                showarrow=False, yanchor="middle", xanchor="center", font=_FONT)

    n_bars = len(x_labels)
    if target > 0:
        st.markdown(
            f'<div style="text-align:right;color:#fbbf24;font-size:0.9rem;margin-bottom:4px">'
            f'Objectif : <strong>{target:g}</strong></div>',
            unsafe_allow_html=True,
        )
        fig.add_hline(y=target, line_dash="dash", line_color="#fbbf24", line_width=2)

    fig.update_layout(
        barmode="overlay",
        paper_bgcolor="#0c1014",
        plot_bgcolor="#0c1014",
        font=dict(family="JetBrains Mono, monospace", color="#aab4c2", size=10),
        xaxis=dict(
            tickfont=dict(size=max(9, 13 - max(0, n_bars - 12)), color="#6b7585", family="JetBrains Mono"),
            tickangle=-45 if n_bars > 12 else 0,
            showgrid=False, zeroline=False, showline=False,
            gridcolor="#1f2935",
        ),
        yaxis=dict(
            tickformat=".2g", gridcolor="#1f2935",
            zeroline=False, showline=False,
            tickfont=dict(size=10, color="#4a5260", family="JetBrains Mono"),
            range=[-ymax * 0.16, ymax],
        ),
        showlegend=False,
        margin=dict(t=12, b=48, l=36, r=12),
        bargap=0.28,
        height=max(380, 560 - max(0, n_bars - 10) * 8),
    )
    st.plotly_chart(fig, use_container_width=True)
    n_played = sum(1 for d in is_dnp if not d)
    st.caption(f"{n_played} matchs joués · {sum(is_dnp)} DNP sur les {len(df_hist)} derniers matchs")


# ── Authentification ───────────────────────────────────────────────────────────

def _check_password() -> bool:
    try:
        pwd = st.secrets["APP_PASSWORD"]
    except Exception:
        return True  # pas de secrets configurés → accès libre en local
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
    # ── Brand header ──────────────────────────────────────────────────────────
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
        "🎯 Objectif", min_value=0.0, value=0.0, step=0.5,
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
    # Jours dispo : union calendar (next_game_date) + games.parquet (plus fiable)
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

# Stat avg par joueur pour le calendrier
stat_avg_map = (
    df_all[(df_all["fenetre"] == fenetre) & (df_all["stat"] == sel_stat)]
    .groupby("player_slug")["moyenne"]
    .first()
    .to_dict()
)

# Tab 1 : jour sélectionné via sidebar, ou aujourd'hui par défaut
_day_filter    = sel_day if sel_day is not None else today_paris
_injured_slugs = set(load_injured_players())

# Filtre "qui joue ce jour" depuis games.parquet (fiable) + active_club_slug du calendar
# La source next_game_date de Sorare peut être en retard d'un jour
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
    # team_slug → {heure Paris, home_away, opp_abbr}
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
    # Fallback : next_game_date du calendar
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

# Override matchup/coup_envoi avec données fraîches depuis games.parquet
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

# Enrichir df_today avec in_season_eligible depuis df_calendar
_is_map = (
    df_calendar[df_calendar["gallery_manager"] == sel_manager]
    .drop_duplicates("player_slug")
    .set_index("player_slug")["in_season_eligible"]
)
df_today["in_season_eligible"] = df_today["player_slug"].map(_is_map)

# PP — probable pitcher pour les matchs d'aujourd'hui
@st.cache_data(ttl=3600)
def _load_pp_today(today_date: str) -> frozenset:
    games = pd.read_parquet(_DATA_DIR / "games.parquet")
    games["game_date"] = pd.to_datetime(games["game_date"], utc=True, errors="coerce")
    today = pd.Timestamp(today_date).date()
    g = games[games["game_date"].dt.date == today]
    slugs = set()
    slugs.update(g["home_probable_pitcher"].dropna())
    slugs.update(g["away_probable_pitcher"].dropna())
    return frozenset(slugs)

_pp_slugs = set(_load_pp_today(str(today_paris)))

# Source 2 : API Sorare (matchs à venir de la GW, filtrés sur aujourd'hui)
try:
    _df_pp, _ = load_upcoming_pitchers()
    if not _df_pp.empty:
        _df_pp_today = _df_pp[_df_pp["game_date"].dt.date == today_paris]
        _pp_slugs.update(_df_pp_today["home_pitcher_slug"].dropna())
        _pp_slugs.update(_df_pp_today["away_pitcher_slug"].dropna())
except Exception:
    pass

df_today["is_pp"] = df_today["player_slug"].isin(_pp_slugs)

# Predictions ML
if not df_ml.empty:
    _ml_mgr = df_ml[df_ml["gallery_manager"] == sel_manager].drop_duplicates("player_slug")
    _ml_map = _ml_mgr.set_index("player_slug")[["pred_median","pred_lo","pred_hi"]]
    df_today["pred_median"] = df_today["player_slug"].map(_ml_map["pred_median"])
    df_today["pred_lo"]     = df_today["player_slug"].map(_ml_map["pred_lo"])
    df_today["pred_hi"]     = df_today["player_slug"].map(_ml_map["pred_hi"])
else:
    df_today["pred_median"] = float("nan")
    df_today["pred_lo"]     = float("nan")
    df_today["pred_hi"]     = float("nan")

# ── Ticker ──────────────────────────────────────────────────────────────────────
render_ticker(df_all, sel_manager, today_paris)

# ── Tabs ────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
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
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — MA GALERIE
# ═══════════════════════════════════════════════════════════════════════════════

with tab1:
    if sel_day is not None:
        _tab1_day_label = pd.Timestamp(sel_day).strftime("%A %d %B").capitalize()
        st.caption(f"📅 {_tab1_day_label}")
    else:
        _tab1_day_label = now_paris.strftime("%A %d %B").capitalize()
        st.caption(f"📅 {_tab1_day_label}")

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

    _pred_avg = df_view["pred_median"].mean() if "pred_median" in df_view.columns and df_view["pred_median"].notna().any() else None
    _pred_std = df_view["pred_median"].std()  if _pred_avg is not None else None
    _pred_max_row = df_view.loc[df_view["pred_median"].idxmax()] if _pred_avg is not None and len(df_view) > 0 else None
    _n_is   = int((df_view["in_season_eligible"] == True).sum())
    _n_pp   = int(df_view.get("is_pp", pd.Series(dtype=bool)).sum()) if "is_pp" in df_view.columns else 0
    _pred_avg_str = f"{_pred_avg:.1f}" if _pred_avg is not None and not pd.isna(_pred_avg) else "—"
    _pred_std_str = f"±{_pred_std:.1f}" if _pred_std is not None and not pd.isna(_pred_std) else ""
    _pred_max_str = (_pred_max_row["player_name"].split()[-1] if _pred_max_row is not None else "—")
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
        f'<div class="ls-cell"><div class="k">Pred. moyenne</div>'
        f'<div class="v pos">{_pred_avg_str}</div><div class="sub">σ {_pred_std_str}</div></div>'
        f'<div class="ls-cell"><div class="k">Pred. max</div>'
        f'<div class="v">{_pred_max_str}</div></div>'
        f'<div class="ls-cell"><div class="k">IS / PP</div>'
        f'<div class="v accent">{_n_is}</div><div class="sub">{_n_pp} probable pitchers</div></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    if df_view.empty:
        if sel_day is not None:
            st.info(f"Aucun joueur de ta galerie ne joue le {_tab1_day_label}.")
        else:
            st.info("Aucun joueur de ta galerie ne correspond aux filtres sélectionnés.")
    else:
        st.markdown(
            f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none;margin-top:8px">'
            f'<span class="title">Suggestion d\'alignement</span>'
            f'<span class="pill">TOP 3</span>'
            f'<span class="right" style="color:var(--fg-3);font-size:9px">tri par {sel_stat_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # Sparklines pour tous les joueurs visibles (top3 + classement)
        _spark_map = load_stat_sparklines(
            tuple(df_view["player_slug"].tolist()), sel_stat_label
        )

        # Mapping slug → picture_url : carte IS la plus récente, sinon rareté max
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

        top3      = df_view.head(3)
        top3_cols = st.columns(len(top3))
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
                if st.button("Historique", key=f"hist_top_{i}", use_container_width=True):
                    show_player_chart(row["player_slug"], row["player_name"],
                                      sel_stat, sel_stat_label, target)

        st.markdown('<div class="divider-h"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
            f'<span class="title">Classement du jour</span>'
            f'<span class="pill">{len(df_view)} joueurs</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        _RAR_COLOR = {"limited": "var(--r-limited)", "rare": "var(--r-rare)",
                      "super_rare": "var(--r-superrare)", "unique": "var(--r-unique)"}

        rows_html = ""
        for _, row in df_view.iterrows():
            _slug    = row["player_slug"]
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
            _moy     = f'{row["moyenne"]:.2f}'
            _matchs  = int(row["nb_matchs"])
            _heure   = row.get("coup_envoi") or "—"
            _matchup = row.get("matchup") or "—"
            rows_html += (
                f'<tr>'
                f'<td class="t1-player">'
                f'<div class="t1-name">{row["player_name"]}</div>'
                f'<div class="t1-meta">'
                f'<span style="color:{_rar_col}">{_rar_lbl}</span>'
                f'<span style="color:var(--fg-3)">·</span>'
                f'<span>{_pos}</span>'
                f'{_is_tag}{_pp_tag}'
                f'</div></td>'
                f'<td class="t1-spark">{_spark}</td>'
                f'<td class="t1-num" style="color:var(--pos)">{_moy}</td>'
                f'<td class="t1-num" style="color:var(--fg-3);font-size:10px">{_matchs}</td>'
                f'<td class="t1-heure">{_heure}</td>'
                f'<td class="t1-adv">{_matchup}</td>'
                f'</tr>'
            )

        st.markdown(
            f'<table class="t1-table">'
            f'<thead><tr>'
            f'<th>Joueur</th>'
            f'<th>Tendance</th>'
            f'<th class="r">{sel_stat_label}</th>'
            f'<th class="r">Matchs</th>'
            f'<th class="r">Heure</th>'
            f'<th>Adversaire</th>'
            f'</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            f'</table>',
            unsafe_allow_html=True,
        )

        # Historique via selectbox
        _hist_names = df_view["player_name"].tolist()
        _hist_sel = st.selectbox(
            "📊 Historique", ["—"] + _hist_names,
            key="tab1_hist_sel", label_visibility="collapsed",
        )
        if _hist_sel and _hist_sel != "—":
            _hist_row = df_view[df_view["player_name"] == _hist_sel].iloc[0]
            show_player_chart(_hist_row["player_slug"], _hist_row["player_name"],
                              sel_stat, sel_stat_label, target)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MES CARTES
# ═══════════════════════════════════════════════════════════════════════════════

with tab2:
    df_p = df_prices[df_prices["gallery_manager"] == sel_manager].copy()

    if df_p.empty:
        st.info("Aucune carte trouvée.")
    else:
        # Métriques portefeuille
        val_is  = df_p["price_in_season"].sum()
        val_oos = df_p["price_out_season"].sum()
        n_priced = df_p["price_in_season"].notna().sum()

        st.markdown(
            f'<div class="metrics">'
            f'<div class="metric"><div class="k">Cartes</div><div class="v">{len(df_p)}</div></div>'
            f'<div class="metric"><div class="k">Avec prix</div><div class="v">{int(n_priced)}</div></div>'
            f'<div class="metric"><div class="k">Valeur IS</div><div class="v pos">{val_is:.0f} €</div></div>'
            f'<div class="metric"><div class="k">Valeur Classic</div><div class="v" style="color:var(--fg-2)">{val_oos:.0f} €</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # Filtres inline
        col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])
        with col_f1:
            raretés_filtre = sorted(df_p["card_display_rarity"].dropna().unique(),
                                    key=lambda r: RARITY_ORDER.get(r.lower() if r else "", 99))
            sel_rar_p = st.multiselect("Rareté", raretés_filtre, default=raretés_filtre, key="rar_prices")
        with col_f2:
            positions_filtre = sorted(df_p["position_agg"].dropna().unique())
            sel_pos_p = st.multiselect("Poste", positions_filtre, default=positions_filtre, key="pos_prices")
        with col_f3:
            tri_options = {
                "Power desc":  ("card_power", False),
                "Carte A-Z":   ("card_name",  True),
            }
            tri_label = st.selectbox("Trier par", list(tri_options.keys()), key="sort_prices")
            tri_col, tri_asc = tri_options[tri_label]
        with col_f4:
            remise_pct = st.number_input(
                "Remise (%)", min_value=0, max_value=100, value=0, step=5,
                key="remise_pct", help="% remise crédits marketplace appliquée au prix d'achat",
            )

        df_p_f = df_p[
            df_p["card_display_rarity"].isin(sel_rar_p) &
            df_p["position_agg"].isin(sel_pos_p)
        ].sort_values(tri_col, ascending=tri_asc).reset_index(drop=True)

        # Barre de progression XP
        _xp_next = df_p_f["card_xp_needed_next_grade"].replace(0, None)
        df_p_f["xp_pct"] = (df_p_f["card_xp"].fillna(0) / _xp_next.fillna(1)).clip(0, 1) * 100

        if "purchase_price_eur" in df_p_f.columns:
            df_p_f["purchase_price"] = pd.to_numeric(df_p_f["purchase_price_eur"], errors="coerce")
            if remise_pct > 0:
                df_p_f["purchase_price"] = (
                    df_p_f["purchase_price"] * (1 - remise_pct / 100)
                ).round(2)
        else:
            df_p_f["purchase_price"] = None

        table_p = df_p_f[[
            "picture_url", "card_name", "position_agg", "card_display_rarity",
            "card_power", "card_grade", "xp_pct", "purchase_price", "in_season_eligible",
        ]].rename(columns={
            "picture_url":         "Image",
            "card_name":           "Carte",
            "position_agg":        "Poste",
            "card_display_rarity": "Rareté",
            "card_power":          "Power",
            "card_grade":          "Grade",
            "xp_pct":              "XP",
            "purchase_price":      "Prix achat (€)",
            "in_season_eligible":  "In Season",
        })

        st.dataframe(
            table_p,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Image":          st.column_config.ImageColumn(width="medium"),
                "Grade":          st.column_config.NumberColumn(format="%d"),
                "XP":             st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
                "Power":          st.column_config.NumberColumn(format="%.2f"),
                "Prix achat (€)": st.column_config.NumberColumn(format="%.2f €"),
                "In Season":      st.column_config.CheckboxColumn(),
            },
        )
        st.caption(f"{len(df_p_f)} cartes affichées")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — BASE DE DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

with tab3:
    fenetre_int = FENETRE_OPTIONS[fenetre]
    df_db = load_db_stats(sel_stat, fenetre_int)

    col_f1, col_f2 = st.columns([3, 2])
    with col_f1:
        positions_db = sorted(df_db["agg_position"].dropna().unique())
        sel_pos_db   = st.multiselect("Position", positions_db, default=positions_db, key="pos_db")
    with col_f2:
        top_n      = st.number_input("Top N", min_value=5, max_value=200, value=50, step=5)
        max_m      = int(df_db["nb_matchs"].max()) if not df_db.empty else fenetre_int
        min_matchs = st.slider("Matchs minimum", 1, max_m, min(3, max_m), key="min_m_db")

    df_db_f = (
        df_db[
            (df_db["agg_position"].isin(sel_pos_db)) &
            (df_db["nb_matchs"] >= min_matchs)
        ]
        .head(int(top_n))
        .reset_index(drop=True)
    )

    st.markdown(
        f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
        f'<span class="title">Top {int(top_n)} — {sel_stat_label}</span>'
        f'<span class="pill">{fenetre}</span>'
        f'<span class="right" style="color:var(--fg-3);font-size:9px">{len(df_db_f)} / {len(df_db)} joueurs</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if df_db_f.empty:
        st.info("Aucun joueur ne correspond aux filtres.")
    else:
        table_db = df_db_f[[
            "display_name", "position_exact", "agg_position", "team_slug", "moyenne", "nb_matchs",
        ]].rename(columns={
            "display_name":  "Joueur",
            "position_exact": "Poste",
            "agg_position":  "Position",
            "team_slug":     "Equipe",
            "moyenne":       sel_stat_label,
            "nb_matchs":     "Matchs",
        })

        event_db = st.dataframe(
            table_db, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row",
        )
        sel_db = event_db.selection.rows
        if sel_db:
            idx_db = sel_db[0]
            if st.session_state.get("_tab2_sel") != idx_db:
                st.session_state["_tab2_sel"] = idx_db
                row_db = df_db_f.iloc[idx_db]
                show_player_chart(row_db["player_slug"], row_db["display_name"],
                                  sel_stat, sel_stat_label, target)
        else:
            st.session_state.pop("_tab2_sel", None)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — VIS-A-VIS
# ═══════════════════════════════════════════════════════════════════════════════

with tab4:
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

        # Galerie hitters (sans SP/RP)
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

        # Toggle galerie / tous
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

        # Construire paires hitter/pitcher
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

        # --- TABLE HITTERS ---
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

        # --- TABLE PITCHERS ---
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


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — PROJECTIONS GW
# ═══════════════════════════════════════════════════════════════════════════════

with tab5:
    try:
        df_p7, gw7 = load_upcoming_pitchers()
    except Exception as e:
        st.error(f"Impossible de charger les matchs : {e}")
        df_p7, gw7 = pd.DataFrame(), 0

    if df_p7.empty:
        st.info("Aucun match programmé pour le prochain fixture CLASSIC.")
    else:
        import math as _math
        _gw_teams7 = set(df_p7["home_team_slug"].dropna()) | set(df_p7["away_team_slug"].dropna())
        _gw_pit_slugs7 = set(df_p7["home_pitcher_slug"].dropna()) | set(df_p7["away_pitcher_slug"].dropna())

        # Galerie hitters & SP dans cette GW
        _gal_h7 = (
            df_calendar[
                (df_calendar["gallery_manager"] == sel_manager) &
                df_calendar["active_club_slug"].isin(_gw_teams7) &
                ~df_calendar["position_agg"].isin(["SP", "RP"])
            ]
            .drop_duplicates("player_slug")
        )
        _gal_sp7 = (
            df_calendar[
                (df_calendar["gallery_manager"] == sel_manager) &
                df_calendar["player_slug"].isin(_gw_pit_slugs7)
            ]
            .drop_duplicates("player_slug")
        )

        _h_slugs7    = tuple(_gal_h7["player_slug"])
        _p_slugs7    = tuple(_gal_sp7["player_slug"])
        _all_p7      = tuple(_gw_pit_slugs7)

        # Matchup stats : hitters galerie vs tous les pitchers de la GW
        df_mu7 = load_matchup_stats(_h_slugs7, _all_p7)
        mu7: dict = {}
        for _, r in df_mu7.iterrows():
            if pd.notna(r["avg_sorare_score"]):
                mu7[(r["hitter_slug"], r["pitcher_slug"])] = float(r["avg_sorare_score"])

        # Score moyen général des hitters (fallback si pas d'historique vs pitcher)
        _fen7      = FENETRE_OPTIONS[fenetre]
        df_havg7   = load_player_avg_scores(_h_slugs7, _fen7)
        havg7      = df_havg7.set_index("player_slug")["avg_score"].to_dict()

        # Score moyen des SP galerie (5 derniers matchs)
        df_pgen7, _ = load_pitcher_stats_vv(_p_slugs7, ())
        pavg7: dict = (
            df_pgen7.drop_duplicates("player_slug")
            .set_index("player_slug")["avg_sorare_score"]
            .dropna()
            .to_dict()
        ) if not df_pgen7.empty else {}

        # Calendrier par équipe : team_slug → [(pitcher_slug|None, opp_name, game_date)]
        team_sched7: dict = {}
        for _, g in df_p7.iterrows():
            hts, ats = g["home_team_slug"], g["away_team_slug"]
            gdt = g["game_date"]
            if hts:
                team_sched7.setdefault(hts, []).append({
                    "pitcher_slug": g["away_pitcher_slug"] or None,
                    "opp_name":     g["away_team_name"],
                    "game_date":    gdt,
                })
            if ats:
                team_sched7.setdefault(ats, []).append({
                    "pitcher_slug": g["home_pitcher_slug"] or None,
                    "opp_name":     g["home_team_name"],
                    "game_date":    gdt,
                })

        max_games7 = max((len(v) for v in team_sched7.values()), default=0)

        # Map Sorare GW projected score (depuis card_prices, galerie uniquement)
        _sorare_proj7: dict = (
            df_prices[df_prices["gallery_manager"] == sel_manager]
            .drop_duplicates("player_slug")
            .set_index("player_slug")["next_gw_projected_score"]
            .dropna()
            .to_dict()
        )

        # Map ML predictions pour cette GW
        _ml7: dict = {}
        if not df_ml.empty:
            _ml7 = (
                df_ml[df_ml["gallery_manager"] == sel_manager]
                .drop_duplicates("player_slug")
                .set_index("player_slug")[[
                    "pred_median", "pred_lo", "pred_hi",
                    "pred_contextual", "park_factor", "weather_factor",
                    "opp_quality_factor", "day_night_factor", "rest_factor", "home_away_factor",
                    "platoon_factor_C", "bat_hand", "opp_pitcher_hand",
                ]]
                .to_dict("index")
            )

        # Calcul des projections
        proj7 = []

        for _, row in _gal_h7.iterrows():
            h_slug  = row["player_slug"]
            h_team  = row["active_club_slug"]
            games   = sorted(team_sched7.get(h_team, []), key=lambda x: x["game_date"])
            total   = 0.0
            nb_g    = 0
            game_scores = []
            for gm in games:
                ps    = gm["pitcher_slug"]
                score = (mu7.get((h_slug, ps)) if ps else None) or havg7.get(h_slug)
                if score is not None:
                    total += score
                    nb_g  += 1
                game_scores.append(round(score, 1) if score is not None else None)

            ml_d   = _ml7.get(h_slug)
            ml_med = round(ml_d["pred_median"] * nb_g, 1) if ml_d and nb_g > 0 else None
            _ctx7  = ml_d.get("pred_contextual") if ml_d else None
            ctx_pred = (round(float(_ctx7) * nb_g, 1)
                        if (_ctx7 is not None and not _math.isnan(float(_ctx7)) and nb_g > 0)
                        else None)

            entry = {
                "player_slug":        h_slug,
                "player_name":        row["player_name"],
                "position_agg":       row["position_agg"] or "?",
                "in_season_eligible": row["in_season_eligible"],
                "category":           "Hitter",
                "nb_games":           nb_g,
                "projected_score":    round(total, 1) if nb_g > 0 else None,
                "sorare_proj":        _sorare_proj7.get(h_slug),
                "ml_pred":            ml_med,
                "ctx_pred":           ctx_pred,
                "bat_hand":           ml_d.get("bat_hand")           if ml_d else None,
                "opp_pitcher_hand":   ml_d.get("opp_pitcher_hand")   if ml_d else None,
                "platoon_factor_C":   ml_d.get("platoon_factor_C")   if ml_d else None,
                "park_factor":        ml_d.get("park_factor")        if ml_d else None,
                "weather_factor":     ml_d.get("weather_factor")     if ml_d else None,
                "opp_quality_factor": ml_d.get("opp_quality_factor") if ml_d else None,
                "home_away_factor":   ml_d.get("home_away_factor")   if ml_d else None,
                "day_night_factor":   ml_d.get("day_night_factor")   if ml_d else None,
                "rest_factor":        ml_d.get("rest_factor")        if ml_d else None,
            }
            for i, gs in enumerate(game_scores):
                entry[f"G{i+1}"] = gs
            proj7.append(entry)

        for _, row in _gal_sp7.iterrows():
            ps    = row["player_slug"]
            score = pavg7.get(ps)
            ml_d  = _ml7.get(ps)
            _ng_sp7 = 1 if score is not None else 0
            _ctx_sp = ml_d.get("pred_contextual") if ml_d else None
            ctx_pred_sp = (round(float(_ctx_sp) * _ng_sp7, 1)
                           if (_ctx_sp is not None and not _math.isnan(float(_ctx_sp)) and _ng_sp7 > 0)
                           else None)
            entry = {
                "player_slug":        ps,
                "player_name":        row["player_name"],
                "position_agg":       row["position_agg"] or "SP",
                "in_season_eligible": row["in_season_eligible"],
                "category":           "SP",
                "nb_games":           _ng_sp7,
                "projected_score":    round(float(score), 1) if score is not None else None,
                "sorare_proj":        _sorare_proj7.get(ps),
                "ml_pred":            ml_d["pred_median"] if ml_d else None,
                "ctx_pred":           ctx_pred_sp,
                "bat_hand":           None,
                "opp_pitcher_hand":   None,
                "platoon_factor_C":   None,
                "park_factor":        ml_d.get("park_factor")        if ml_d else None,
                "weather_factor":     ml_d.get("weather_factor")     if ml_d else None,
                "opp_quality_factor": ml_d.get("opp_quality_factor") if ml_d else None,
                "home_away_factor":   ml_d.get("home_away_factor")   if ml_d else None,
                "day_night_factor":   ml_d.get("day_night_factor")   if ml_d else None,
                "rest_factor":        ml_d.get("rest_factor")        if ml_d else None,
                "G1":                 round(float(score), 1) if score is not None else None,
            }
            proj7.append(entry)

        df7 = pd.DataFrame(proj7)
        game_cols7 = (
            [f"G{i+1}" for i in range(max_games7) if f"G{i+1}" in df7.columns]
            if not df7.empty else []
        )

        # ── Extension : tous les joueurs de la GW (via ML) ───────────────────
        _show_all7 = st.checkbox(
            "Charger les données de tous les joueurs", value=False, key="proj7_all"
        )
        if _show_all7 and not df_ml.empty:
            _already7 = set(df7["player_slug"]) if not df7.empty else set()
            _extra7   = []
            for _, _mr7 in df_ml.iterrows():
                _s7 = _mr7["player_slug"]
                if _s7 in _already7:
                    continue
                _pos7_raw = str(_mr7.get("position", ""))
                _pos7_agg = POSITION_AGG.get(_pos7_raw, POSITION_EXACT.get(_pos7_raw, _pos7_raw))
                _isp7     = _pos7_agg in ("SP", "RP")
                _ng7      = int(_mr7.get("n_games_gw") or 0)
                _mu7_     = float(_mr7["pred_median"] or 0)
                _mm7      = round(_mu7_ * _ng7, 1) if _ng7 > 0 else None
                _ctx7_raw = _mr7.get("pred_contextual")
                _ctx7_tot = (round(float(_ctx7_raw) * _ng7, 1)
                             if (_ctx7_raw is not None and not _math.isnan(float(_ctx7_raw)) and _ng7 > 0)
                             else None)
                _extra7.append({
                    "player_slug":        _s7,
                    "player_name":        _mr7["player_name"],
                    "position_agg":       _pos7_agg,
                    "in_season_eligible": None,
                    "category":           "SP" if _isp7 else "Hitter",
                    "nb_games":           _ng7,
                    "projected_score":    None,
                    "ml_pred":            _mm7,
                    "ctx_pred":           _ctx7_tot,
                    "bat_hand":           _mr7.get("bat_hand") if not _isp7 else None,
                    "opp_pitcher_hand":   _mr7.get("opp_pitcher_hand") if not _isp7 else None,
                    "platoon_factor_C":   _mr7.get("platoon_factor_C") if not _isp7 else None,
                    "park_factor":        _mr7.get("park_factor"),
                    "weather_factor":     _mr7.get("weather_factor"),
                    "opp_quality_factor": _mr7.get("opp_quality_factor"),
                    "home_away_factor":   _mr7.get("home_away_factor"),
                    "day_night_factor":   _mr7.get("day_night_factor"),
                    "rest_factor":        _mr7.get("rest_factor"),
                })
            if _extra7:
                df7 = pd.concat([df7, pd.DataFrame(_extra7)], ignore_index=True)

        # ── Filtres + tri ─────────────────────────────────────────────────────
        st.markdown(
            f'<div class="panel__hd" style="border:1px solid var(--line);border-bottom:none">'
            f'<span class="title">GW{gw7} — Projections</span>'
            f'<span class="pill accent">ML + CTX</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        col7f1, col7f2, col7f3 = st.columns([2, 3, 4])
        with col7f1:
            show_cat7 = st.radio(
                "Catégorie", ["Hitter", "SP"],
                horizontal=True, key="proj7_cat",
            )
        with col7f2:
            _pos_opts7 = (
                ["CI", "MI", "OF"] if show_cat7 == "Hitter" else ["SP", "RP"]
            )
            sel_pos7 = st.multiselect(
                "Poste", _pos_opts7, default=_pos_opts7, key="proj7_pos",
            )
        with col7f3:
            sort_by7 = st.radio(
                "Trier par", ["Score historique", "Prédiction ML", "CTX", "Sorare proj."],
                horizontal=True, key="proj7_sort",
            )

        df7_f = df7[df7["category"] == show_cat7].copy() if not df7.empty else pd.DataFrame()
        if not df7_f.empty and sel_pos7:
            df7_f = df7_f[df7_f["position_agg"].isin(sel_pos7)]

        sort_map7 = {
            "Score historique": ("projected_score", False),
            "Prédiction ML":    ("ml_pred", False),
            "CTX":              ("ctx_pred", False),
            "Sorare proj.":     ("sorare_proj", False),
        }
        sort_col7, sort_asc7 = sort_map7[sort_by7]
        if not df7_f.empty:
            df7_f = df7_f.sort_values(sort_col7, ascending=sort_asc7, na_position="last")

        # ── Tableau ──────────────────────────────────────────────────────────
        display_cols7 = (
            ["player_name", "position_agg", "in_season_eligible", "projected_score"]
            + game_cols7
            + ["sorare_proj", "ml_pred",
               "bat_hand", "opp_pitcher_hand", "platoon_factor_C",
               "park_factor", "weather_factor", "opp_quality_factor",
               "home_away_factor", "day_night_factor", "rest_factor", "ctx_pred"]
        )
        display_cols7 = [c for c in display_cols7 if not df7_f.empty and c in df7_f.columns]

        col_config7 = {
            "player_name":        st.column_config.TextColumn("Joueur"),
            "position_agg":       st.column_config.TextColumn("Poste"),
            "in_season_eligible": st.column_config.CheckboxColumn("In Season"),
            "projected_score":    st.column_config.NumberColumn("Score hist. GW", format="%.1f"),
            "sorare_proj":        st.column_config.NumberColumn("Sorare proj.", format="%.1f"),
            "ml_pred":            st.column_config.NumberColumn("ML pred.", format="%.1f"),
            "bat_hand":           st.column_config.TextColumn("Main"),
            "opp_pitcher_hand":   st.column_config.TextColumn("Pitcher(s)"),
            "platoon_factor_C":   st.column_config.NumberColumn("⚾ Platoon", format="%.3f"),
            "park_factor":        st.column_config.NumberColumn("🏟 Stade", format="%.2f"),
            "weather_factor":     st.column_config.NumberColumn("🌬 Météo", format="%.2f"),
            "opp_quality_factor": st.column_config.NumberColumn("⚔ Adv.", format="%.2f"),
            "home_away_factor":   st.column_config.NumberColumn("🏠 Dom.", format="%.2f"),
            "day_night_factor":   st.column_config.NumberColumn("☀ J/N", format="%.2f"),
            "rest_factor":        st.column_config.NumberColumn("💤 Repos", format="%.2f"),
            "ctx_pred":           st.column_config.NumberColumn("CTX", format="%.1f"),
        }
        for gc in game_cols7:
            col_config7[gc] = st.column_config.NumberColumn(gc, format="%.1f")

        st.dataframe(
            df7_f[display_cols7].reset_index(drop=True) if not df7_f.empty else pd.DataFrame(),
            use_container_width=True,
            hide_index=True,
            column_config=col_config7,
        )
        st.caption(f"{len(df7_f)} joueurs affichés")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — CONSTRUCTION D'ÉQUIPE
# ═══════════════════════════════════════════════════════════════════════════════

with tab6:
    _t8_comp, _t8_arena = st.tabs(["🏗️ Compétitions", "🏟️ Arena"])


with _t8_comp:
    from collections import Counter as _Counter

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

    # ── Contrôles ─────────────────────────────────────────────────────────────
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

    # ── State par mode × rareté ────────────────────────────────────────────────
    _tb_sk = f"tb_teams_{tb_mode}_{tb_rar}"
    _DEFAULT_N_TEAMS_INIT = {"Champions": 3, "Hot Streak": 4, "Challenger": 4}
    if _tb_sk not in st.session_state:
        _n_init = _DEFAULT_N_TEAMS_INIT.get(tb_mode, 1)
        st.session_state[_tb_sk] = [_EMPTY_TEAM() for _ in range(_n_init)]
    tb_teams = st.session_state[_tb_sk]

    # ── Joueurs disponibles (hors blessés) ────────────────────────────────────
    df_tb = (
        df_prices[
            (df_prices["gallery_manager"] == sel_manager) &
            (df_prices["card_display_rarity"].str.lower() == tb_rar.lower()) &
            ~df_prices["player_slug"].isin(_injured_slugs)
        ]
        .drop_duplicates("card_name")
        .copy()
    )
    df_tb["position_agg"] = df_tb["card_display_position"].map(POSITION_AGG)
    df_tb["is_eligible"]  = df_tb["in_season_eligible"] == True

    # Scores GW projetés — on utilise TOUTE la galerie du manager comme clé de cache
    # (pas juste la rareté sélectionnée) pour que le cache reste chaud quand on change de rareté
    _all_gal_prices = df_prices[df_prices["gallery_manager"] == sel_manager]
    _all_gal_slugs  = tuple(_all_gal_prices["player_slug"].unique())
    _all_gal_h_slugs = tuple(
        _all_gal_prices[
            ~_all_gal_prices["card_display_position"].map(POSITION_AGG).isin(["SP", "RP"])
        ]["player_slug"].unique()
    )
    _avg_tb  = load_player_avg_scores(_all_gal_slugs, FENETRE_OPTIONS[fenetre])
    _smap_tb = _avg_tb.set_index("player_slug")["avg_score"].to_dict()

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

    # Prediction ML GW : pred_contextual * nb_matchs_dans_la_GW
    if not df_ml.empty:
        _ml8 = (
            df_ml[df_ml["gallery_manager"] == sel_manager]
            .drop_duplicates("player_slug")
            .set_index("player_slug")["pred_contextual"]
        )
        _tsched8_len = {t: len(g) for t, g in _tsched8.items()} if not _df_p8.empty else {}

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
        # proj_score = ML si dispo, sinon historique
        df_tb["proj_score"] = df_tb["proj_score_ml"].combine_first(df_tb["proj_score_hist"])
    else:
        df_tb["proj_score_ml"] = None
        df_tb["proj_score"]    = df_tb["proj_score_hist"]

    # Indicateur Sorare GW+ : nextClassicFixtureProjectedScore brut
    _sorare_gw = pd.to_numeric(df_tb.get("next_gw_projected_score", pd.Series(dtype=float)), errors="coerce")
    df_tb["proj_score_sorare"] = _sorare_gw

    # Score de référence selon l'indicateur choisi
    if tb_score_src == "Sorare GW+":
        _base_score = _sorare_gw.fillna(0.0)
    else:
        _base_score = pd.to_numeric(df_tb["proj_score"], errors="coerce").fillna(0.0)

    # Score effectif = score de référence × power de la carte (bonus Sorare)
    _power_num = pd.to_numeric(df_tb["card_power"], errors="coerce").fillna(1.0)
    df_tb["proj_score_eff"] = (_base_score * _power_num).round(1)
    # Score effectif figé pour chaque source (pour sauvegarder les 2 suggestions au save)
    df_tb["proj_score_eff_auto"]   = (pd.to_numeric(df_tb["proj_score"],        errors="coerce").fillna(0.0) * _power_num).round(1)
    df_tb["proj_score_eff_sorare"] = (pd.to_numeric(df_tb["proj_score_sorare"], errors="coerce").fillna(0.0) * _power_num).round(1)

    # Exclure les SP non-probables quand les données de calendrier sont disponibles
    if _tsched8:
        _probable_sp_slugs = {
            g["pitcher_slug"]
            for games in _tsched8.values()
            for g in games
            if g["pitcher_slug"]
        }
        _is_sp = df_tb["position_agg"] == "SP"
        df_tb = df_tb[~_is_sp | df_tb["player_slug"].isin(_probable_sp_slugs)].reset_index(drop=True)

    # Index card_name → row
    _cl = df_tb.set_index("card_name").to_dict("index")

    # ── Helpers ───────────────────────────────────────────────────────────────
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
        if tb_score_src == "Sorare GW+":
            src = "SOR" if r.get("proj_score_sorare") is not None else "—"
        else:
            src = "ML" if r.get("proj_score_ml") is not None else "~"
        return f"{x}  [{pos} · {is_} · {sc:.0f} pts eff. · ×{pwr:.3f} · {src}]"

    def _tb_suggest(other_used: set, other_used_slugs: set, require_is: bool,
                    score_col: str = "proj_score_eff",
                    slot_pos: dict | None = None,
                    df_pool: pd.DataFrame | None = None,
                    locked: dict | None = None) -> dict:
        """Greedy team builder : maximise score_col, force ≥6 IS si requis.
        locked : dict slot_name → card_name à conserver tels quels."""
        _df      = df_pool if df_pool is not None else df_tb
        _spos    = slot_pos if slot_pos is not None else _SLOT_POS
        _locked  = locked or {}
        is_map   = _df.set_index("card_name")["is_eligible"].to_dict()
        slug_map = _df.set_index("card_name")["player_slug"].to_dict()

        _eff_col  = score_col if score_col in _df.columns else "proj_score_eff"
        _locked_cards = {c for c in _locked.values() if c}
        _locked_slugs = {slug_map.get(c, "") for c in _locked_cards}

        def _fill_is(pre_filled: dict, excl_cards: set, excl_slugs: set) -> dict:
            """Greedy IS fill pour tous les slots non pré-remplis et non verrouillés."""
            res       = dict(pre_filled)
            _used     = {c for c in res.values() if c}
            _u_slugs  = {slug_map.get(c, "") for c in _used}
            for sname, valid_pos in _spos.items():
                if sname in res:
                    continue
                cands_all = _df[
                    _df["position_agg"].isin(valid_pos) &
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

        # ── Passe 1 : équipe tout IS ─────────────────────────────────────────────
        result = _fill_is(dict(_locked), other_used, other_used_slugs)

        # ── Passe 2 (require_is) : tester chaque slot comme slot non-IS ─────────
        # Pour chaque slot candidat : place le meilleur non-IS, re-remplit TOUS
        # les autres slots IS depuis zéro → la carte IS libérée peut aller ailleurs.
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
                    # Trouver le meilleur non-IS pour ce slot (sans contrainte sur les autres slots)
                    non_is_c = _df[
                        _df["position_agg"].isin(valid_pos) &
                        ~_df["card_name"].isin(other_used | _locked_cards) &
                        ~_df["player_slug"].isin(other_used_slugs | _locked_slugs) &
                        ~_df["is_eligible"]
                    ].sort_values(_eff_col, ascending=False)
                    if non_is_c.empty:
                        continue
                    ni_card = non_is_c.iloc[0]["card_name"]
                    # Re-remplir tous les autres slots IS depuis zéro
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
        """Retourne (is_count, max_club_count, total_score_eff, n_filled)."""
        cards = [v for v in team.values() if v]
        if not cards:
            return 0, 0, 0.0, 0
        is_c   = sum(1 for c in cards if _cl.get(c, {}).get("is_eligible", False))
        clubs  = [_cl.get(c, {}).get("active_club_slug", "") for c in cards]
        max_cl = max(_Counter(clubs).values()) if clubs else 0
        score  = sum(float(_cl.get(c, {}).get("proj_score_eff") or 0.0) for c in cards)
        return is_c, max_cl, score, len(cards)

    # ── Ajout / suppression d'équipe ──────────────────────────────────────────
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
                    st.session_state[f"tb_{_i}_{_sl}"] = "—"
                st.session_state[f"tb_locks_{_i}"] = set()
            st.rerun()

    st.divider()

    # Map global card_name → player_slug (toutes raretés, pour détecter doublons joueur)
    _global_card_slug = (
        df_prices[df_prices["gallery_manager"] == sel_manager]
        .drop_duplicates("card_name")
        .set_index("card_name")["player_slug"]
        .to_dict()
    )

    # ── Éditeur de chaque équipe ───────────────────────────────────────────────
    for _ti, _team in enumerate(tb_teams):
        # Cartes utilisées dans les AUTRES équipes (tous modes × raretés confondus)
        _all_used_cards = {
            c
            for key, teams in st.session_state.items()
            if (key.startswith("tb_teams_") or key.startswith("ar9_teams_")) and isinstance(teams, list)
            for t in teams
            for c in t.values()
            if c
        }
        # Cartes déjà utilisées dans d'autres équipes (même carte interdite cross-team)
        _other_used = _all_used_cards - {v for v in tb_teams[_ti].values() if v}

        _locks_key = f"tb_locks_{_ti}"
        if _locks_key not in st.session_state:
            st.session_state[_locks_key] = set()
        _locks = st.session_state[_locks_key]

        with st.expander(f"Équipe {_ti + 1}", expanded=True):
            # Boutons suggérer / vider / déverrouiller
            _cs, _cc, _cul = st.columns([2, 2, 2])
            with _cs:
                if st.button("✨ Suggérer l'équipe", key=f"tb_sug_{_ti}"):
                    _locked_cards = {s: tb_teams[_ti].get(s) for s in _locks if tb_teams[_ti].get(s)}
                    _sug = _tb_suggest(_other_used, set(), _require_is, locked=_locked_cards)
                    tb_teams[_ti] = _sug
                    for _sl, _cn in _sug.items():
                        if _sl not in _locks:
                            st.session_state[f"tb_{_ti}_{_sl}"] = _cn if _cn is not None else "—"
                    st.rerun()
            with _cc:
                if st.button("🗑️ Vider", key=f"tb_clr_{_ti}"):
                    tb_teams[_ti] = _EMPTY_TEAM()
                    st.session_state[_locks_key] = set()
                    for _sl in _SLOT_POS:
                        st.session_state[f"tb_{_ti}_{_sl}"] = "—"
                    st.rerun()
            with _cul:
                if _locks and st.button("🔓 Déverrouiller tout", key=f"tb_unlock_{_ti}"):
                    st.session_state[_locks_key] = set()
                    st.rerun()

            # Slots en deux colonnes
            _col_l, _col_r = st.columns(2)
            for _si, (_sname, _vpos) in enumerate(_SLOT_POS.items()):
                _col = _col_l if _si < 4 else _col_r
                with _col:
                    # Options disponibles pour ce slot
                    _in_team_used  = {v for k, v in _team.items() if v and k != _sname}
                    _in_team_slugs = {_global_card_slug[c] for c in _in_team_used if c in _global_card_slug}
                    _blocked_slugs = _in_team_slugs  # unicité joueur intra-équipe seulement
                    _cands = (
                        df_tb[
                            df_tb["position_agg"].isin(_vpos) &
                            ~df_tb["card_name"].isin(_other_used | _in_team_used) &
                            ~df_tb["player_slug"].isin(_blocked_slugs)
                        ]
                        .sort_values("proj_score_eff", ascending=False)
                    )
                    _opts    = ["—"] + _cands["card_name"].tolist()
                    _current = _team.get(_sname)
                    # Si la carte courante n'est plus disponible, la garder visible
                    if _current and _current not in _opts:
                        _opts.insert(1, _current)
                    # Initialise l'état widget depuis le dict équipe (évite le conflit index= vs session_state)
                    _wkey = f"tb_{_ti}_{_sname}"
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

            # Barre de validation
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

            # Résumé visuel — images des cartes sélectionnées
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

            # Bouton sauvegarder
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

                    # Exclure les cartes déjà suggérées dans les autres équipes sauvegardées (même GW/mode/rareté)
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


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7 — COMPÉTITIONS & RÉCOMPENSES
# ═══════════════════════════════════════════════════════════════════════════════

with tab7:
    pass


# ── Construction d'équipes Arena ──────────────────────────────────────────────

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
    _df_ar9["position_agg"] = _df_ar9["card_display_position"].map(POSITION_AGG)
    _df_ar9["is_eligible"]  = _df_ar9["in_season_eligible"] == True

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

    # Exclure joueurs sans match dans la GW courante (SP non programmés, etc.)
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

    # Multiplicateur n_games_gw : hitters × n_games, lanceurs (SP/RP) × 1
    _ar9_ngw_raw = (
        _df_ar9["_n_games_gw"].fillna(1.0)
        if "_n_games_gw" in _df_ar9.columns
        else pd.Series(1.0, index=_df_ar9.index)
    )
    _ar9_is_pitcher = _df_ar9["position_agg"].isin(["SP", "RP"])
    _ar9_ngw = _ar9_ngw_raw.where(~_ar9_is_pitcher, other=1.0)

    # hist × n_games ; ML (pred_contextual) × n_games ; Sorare GW+ déjà en total GW
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
    # Arena : pas de bonus card_power
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

    # Migration : ancienne clé → liste
    _ar9_old_sk = f"arena_{_ar9_type}_{_ar9_rar}"
    if _ar9_old_sk in st.session_state and _ar9_lk not in st.session_state:
        st.session_state[_ar9_lk] = [st.session_state.pop(_ar9_old_sk)]

    if _ar9_lk not in st.session_state:
        st.session_state[_ar9_lk] = [_EMPTY_AR9()]
    # Assurer que toutes les teams ont les bons slots (après changement de type)
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

        # ── Sélecteur de lineup + bouton "+" ──────────────────────────────────
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

        # Cartes déjà utilisées dans les équipes Compétitions ET dans les autres types d'Arena
        _ar9_used_comp = {
            c
            for key, teams in st.session_state.items()
            if (key.startswith("tb_teams_") or (key.startswith("ar9_teams_") and key != _ar9_lk))
            and isinstance(teams, list)
            for t in teams
            for c in t.values()
            if c
        }
        # Cartes utilisées dans les autres lineups Arena du même type
        _ar9_other_used = _ar9_used_comp | {
            c for _ni, _tc in enumerate(ar9_teams)
            if _ni != _ar9_ti
            for c in _tc.values() if c
        }
        _ar9_other_slugs = {_ar9_global_slug.get(c, "") for c in _ar9_other_used}

        _ar9_btn1, _ar9_btn2 = st.columns([2, 2])
        with _ar9_btn1:
            if st.button("✨ Suggérer l'équipe", key=f"ar9_sug_{_ar9_ti}"):
                _sug_ar9 = _tb_suggest(_ar9_other_used, _ar9_other_slugs, False,
                                       score_col="proj_score_eff",
                                       slot_pos=_ar9_sl,
                                       df_pool=_df_ar9)
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
                        _df_ar9["position_agg"].isin(_vp9) &
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
            from collections import Counter as _Ctr9
            _clubs9 = [_cl_ar9.get(c, {}).get("active_club_slug", "") for c in _cards9]
            _mc9    = max(_Ctr9(_clubs9).values()) if _clubs9 else 0
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


# ── Leaderboards & récompenses ────────────────────────────────────────────────

with tab7:
    import math as _math9
    import plotly.graph_objects as go

    if df_lb.empty:
        st.info("Aucune donnée de compétition. Lance `python fetch_leaderboard_history.py` pour collecter.")
        st.stop()

    _arena9 = df_lb[
        (df_lb["source"] == "arena") &
        ~df_lb["leaderboard_slug"].str.lower().str.endswith("_pve", na=False)
    ].copy()
    _hs9    = df_lb[df_lb["source"] == "hot_streak"].copy()

    # ── Filtres ───────────────────────────────────────────────────────────────
    _RAR_DISPLAY9 = {"limited": "Limited", "rare": "Rare", "super_rare": "Super Rare"}

    _col9a, _col9b, _col9c_filt = st.columns([2, 2, 3])
    with _col9a:
        _rar9 = st.radio(
            "Rareté", ["limited", "rare", "super_rare"],
            format_func=lambda r: _RAR_DISPLAY9.get(r, r),
            horizontal=True, key="lb9_rar",
        )
    _rar9_disp = _RAR_DISPLAY9.get(_rar9, _rar9)
    with _col9b:
        _arena_filter9 = st.radio(
            "Type", ["Toutes", "Arena", "Classiques"],
            horizontal=True, key="lb9_arena_filter",
        )

    # Mapping nom affiché → nom réel (pour garder le filtre sur leaderboard_name)
    _rar_df9 = _arena9[_arena9["rarity_type"] == _rar9].copy()
    if _arena_filter9 == "Arena":
        _rar_df9 = _rar_df9[_rar_df9["is_arena"] == True]
    elif _arena_filter9 == "Classiques":
        _rar_df9 = _rar_df9[_rar_df9["is_arena"] == False]

    # Table de correspondance : nom_affiché → nom_réel
    _name_map9 = {
        (f"ARENA — {n}" if bool(
            _rar_df9[_rar_df9["leaderboard_name"] == n]["is_arena"].any()
        ) else n): n
        for n in sorted(_rar_df9["leaderboard_name"].dropna().unique())
    }
    _all_comps9_disp = list(_name_map9.keys())
    _default_real9   = ["Champion"]
    _default_disp9   = [d for d, r in _name_map9.items() if r in _default_real9]

    with _col9c_filt:
        _sel_comps9_disp = st.multiselect(
            "Compétitions", _all_comps9_disp,
            default=_default_disp9,
            key="lb9_comps",
        )

    # Noms réels sélectionnés
    _sel_comps9 = [_name_map9[d] for d in _sel_comps9_disp if d in _name_map9]

    st.divider()

    # Sous-ensemble filtré
    _df9 = _arena9[
        (_arena9["rarity_type"] == _rar9) &
        (_arena9["leaderboard_name"].isin(_sel_comps9)) &
        _arena9["score_threshold"].notna() &
        _arena9["gw_int"].notna()
    ].copy()
    _df9["gw_int"] = _df9["gw_int"].astype(int)
    # Nom affiché : préfixe "ARENA — " pour les compétitions arena
    _rev_map9 = {v: k for k, v in _name_map9.items()}
    _df9["leaderboard_display"] = _df9["leaderboard_name"].map(_rev_map9).fillna(_df9["leaderboard_name"])

    # ── Section 1 : seuils d'entrée et de victoire par GW ────────────────────
    st.subheader("Évolution des seuils par compétition")
    st.caption("Seuil d'entrée = score minimum pour toute récompense · Seuil top = score le plus haut")

    _entry9 = (
        _df9.groupby(["gw_int", "leaderboard_display"], as_index=False)
        .agg(
            entry=("score_threshold", "min"),
            top=("score_threshold", "max"),
            median=("score_threshold", "median"),
            nb_div=("leaderboard_slug", "nunique"),
        )
        .sort_values("gw_int")
    )

    _COMP_COLORS = {
        "Champion":   "#f59e0b",
        "Challenger": "#ef4444",
        "Standard":   "#3b82f6",
        "American":   "#10b981",
        "National":   "#8b5cf6",
        "Beginner":   "#94a3b8",
        "Elite":      "#ec4899",
        "Hitters":    "#06b6d4",
        "Legacy":     "#a16207",
        "OG":         "#7c3aed",
        "Sandlot":    "#059669",
    }

    fig_entry = go.Figure()
    for comp_disp in _sel_comps9_disp:
        comp_real = _name_map9.get(comp_disp, comp_disp)
        sub = _entry9[_entry9["leaderboard_display"] == comp_disp]
        if sub.empty:
            continue
        color = _COMP_COLORS.get(comp_real, "#888")
        # Bande min-max (si plusieurs divisions)
        if (sub["top"] - sub["entry"]).max() > 1:
            fig_entry.add_trace(go.Scatter(
                x=list(sub["gw_int"]) + list(sub["gw_int"])[::-1],
                y=list(sub["top"]) + list(sub["entry"])[::-1],
                fill="toself",
                fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.10)",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ))
        # Ligne seuil d'entrée
        fig_entry.add_trace(go.Scatter(
            x=sub["gw_int"], y=sub["entry"],
            mode="lines+markers",
            name=f"{comp_disp} — entrée",
            line=dict(color=color, width=2, dash="dot"),
            marker=dict(size=6),
            customdata=sub[["nb_div"]].values,
            hovertemplate="%{y:.1f} pts · %{customdata[0]} division(s)<extra>%{fullData.name}</extra>",
        ))
        # Ligne top score
        fig_entry.add_trace(go.Scatter(
            x=sub["gw_int"], y=sub["top"],
            mode="lines+markers",
            name=f"{comp_disp} — top",
            line=dict(color=color, width=2),
            marker=dict(size=6),
            customdata=sub[["nb_div"]].values,
            hovertemplate="%{y:.1f} pts · %{customdata[0]} division(s)<extra>%{fullData.name}</extra>",
        ))

    # Ligne "entrée $" pour Champion : seuil minimum des paliers monétaires
    _champ_real9 = "Champion"
    _champ_disp9 = _rev_map9.get(_champ_real9, _champ_real9)
    if _champ_disp9 in _sel_comps9_disp:
        _champ_mon9 = (
            _df9[
                (_df9["leaderboard_name"] == _champ_real9) &
                (_df9["reward_type"] == "monetary") &
                _df9["score_threshold"].notna()
            ]
            .groupby("gw_int", as_index=False)
            .agg(entree_dollar=("score_threshold", "min"))
            .sort_values("gw_int")
        )
        if not _champ_mon9.empty:
            fig_entry.add_trace(go.Scatter(
                x=_champ_mon9["gw_int"], y=_champ_mon9["entree_dollar"],
                mode="lines+markers",
                name=f"{_champ_disp9} — entrée $",
                line=dict(color="#22c55e", width=2, dash="dashdot"),
                marker=dict(size=7, symbol="diamond"),
                hovertemplate="%{y:.1f} pts<extra>%{fullData.name}</extra>",
            ))

    _gw_min9 = int(_df9["gw_int"].min()) if not _df9.empty else 119
    _gw_max9 = int(_df9["gw_int"].max()) if not _df9.empty else 133
    fig_entry.update_layout(
        xaxis=dict(title="GW", tickmode="linear", dtick=1,
                   range=[_gw_min9 - 0.5, _gw_max9 + 0.5]),
        yaxis=dict(title="Score"),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        margin=dict(r=200),
    )
    st.plotly_chart(fig_entry, use_container_width=True)

    # ── Section 2 : paliers complets pour une compétition choisie ────────────
    st.divider()
    st.subheader("Structure des paliers — détail")

    _gws_sorted9 = sorted(_arena9["gw_int"].dropna().unique())

    _col9c, _col9d, _col9e = st.columns([2, 2, 2])
    with _col9c:
        _comp_detail9_disp = st.selectbox(
            "Compétition", _sel_comps9_disp if _sel_comps9_disp else _all_comps9_disp,
            key="lb9_comp_detail",
        )
    with _col9d:
        _detail_mode9 = st.radio(
            "Période", ["GW spécifique", "Moyenne 5 dernières GW"],
            horizontal=True, key="lb9_detail_mode",
        )
    _comp_detail9_real = _name_map9.get(_comp_detail9_disp, _comp_detail9_disp) if _comp_detail9_disp else None

    _gw_detail9 = None
    if _detail_mode9 == "GW spécifique":
        with _col9e:
            _gws_avail9 = sorted(
                _df9[_df9["leaderboard_name"] == _comp_detail9_real]["gw_int"].unique(), reverse=True
            ) if _comp_detail9_real else []
            _gw_detail9 = st.selectbox(
                "GW", _gws_avail9, index=0, key="lb9_gw_detail"
            ) if _gws_avail9 else None

    if _comp_detail9_real and (_gw_detail9 is not None or _detail_mode9 == "Moyenne 5 dernières GW"):
        _has_from_rank9 = "from_rank" in _df9.columns

        if _detail_mode9 == "GW spécifique":
            _detail9 = _df9[
                (_df9["leaderboard_name"] == _comp_detail9_real) &
                (_df9["gw_int"] == _gw_detail9) &
                _df9["score_threshold"].notna()
            ]
            _title_base9 = f"{_comp_detail9_disp} {_rar9_disp} — GW{_gw_detail9}"
        else:
            # 5 GWs les plus récentes en excluant la dernière (encore en cours)
            _gws_comp9 = sorted(_df9[_df9["leaderboard_name"] == _comp_detail9_real]["gw_int"].unique())
            _gws_comp_excl9 = _gws_comp9[:-1] if len(_gws_comp9) > 1 else _gws_comp9
            _last5_detail9  = _gws_comp_excl9[-5:]
            _detail9 = _df9[
                (_df9["leaderboard_name"] == _comp_detail9_real) &
                _df9["gw_int"].isin(_last5_detail9) &
                _df9["score_threshold"].notna()
            ]
            _gw_range9   = f"GW{int(_last5_detail9[0])}–GW{int(_last5_detail9[-1])}"
            _title_base9 = f"{_comp_detail9_disp} {_rar9_disp} — moy. {_gw_range9}"

        def _build_tiers(df_sub: pd.DataFrame) -> pd.DataFrame:
            if df_sub.empty:
                return pd.DataFrame()
            agg = dict(
                score_min=("score_threshold", "min"),
                score_median=("score_threshold", "median"),
                score_max=("score_threshold", "max"),
                reward_quantity=("reward_quantity", "median"),
                reward_usd_cents=("reward_usd_cents", "median"),
            )
            if _has_from_rank9:
                agg["from_rank"] = ("from_rank", "first")
            t = df_sub.groupby("tier_rank", as_index=False).agg(**agg).sort_values("tier_rank")
            if "from_rank" not in t.columns:
                t["from_rank"] = None
            return t

        _tiers_mon9 = _build_tiers(_detail9[_detail9["reward_type"] == "monetary"])
        _tiers_ess9 = _build_tiers(_detail9[_detail9["reward_type"] == "card_shard"])

        def _fig_paliers(tiers: pd.DataFrame, title: str, bar_color: str, reward_type: str = "card_shard") -> go.Figure:
            fig = go.Figure()
            for _, row in tiers.iterrows():
                tier  = int(row["tier_rank"])
                score = row["score_median"]
                x_label = (
                    f"Top {int(row['from_rank'])}"
                    if pd.notna(row.get("from_rank"))
                    else f"Palier {tier}"
                )
                if reward_type == "monetary" and pd.notna(row.get("reward_usd_cents")):
                    reward_text = f"${row['reward_usd_cents'] / 100:.0f}"
                elif pd.notna(row.get("reward_quantity")):
                    reward_text = f"{int(row['reward_quantity'])}"
                else:
                    reward_text = ""
                err_y = dict(
                    type="data", symmetric=False,
                    array=[row["score_max"] - score],
                    arrayminus=[score - row["score_min"]],
                    visible=True, color=bar_color,
                ) if (row["score_max"] - row["score_min"]) > 0.5 else None
                fig.add_trace(go.Bar(
                    x=[x_label], y=[score],
                    error_y=err_y,
                    marker_color=bar_color,
                    text=[reward_text],
                    textposition="inside",
                    insidetextanchor="middle",
                    textangle=0,
                    textfont=dict(color="white", size=13),
                    showlegend=False,
                    hovertemplate=f"Score seuil : %{{y:.1f}}<br>Récompense : {reward_text}<extra></extra>",
                ))
            y_max = float(tiers["score_max"].max()) if not tiers.empty else 300
            fig.update_layout(
                title=title,
                yaxis=dict(title="Score requis", range=[0, y_max * 1.18]),
                xaxis=dict(title="Classement"),
                height=360,
                bargap=0.35,
                margin=dict(t=50, b=40),
            )
            return fig

        _fcols9 = st.columns(2)
        with _fcols9[0]:
            if not _tiers_mon9.empty:
                st.plotly_chart(
                    _fig_paliers(_tiers_mon9, f"Récompenses en Cash — {_title_base9}", "#22c55e", reward_type="monetary"),
                    use_container_width=True,
                )
            else:
                st.caption("Pas de récompenses monétaires pour cette compétition.")
        with _fcols9[1]:
            if not _tiers_ess9.empty:
                st.plotly_chart(
                    _fig_paliers(_tiers_ess9, f"Essences — {_title_base9}", "#a78bfa"),
                    use_container_width=True,
                )
            else:
                st.caption("Pas de récompenses en essences pour cette compétition.")

    # ── Section 3 : tableau récapitulatif ────────────────────────────────────
    st.divider()
    st.subheader("Récapitulatif des seuils")

    _gws_recap9 = (_gws_sorted9[:-1] if len(_gws_sorted9) > 1 else _gws_sorted9)[-5:]
    _recap_per_gw9 = (
        _arena9[
            (_arena9["gw_int"].isin(_gws_recap9)) &
            (_arena9["rarity_type"] == _rar9) &
            _arena9["score_threshold"].notna()
        ]
        .groupby(["gw_int", "leaderboard_name"], as_index=False)
        .agg(
            seuil_entree=("score_threshold", "min"),
            seuil_top=("score_threshold", "max"),
            nb_divisions=("leaderboard_slug", "nunique"),
        )
    )
    _recap9 = (
        _recap_per_gw9
        .groupby("leaderboard_name", as_index=False)
        .agg(
            seuil_entree=("seuil_entree", "mean"),
            seuil_top=("seuil_top", "mean"),
            nb_divisions=("nb_divisions", "mean"),
        )
        .sort_values("seuil_entree")
    )
    _recap9.columns = ["Compétition", "Seuil entrée", "Seuil top", "Nb divisions"]
    _gw_range_recap9 = (
        f"GW{int(_gws_recap9[0])}–GW{int(_gws_recap9[-1])}"
        if len(_gws_recap9) >= 2 else f"GW{int(_gws_recap9[0])}"
    ) if _gws_recap9 else "—"
    st.caption(f"Moy. {_gw_range_recap9} · rareté {_rar9_disp}")
    st.dataframe(
        _recap9.style.format({"Seuil entrée": "{:.1f}", "Seuil top": "{:.1f}"}),
        use_container_width=True, hide_index=True,
    )

    # ── Section 4 : Hot Streak référence ─────────────────────────────────────
    st.divider()
    st.subheader("Hot Streak — seuils de référence")
    st.caption("Seuils fixes (indépendants de la GW). Bonus essences = par équipe supplémentaire atteignant le seuil.")
    _hs_disp9 = _hs9[_hs9["rarity_type"] == _rar9][
        ["score_threshold", "reward_quantity", "bonus_shards"]
    ].rename(columns={
        "score_threshold": "Score cible",
        "reward_quantity": "Essences (1ère équipe)",
        "bonus_shards":    "Bonus / équipe supp.",
    })
    st.dataframe(
        _hs_disp9.style.format({"Score cible": "{:.0f}", "Essences (1ère équipe)": "{:.0f}", "Bonus / équipe supp.": "{:.0f}"}),
        use_container_width=True, hide_index=True,
    )

    # ── Section 5 : Comparaison de rentabilité ────────────────────────────────
    st.divider()
    st.subheader("Comparaison de rentabilité")

    _ESS_RATE9        = 3 / 1000
    _ARENA_ENTRY9     = {"Beginner": 100, "Elite": 800}
    _ARENA_ENTRY_DEF9 = 300
    _LINEUP_SIZE9     = {"Hitters": 5, "Sandlot": 5}   # autres : 7 joueurs par défaut
    _LINEUP_COMP9     = {"Hitters": "5 hitters", "Sandlot": "3 hitters + 2 SP"}

    # ── Paliers HS pour la rareté active ──────────────────────────────────────
    _hs_all9 = (
        _hs9[_hs9["rarity_type"] == _rar9]
        .sort_values("score_threshold")
        .reset_index(drop=True)
    )
    _hs_palier_labels9 = [
        f"Palier {i+1} ({int(r.score_threshold)} pts)"
        for i, r in enumerate(_hs_all9.itertuples(index=False))
    ]

    # ── Contrôles ─────────────────────────────────────────────────────────────
    _cmp_c1, _cmp_c2, _cmp_c3 = st.columns([4, 2, 2])
    with _cmp_c1:
        _score_cmp9 = st.slider(
            "Score cible (lineup 7 joueurs)", min_value=100, max_value=400, value=200, step=5, key="lb9_score_cmp"
        )
    with _cmp_c2:
        _hs_palier_sel9 = st.selectbox(
            "Palier HS actuel",
            options=list(range(len(_hs_palier_labels9))),
            format_func=lambda i: _hs_palier_labels9[i],
            key="lb9_hs_palier",
        )
    with _cmp_c3:
        _n_teams_hs9 = st.number_input(
            "Équipes Hot Streak", min_value=1, max_value=4, value=1, step=1, key="lb9_n_teams_hs"
        )

    _gw_mode_cmp9 = st.radio(
        "Référence GW", ["Dernière GW terminée", "Moyenne 5 dernières GW terminées"],
        horizontal=True, key="lb9_gw_mode_cmp",
    )
    _gws_excl_last9 = _gws_sorted9[:-1]  # exclut la GW en cours
    if _gw_mode_cmp9 == "Dernière GW terminée":
        _gws_cmp9      = [int(_gws_excl_last9[-1])] if len(_gws_excl_last9) >= 1 else []
        _gw_ref_lbl9   = f"GW{_gws_cmp9[0]}" if _gws_cmp9 else "—"
    else:
        _last5_cmp9    = _gws_excl_last9[-5:] if len(_gws_excl_last9) >= 5 else _gws_excl_last9
        _gws_cmp9      = [int(g) for g in _last5_cmp9]
        _gw_ref_lbl9   = f"moy. GW{_gws_cmp9[0]}–GW{_gws_cmp9[-1]}" if _gws_cmp9 else "—"

    st.caption(f"Hypothèse : 1 000 essences = 3 $ · Référence : {_gw_ref_lbl9}")

    def _best_tier_reached(df_ref, score):
        hits = df_ref[df_ref["score_threshold"] <= score]
        return hits.sort_values("score_threshold", ascending=False).iloc[0] if not hits.empty else None

    # ── Données de référence : toutes compétitions × types de récompenses ─────
    _ref_base9 = _arena9[
        (_arena9["rarity_type"] == _rar9) &
        _arena9["gw_int"].isin(_gws_cmp9) &
        _arena9["score_threshold"].notna()
    ]
    _is_arena_map9 = _ref_base9.groupby("leaderboard_name")["is_arena"].first().to_dict()

    _comp_ref9 = (
        _ref_base9
        .groupby(["leaderboard_name", "reward_type", "tier_rank"], as_index=False)
        .agg(
            score_threshold=("score_threshold",  "median"),
            reward_quantity=("reward_quantity",   "median"),
            reward_usd_cents=("reward_usd_cents", "median"),
        )
    )

    # ── Construction du tableau ────────────────────────────────────────────────
    _cmp_rows9 = []
    _comp_order9 = sorted(_comp_ref9["leaderboard_name"].unique())
    for _cname9 in _comp_order9:
        _is_arena_c9  = bool(_is_arena_map9.get(_cname9, False))
        _entry9_cost  = _ARENA_ENTRY9.get(_cname9, _ARENA_ENTRY_DEF9) if _is_arena_c9 else 0
        _prefix9      = "ARENA — " if _is_arena_c9 else ""
        _n_players9   = _LINEUP_SIZE9.get(_cname9, 7)
        _fmt_lbl9     = _LINEUP_COMP9.get(_cname9, f"{_n_players9} joueurs")

        _adj9 = 7 / _n_players9  # facteur de normalisation vers équivalent 7 joueurs

        for _rtype9 in ["monetary", "card_shard"]:
            _sub9 = _comp_ref9[
                (_comp_ref9["leaderboard_name"] == _cname9) &
                (_comp_ref9["reward_type"] == _rtype9)
            ].copy()
            if _sub9.empty:
                continue

            # Normalise les seuils vers l'équivalent 7 joueurs avant comparaison
            _sub9["score_threshold"] = _sub9["score_threshold"] * _adj9
            _best9 = _best_tier_reached(_sub9, _score_cmp9)

            if _rtype9 == "monetary":
                _lbl9 = f"{_prefix9}{_cname9} (cash)"
                if _best9 is not None:
                    _val9   = float(_best9["reward_usd_cents"]) / 100
                    _rew9   = f"${_val9:.2f}"
                    _thr_adj9  = _best9["score_threshold"]
                    _thr_real9 = _thr_adj9 / _adj9
                    _seuil9 = (
                        f"{_thr_adj9:.0f} pts ({_thr_real9:.0f} réel)"
                        if _n_players9 != 7
                        else f"{_thr_adj9:.0f} pts"
                    )
                else:
                    _val9   = 0.0
                    _rew9   = "$0"
                    _seuil9 = "non atteint"
            else:
                _lbl9 = f"{_prefix9}{_cname9} (ess.)"
                if _best9 is not None:
                    _ess9      = float(_best9["reward_quantity"])
                    _net9      = _ess9 - _entry9_cost
                    _val9      = _net9 * _ESS_RATE9
                    _thr_adj9  = _best9["score_threshold"]
                    _thr_real9 = _thr_adj9 / _adj9
                    _seuil9 = (
                        f"{_thr_adj9:.0f} pts ({_thr_real9:.0f} réel)"
                        if _n_players9 != 7
                        else f"{_thr_adj9:.0f} pts"
                    )
                    _rew9   = (
                        f"{int(_ess9)} − {_entry9_cost} = {int(_net9)} ess. → ${_val9:.2f}"
                        if _entry9_cost > 0
                        else f"{int(_ess9)} ess. → ${_val9:.2f}"
                    )
                else:
                    _net9   = -_entry9_cost
                    _val9   = _net9 * _ESS_RATE9
                    _seuil9 = "non atteint"
                    _rew9   = (
                        f"0 − {_entry9_cost} = {int(_net9)} ess. → ${_val9:.2f}"
                        if _entry9_cost > 0
                        else "0 ess. → $0"
                    )

            _cmp_rows9.append({
                "Compétition":      _lbl9,
                "Format":           _fmt_lbl9,
                "Score nécessaire": _seuil9,
                "Récompense":       _rew9,
                "Valeur ($)":       _val9,
            })

    # ── Hot Streak ────────────────────────────────────────────────────────────
    _hsr_sel9    = _hs_all9.iloc[_hs_palier_sel9]
    _hs_thr9     = float(_hsr_sel9["score_threshold"])
    _hs_rew9     = float(_hsr_sel9["reward_quantity"])
    _hs_bon9     = float(_hsr_sel9.get("bonus_shards", 0) or 0)
    _hs_label9   = _hs_palier_labels9[_hs_palier_sel9]

    if _score_cmp9 >= _hs_thr9:
        _hs_total9   = _hs_rew9 + (_n_teams_hs9 - 1) * _hs_bon9
        _hs_val9     = _hs_total9 * _ESS_RATE9
        _hs_rew_str9 = (
            f"{int(_hs_rew9)} ess. → ${_hs_val9:.2f}" if _n_teams_hs9 == 1
            else f"{int(_hs_rew9)} + {_n_teams_hs9-1}×{int(_hs_bon9)} = {int(_hs_total9)} ess. → ${_hs_val9:.2f}"
        )
        _hs_seuil9   = f"{int(_hs_thr9)} pts ✓"
        _hs_next9    = (_hs_palier_labels9[_hs_palier_sel9 + 1]
                        if _hs_palier_sel9 + 1 < len(_hs_palier_labels9)
                        else "Streak complète !")
    else:
        _hs_val9     = 0.0
        _hs_rew_str9 = "$0 + reset palier 1"
        _hs_seuil9   = f"{int(_hs_thr9)} pts ✗"
        _hs_next9    = "—"

    _cmp_rows9.append({
        "Compétition":      f"Hot Streak {_hs_label9}",
        "Format":           "7 joueurs",
        "Score nécessaire": _hs_seuil9,
        "Récompense":       _hs_rew_str9,
        "Valeur ($)":       _hs_val9,
    })

    # ── Affichage ─────────────────────────────────────────────────────────────
    _cmp_df9   = pd.DataFrame(_cmp_rows9).sort_values("Valeur ($)", ascending=False).reset_index(drop=True)
    _best_val9 = float(_cmp_df9["Valeur ($)"].max())

    def _hl_best9(row):
        bg = "background-color: rgba(34,197,94,0.20)" if row["Valeur ($)"] == _best_val9 and _best_val9 > 0 else ""
        return [bg] * len(row)

    _display_cols9 = ["Compétition", "Format", "Score nécessaire", "Récompense", "Valeur ($)"]
    st.dataframe(
        _cmp_df9[_display_cols9].style.apply(_hl_best9, axis=1).format({"Valeur ($)": "${:.2f}"}),
        use_container_width=True, hide_index=True,
    )

    if _best_val9 > 0:
        _winner9 = _cmp_df9.iloc[0]
        st.success(f"**Meilleur choix à {_score_cmp9} pts :** {_winner9['Compétition']} — {_winner9['Récompense']}")

    if _score_cmp9 >= _hs_thr9 and _hs_next9 not in ("—", "Streak complète !"):
        st.info(f"Hot Streak réussie → prochain palier : **{_hs_next9}**")

    st.caption(
        "Arena : coût d'entrée déduit (Beginner 100 ess., Elite 800 ess., autres 300 ess.). "
        "Hitters / Sandlot : seuils multipliés par 7/5 pour comparaison sur base 7 joueurs (valeur réelle entre parenthèses). "
        "Champion / Challenger (cash) et (ess.) sont mutuellement exclusifs selon le classement final. "
        "Hot Streak : tout ou rien — échec = $0 et retour au palier 1. "
        "Multi-équipes HS : toutes les équipes supposées au même score."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 8 — MES LINEUPS SAUVEGARDÉS
# ═══════════════════════════════════════════════════════════════════════════════

with tab8:
    _saved = load_saved_lineups()
    _saved_mgr = [l for l in _saved if l.get("manager") == sel_manager]

    if not _saved_mgr:
        st.info("Aucun lineup sauvegardé. Crée une équipe dans l'onglet 🏗️ Équipe puis clique sur 💾 Sauvegarder.")
    else:
        _gs_all = load_game_scores_all()

        # ── Filtres + suppression globale ────────────────────────────────────
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
            # Scores réels disponibles pour cette GW ?
            _gs_gw10 = (
                _gs_all[_gs_all["gw_int"] == _sel_gw10]
                .groupby("player_slug", as_index=False)["score"]
                .sum()
                .set_index("player_slug")["score"]
                .to_dict()
                if not _gs_all.empty else {}
            )
            _has_real = bool(_gs_gw10)

            # Photo map (galerie uniquement — null pour les autres)
            _pic_map10 = (
                df_prices.drop_duplicates("player_slug")
                .set_index("player_slug")["picture_url"]
                .to_dict()
            )

            def _card10(pdata, real_sc, border_color="#334155"):
                """HTML card pour un joueur dans la grille lineup."""
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
                # Prénom initial + nom de famille si trop long
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
                # Compat ancien format (suggested_slots) + nouveau format
                _sug_auto10   = (_l10.get("suggested_slots_auto")
                                 or _l10.get("suggested_slots") or {})
                _sug_sorare10 = _l10.get("suggested_slots_sorare") or {}
                _title      = (
                    f"{_l10['mode']} · {_l10['rarity']} · GW{_l10['gw_int']} "
                    f"· {_src_label} — sauvegardé le {_ldate}"
                )

                with st.expander(_title, expanded=True):
                    # ── Tableau principal ─────────────────────────────────────
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

                    # Métriques résumé
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

                    # ── Grille visuelle ───────────────────────────────────────
                    _slot_keys10 = list(_l10["slots"].keys())
                    _nc10 = len(_slot_keys10)
                    _col_ratios10 = [0.65] + [1] * _nc10

                    # Ligne labels slots
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

                    # Pré-calcul projections totales
                    _proj_my   = sum(float(v.get("proj_score_eff") or 0) for v in _l10["slots"].values() if v)
                    _proj_ml   = sum(float(v.get("proj_score_eff") or 0) for v in _sug_auto10.values()   if v) if _sug_auto10   else None
                    _proj_gw   = sum(float(v.get("proj_score_eff") or 0) for v in _sug_sorare10.values() if v) if _sug_sorare10 else None

                    # Ligne : Mon équipe
                    _row_a = st.columns(_col_ratios10)
                    _row_a[0].markdown(_row_label("Mon équipe", "#94a3b8", _proj_my), unsafe_allow_html=True)
                    for _ci, _sk in enumerate(_slot_keys10):
                        _pd10 = _l10["slots"].get(_sk)
                        _rl10 = _gs_gw10.get(_pd10.get("player_slug", "")) if _pd10 else None
                        _sug_card10 = (_sug_auto10.get(_sk) or {}).get("card_name") if _sug_auto10 else None
                        _border10 = "#334155" if (not _sug_card10 or not _pd10 or _pd10.get("card_name") == _sug_card10) else "#f59e0b"
                        _row_a[_ci + 1].markdown(_card10(_pd10, _rl10, _border10), unsafe_allow_html=True)

                    # Ligne : Suggestion ML
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

                    # Ligne : Suggestion GW+
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

                    # ── Bouton supprimer ──────────────────────────────────────
                    if st.button("🗑️ Supprimer ce lineup", key=f"del10_{_lid}"):
                        _delete_lineup(_lid)
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 9 — MARCHÉ (scores ML + prix pour tous les joueurs)
# ═══════════════════════════════════════════════════════════════════════════════

with tab9:
    if df_ml.empty:
        st.info("Aucune prédiction ML disponible. Lancez `update_data.py` pour générer les données.")
    else:
        try:
            _df_p11, _gw11 = load_upcoming_pitchers()
        except Exception:
            _df_p11, _gw11 = pd.DataFrame(), 0

        # Construire le dataframe combiné : scores ML + prix marché
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

        # Moyenne des X derniers matchs par joueur (depuis game_scores)
        _gs_hist11 = load_game_scores_all()
        # seal_ratio sera calculé après le filtre rareté (dépend de _rar11)

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

        # ── Filtres ───────────────────────────────────────────────────────────
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

        # Moyenne des X derniers matchs par joueur
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

        # Valeur de sealing depuis all_players_market (colonne sealable_<rarity>, tous les joueurs)
        _seal_col11 = {"Limited": "sealable_limited", "Rare": "sealable_rare",
                       "Super Rare": "sealable_sr", "Unique": "sealable_unique"}[_rar11]
        _ml11["seal_value"] = pd.to_numeric(
            _ml11[_seal_col11] if _seal_col11 in _ml11.columns else float("nan"),
            errors="coerce",
        )

        # Seal ratio : valeur de sealing / min(prix IS, Classic)
        _p_is11  = f"price_{_rar11_key}_is"
        _p_oos11 = f"price_{_rar11_key}_oos"
        _min_p11 = _ml11[[c for c in [_p_is11, _p_oos11] if c in _ml11.columns]].min(axis=1)
        _ml11["seal_ratio"] = (
            (_ml11["seal_value"] / _min_p11).replace([float("inf"), float("-inf")], None).round(3)
        )

        # Ratios pts/€ (moyenne X derniers matchs / prix) — calculé pour toutes les raretés
        _RARS11 = [("Limited", "limited"), ("Rare", "rare"), ("SR", "sr"), ("Unique", "unique")]
        for _rl, _rk in _RARS11:
            _pc = f"price_{_rk}_{_sfx11}"
            _rc = f"ratio_{_rk}"
            if _pc in _ml11.columns:
                _ml11[_rc] = (_ml11["avg_last_x"] / _ml11[_pc]).replace(
                    [float("inf"), float("-inf")], None
                ).round(3)

        # N'afficher que la rareté sélectionnée
        _RAR11_DISP = [(_rar11, _rar11_key)]

        _sort_opts11 = [f"pts/€ {_rar11}", f"Prix {_rar11}", "Seal ratio"]
        with _c11f:
            _sort11 = st.selectbox("Trier par", _sort_opts11, key="mkt11_sort")

        _sort_map11 = {
            f"pts/€ {_rar11}": f"ratio_{_rar11_key}",
            f"Prix {_rar11}":  f"price_{_rar11_key}_{_sfx11}",
            "Seal ratio":      "seal_ratio",
        }

        # Filtres
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

        # ── Affichage dataframe ───────────────────────────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 10 — DOCUMENTATION
# ═══════════════════════════════════════════════════════════════════════════════

with tab10:
    st.title("📖 Documentation du dashboard Sorare MLB")
    st.caption("Référence complète : architecture, onglets, méthodes de prédiction et règles Sorare.")

    # ── Vue d'ensemble ────────────────────────────────────────────────────────
    with st.expander("🏗️ Architecture générale", expanded=True):
        st.markdown("""
Le dashboard est alimenté par un pipeline en trois couches :

| Couche | Rôle |
|---|---|
| **API Sorare** | Galerie, scores, prix, calendrier, pitchers annoncés |
| **Base PostgreSQL** (`mlb.*`) | Stockage des données brutes et enrichies |
| **Fichiers Parquet** (`data/`) | Cache rapide pour Streamlit (rechargé par `update_data.py`) |

**Scripts principaux :**

- `update_data.py` — Rafraîchit tout (galerie, scores, prix, stades, météo, park factors) puis appelle `ml_predict_gw.py`.
- `ml_predict_gw.py` — Calcule les prédictions pour la prochaine GW Classic et les exporte dans `data/ml_predictions.parquet`.
- `fetch_weather.py` — Récupère la météo par match via Open-Meteo (gratuit, sans clé API).
- `fetch_park_factors.py` — Récupère les Park Factors MLB via `pybaseball`.

**Sélecteurs globaux (barre latérale) :**

- **Manager** — filtre toutes les vues sur la galerie du manager sélectionné.
- **Statistique** — choisit la stat affichée dans les classements (score Sorare, HR, RBI…).
- **Fenêtre** — nombre de matchs sur lesquels calculer les moyennes historiques (5, 10 ou 20 matchs).
""")

    # ── Description des onglets ───────────────────────────────────────────────
    with st.expander("📑 Description des onglets"):
        st.markdown("""
### 🏆 Défis journaliers (Tab 1)
Classement des joueurs de la galerie qui jouent **aujourd'hui**, triés par la statistique sélectionnée.
Suggestion d'alignement : top 3 joueurs. Cliquer sur une ligne affiche l'historique du joueur.

### 📅 Calendrier (Tab 2)
Vue par jour de tous les matchs à venir pour la galerie. Chaque match montre les joueurs du manager,
leur rareté, leur statut IS/OOS, le pourcentage de matches joués et la moyenne.

### 💰 Mes cartes (Tab 3)
Liste de toutes les cartes du manager avec stats agrégées, prix de marché (IS et OOS), et valeur totale du portefeuille.
Filtres : rareté, position, statut IS, blessures.

### 🔍 Base de données (Tab 4)
Exploration brute des scores historiques par joueur. Recherche par nom, filtre par fenêtre temporelle.
Affiche les détails stat par stat (HR, RBI, K, etc.).

### ⚾ Pitchers GW (Tab 5)
Pour chaque match de la prochaine GW, affiche le pitcher annoncé et ses statistiques récentes.
Permet de voir l'adversaire de chaque joueur de la galerie.

### ⚔️ Vis-à-vis (Tab 6)
Historique frappeur vs pitcher spécifique. Utile pour estimer la difficulté d'un matchup.
Agrège les scores Sorare de chaque hitter de la galerie contre chaque pitcher annoncé.

### 📈 Projections GW (Tab 7)
Projections de score pour la prochaine GW Classic. Deux indicateurs par joueur :
- **EWMA** : prédiction EWMA × nb matchs dans la GW, avec intervalle de confiance 80%.
- **CTX** : prédiction contextuelle intégrant les 6 facteurs d'ajustement (voir section Méthode).
Les chips de couleur montrent chaque facteur qui s'écarte de la neutralité (>0.8%).

### 🏗️ Équipe (Tab 8)
Constructeur d'équipe en deux sous-onglets :
- **Compétitions** : Champions, Hot Streak, Challenger — suggère automatiquement les meilleures équipes pour chaque slot en maximisant le score effectif (score × card_power).
- **Arena** : 9 types d'arenas (Standard, Elite, AL/NL, OG, Legacy, Sandlot…).

### 🎖️ Compétitions (Tab 9)
Leaderboards des compétitions actives. Compare la rentabilité (gains / valeur investie) par rareté et mode.

### 📋 Mes lineups (Tab 10)
Lineups sauvegardés depuis l'onglet Équipe. Compare chaque équipe sauvegardée
contre les deux suggestions automatiques (Auto ML et Sorare GW+).

### 🛒 Marché (Tab 11)
Vue globale sur tous les joueurs MLB : prédiction ML, prix de marché par rareté (IS/OOS),
ratio score/prix pour identifier les joueurs sous-cotés.

""")

    # ── Méthode de prédiction ─────────────────────────────────────────────────
    with st.expander("🧮 Méthode de prédiction EWMA"):
        st.markdown("""
### Principe

Le modèle est basé sur une **moyenne mobile exponentiellement pondérée (EWMA)** par joueur,
combinée avec le **théorème central limite (CLT)** pour construire des intervalles de confiance.

Un modèle LightGBM global avait été testé et abandonné : il prédit la médiane MLB (~3 pts)
alors que les joueurs d'une galerie compétitive ont une moyenne de ~7 pts (biais de sélection fort).
L'EWMA est optimal quand le signal est faible, le processus non-stationnaire (forme, blessures,
changement d'équipe) et les données peu nombreuses.

### Calcul

```
Poids EWMA :  w_i = 0.5 ^ ((N-1-i) / 25)    [demi-vie = 25 matchs]
mu           = somme(w_i × score_i) / somme(w_i)
sigma        = écart-type empirique sur les 50 derniers matchs
IC 80%/match = [max(0, mu − 1.282σ), mu + 1.282σ]
IC 80%/GW    = [max(0, N×mu − 1.282σ√N), N×mu + 1.282σ√N]
```

**Seuil minimum** : 5 matchs historiques requis. En dessous, fallback sur la moyenne du groupe
(hitters ou pitchers) calculée sur l'ensemble de la galerie.

### Colonnes du parquet `data/ml_predictions.parquet`

| Colonne | Description |
|---|---|
| `pred_median` | EWMA par match (à multiplier par `n_games_gw` pour le total GW) |
| `pred_lo / pred_hi` | Borne inférieure / supérieure IC 80% par match |
| `n_games_gw` | Nb matchs de l'équipe dans la GW (SPs capés à 1) |
| `pred_contextual` | EWMA × tous les facteurs d'ajustement (par match) |
| `pred_A / B / C` | Variantes avec ajustement platoon (par match) |
""")

    # ── Facteurs d'ajustement ─────────────────────────────────────────────────
    with st.expander("⚙️ Facteurs d'ajustement (pred_contextual)"):
        st.markdown("""
La prédiction contextuelle intègre 6 facteurs multiplicatifs appliqués sur la base EWMA :

```
pred_contextual = mu × platoon_C × park_factor × weather_factor
                     × home_away_factor × opp_quality_factor
                     × day_night_factor × rest_factor
```

### Platoon (platoon_C — Option C hybride)

Ajuste selon la combinaison main du frappeur × main du pitcher annoncé.

- **Option A** — splits personnels du joueur (≥15 matchs vs cette main requis)
- **Option B** — facteurs league-average MLB :

| Frappeur \\ Pitcher | Gaucher (L) | Droitier (R) |
|---|---|---|
| **Gaucher (L)** | ×0.94 | ×1.03 |
| **Droitier (R)** | ×1.05 | ×0.97 |
| **Switch (S)** | ×1.00 | ×1.00 |

- **Option C** (retenue) — hybride : splits personnels si ≥15 matchs, mélange progressif entre 5 et 14, league-average si <5.

*Pitchers : aucun ajustement platoon (ils affrontent des lineups mixtes).*

### Park factor (🏟)

Corrige l'environnement offensif du stade visité.

- **Frappeur** : `0.40×R + 0.35×HR + 0.25×H` (selon main du frappeur si disponible)
- **Lanceur** : inverse de l'environnement : `1 / (0.60×R + 0.40×HR)`
- Source : table `mlb.park_factors` (via `pybaseball`, saison en cours)
- 100 = neutre, 110 = +10% de runs dans ce stade

### Météo (🌬)

Données horaires via Open-Meteo (gratuit), appariées à l'heure du match.

**Vent :** calculé par rapport à l'orientation `home → centre field` (colonne `cf_orientation_deg` des stades).

| Direction | Effet frappeur | Effet lanceur |
|---|---|---|
| `out` (de dos, pousse vers CF) | +max 6% à ≥20 mph | −max 6% |
| `in` (de face, venant de CF) | −max 6% à ≥20 mph | +max 6% |
| `cross_L / cross_R` | ×1.0 | ×1.0 |
| `calm` (<5 mph) | ×1.0 | ×1.0 |
| `dome` (stade fermé) | ×1.0 | ×1.0 |

**Température :** ±1% par 10°F d'écart depuis 72°F (capé ±5%).
**Pluie :** −5% frappeurs, +3% lanceurs.

### Domicile / Extérieur (🏠)

- Domicile : ×1.02 (+2%)
- Extérieur : ×0.98 (−2%)

Si un joueur a plusieurs matchs dans la GW, le facteur est la moyenne pondérée.

### Qualité de l'adversaire (⚔ — frappeurs uniquement)

Ajuste selon la qualité EWMA du pitcher annoncé par rapport à la moyenne de la ligue.

```
opp_quality_factor = max(0.80, min(1.20, 1.0 − 0.15 × (ewma_pitcher / moy_ligue − 1.0)))
```

Interprétation : face à un lanceur 20% au-dessus de la moyenne, le facteur est 0.97 (−3%).

### Jour / Nuit (☀)

- Match de jour (heure UTC < 20h) : frappeurs −3%, lanceurs +3% (les frappeurs performent légèrement moins le jour).
- Plusieurs matchs GW : facteur proportionnel à la part de matchs de jour.

### Repos (💤)

| Jours de repos avant la GW | Facteur |
|---|---|
| 0 jour | ×0.98 |
| 1–2 jours | ×1.00 (neutre) |
| ≥3 jours | ×1.02 |
""")

    # ── Règles Sorare MLB ─────────────────────────────────────────────────────
    with st.expander("📋 Règles Sorare MLB"):
        st.markdown("""
### Structure d'une équipe (7 slots)

| Slot | Positions acceptées |
|---|---|
| SP | Starting Pitcher uniquement |
| RP | Relief Pitcher uniquement |
| CI | Corner Infield (1B / 3B) |
| MI | Middle Infield (2B / SS) |
| OF | Outfield (LF / CF / RF) |
| Flex | CI, MI ou OF |
| Libre | CI, MI ou OF |

### Contraintes

- **Max 6 cartes d'un même club** par équipe (4 pour les arenas 5 joueurs : Sandlot).
- **In Season (IS)** : carte émise dans la saison MLB en cours.
- **Out of Season (OOS)** : carte d'une saison passée.

### Modes de compétition

| Mode | Contrainte IS |
|---|---|
| Champions | ≥6 cartes IS obligatoires |
| Hot Streak | ≥6 cartes IS obligatoires |
| Challenger | Aucune contrainte IS |

### Card Power

Bonus multiplicatif sur le score de la carte : entre ×1.01 et ×1.20.
Le dashboard l'intègre dans le **score effectif** : `score_projeté × card_power`.

### Score effectif (affiché dans l'onglet Équipe)

```
score_effectif = score_projeté × card_power
```

L'algorithme de suggestion maximise la somme des scores effectifs tout en respectant
les contraintes de slots, de clubs (max 6) et de cartes IS.
""")

    # ── Glossaire ─────────────────────────────────────────────────────────────
    with st.expander("📚 Glossaire"):
        st.markdown("""
| Terme | Définition |
|---|---|
| **EWMA** | Exponentially Weighted Moving Average — moyenne pondérée donnant plus de poids aux matchs récents |
| **demi-vie** | Nombre de matchs au bout duquel un score pèse moitié moins (réglé à 25) |
| **IC 80%** | Intervalle de confiance à 80% — la vraie valeur a 80% de chances de se trouver dans cet intervalle |
| **pred_median** | Prédiction EWMA par match (sans ajustements contextuels) |
| **pred_contextual** | Prédiction par match avec tous les facteurs d'ajustement |
| **platoon** | Avantage / désavantage selon la combinaison main frappeur × main pitcher |
| **park factor** | Mesure de l'influence du stade sur les stats offensives (100 = neutre) |
| **wind_label** | Direction du vent par rapport à l'axe home plate → centre field |
| **IS** | In Season — carte émise dans la saison MLB en cours |
| **OOS** | Out of Season — carte d'une saison précédente |
| **card_power** | Bonus multiplicatif sur le score de la carte (1.01 à 1.20) |
| **score effectif** | score_projeté × card_power |
| **GW** | Game Week — semaine de jeu Sorare (fixe pour Classic, variable pour Daily) |
| **CI** | Corner Infield — joueurs de 1ère et 3ème base |
| **MI** | Middle Infield — joueurs de 2ème base et shortstop |
| **SP** | Starting Pitcher |
| **RP** | Relief Pitcher |
| **OF** | Outfield |
""")

    # ── Pipeline de données ───────────────────────────────────────────────────
    with st.expander("🔄 Pipeline de données"):
        st.markdown("""
### Rafraîchissement des données

Lance `python update_data.py` pour tout mettre à jour. Le script :

1. **Galerie** — récupère les cartes et joueurs de chaque manager via l'API Sorare.
2. **Scores** — incrémental : récupère les scores depuis `MAX(game_date) − 1 jour`.
3. **Matchs & GW** — calendrier MLB, pitchers annoncés, résultats.
4. **Prix** — prix de marché par (joueur, rareté, IS/OOS).
5. **Stades** — données statiques (coordonnées, orientation CF, dome, dimensions).
6. **Park factors** — via `pybaseball` pour la saison en cours.
7. **Météo** — Open-Meteo : 7 jours passés + 16 jours futurs par stade.
8. **Prédictions** — appel à `ml_predict_gw.py` pour générer `data/ml_predictions.parquet`.

### Fréquence recommandée

- **Avant chaque GW** : une fois après l'annonce des pitchers probables (J−1 ou J matin).
- En mode `--full` : pour un recalcul complet de l'historique (rare, ~20 min).

### Tables PostgreSQL clés

| Table | Contenu |
|---|---|
| `mlb.games` | Matchs MLB avec dates, équipes, pitchers probables/gagnants |
| `mlb.game_scores` | Score Sorare par (joueur, match, position) |
| `mlb.game_score_details` | Détail stat par stat (HR, K, RBI…) |
| `mlb.players` | Référentiel joueurs (équipe, main, positions) |
| `mlb.gallery_players` | Cartes en galerie par manager |
| `mlb.stadiums` | Stades (coordonnées, is_dome, cf_orientation_deg) |
| `mlb.park_factors` | Park factors par (équipe, saison, stat) |
| `mlb.game_weather` | Météo par match (température, vent, pluie, is_forecast) |
""")

# (tab11 Builder visuel archivé dans codes_image/builder_tab_backup.py)
if False:
    _BV_SLOTS    = ["SP", "RP", "CI", "MI", "OF", "Flex", "Libre"]
    _BV_SLOT_POS = {
        "SP":    ["SP"],
        "RP":    ["RP"],
        "CI":    ["CI"],
        "MI":    ["MI"],
        "OF":    ["OF"],
        "Flex":  ["CI", "MI", "OF"],
        "Libre": ["CI", "MI", "OF"],
    }
    _BV_SLOT_LBL = {
        "SP": "SP", "RP": "RP", "CI": "CI", "MI": "MI", "OF": "OF",
        "Flex": "FLX", "Libre": "H",
    }

    # ── Controls ──────────────────────────────────────────────────────────────
    _bvc1, _bvc2 = st.columns([3, 3])
    with _bvc1:
        _bv_rar = st.radio(
            "Rareté", ["Limited", "Rare", "Super Rare", "Unique"],
            horizontal=True, key="bv_rar",
        )
    with _bvc2:
        _bv_src = st.radio(
            "Score", ["Auto (ML→Hist.)", "Sorare GW+"],
            horizontal=True, key="bv_src",
        )

    # ── Session state ─────────────────────────────────────────────────────────
    _bv_lk = f"bv_lineup_{_bv_rar}"
    if _bv_lk not in st.session_state:
        st.session_state[_bv_lk] = {s: None for s in _BV_SLOTS}
    if "bv_active" not in st.session_state:
        st.session_state["bv_active"] = "SP"
    _bv_lineup = st.session_state[_bv_lk]
    _bv_active = st.session_state["bv_active"]

    # ── Données joueurs ───────────────────────────────────────────────────────
    _df_bv = (
        df_prices[
            (df_prices["gallery_manager"] == sel_manager) &
            (df_prices["card_display_rarity"].str.lower() == _bv_rar.lower()) &
            ~df_prices["player_slug"].isin(_injured_slugs)
        ]
        .drop_duplicates("card_name")
        .copy()
    )
    _df_bv["position_agg"]   = _df_bv["card_display_position"].map(POSITION_AGG)
    _df_bv["position_exact"] = _df_bv["card_display_position"].map(POSITION_EXACT)
    _df_bv["is_eligible"]    = _df_bv["in_season_eligible"] == True

    _bv_all_slugs    = tuple(_df_bv["player_slug"].unique())
    _bv_hitter_slugs = tuple(
        _df_bv[~_df_bv["position_agg"].isin(["SP", "RP"])]["player_slug"].unique()
    )
    _avg_bv  = load_player_avg_scores(_bv_all_slugs, FENETRE_OPTIONS[fenetre]) if _bv_all_slugs else pd.DataFrame()
    _smap_bv = _avg_bv.set_index("player_slug")["avg_score"].to_dict() if not _avg_bv.empty else {}

    try:
        _df_pbv, _gw_bv = load_upcoming_pitchers()
    except Exception:
        _df_pbv, _gw_bv = pd.DataFrame(), 0

    _tsched_bv: dict = {}
    if not _df_pbv.empty:
        for _, _gbv in _df_pbv.iterrows():
            if _gbv["home_team_slug"]:
                _tsched_bv.setdefault(_gbv["home_team_slug"], []).append(
                    {"pitcher_slug": _gbv["away_pitcher_slug"] or None}
                )
            if _gbv["away_team_slug"]:
                _tsched_bv.setdefault(_gbv["away_team_slug"], []).append(
                    {"pitcher_slug": _gbv["home_pitcher_slug"] or None}
                )

    _all_pbv = tuple({
        s for col in ("home_pitcher_slug", "away_pitcher_slug")
        for s in _df_pbv[col].dropna()
    }) if not _df_pbv.empty else ()
    _df_mu_bv = (
        load_matchup_stats(_bv_hitter_slugs, _all_pbv)
        if (_bv_hitter_slugs and _all_pbv) else pd.DataFrame()
    )
    _mu_bv: dict = {}
    for _, _rmu in _df_mu_bv.iterrows():
        if pd.notna(_rmu["avg_sorare_score"]):
            _mu_bv[(_rmu["hitter_slug"], _rmu["pitcher_slug"])] = float(_rmu["avg_sorare_score"])

    def _bv_hist_score(slug, team, pos_agg):
        if pos_agg in ("SP", "RP"):
            return _smap_bv.get(slug, 0.0)
        games = _tsched_bv.get(team, [])
        total = 0.0
        for _gmv in games:
            ps = _gmv["pitcher_slug"]
            sc = (_mu_bv.get((slug, ps)) if ps else None) or _smap_bv.get(slug)
            if sc:
                total += sc
        return round(total, 1) if games else _smap_bv.get(slug, 0.0)

    _df_bv["proj_hist"] = _df_bv.apply(
        lambda r: _bv_hist_score(r["player_slug"], r.get("active_club_slug", ""), r["position_agg"]),
        axis=1,
    )

    if not df_ml.empty:
        _ml_bv_s = (
            df_ml[df_ml["gallery_manager"] == sel_manager]
            .drop_duplicates("player_slug")
            .set_index("player_slug")["pred_contextual"]
        )
        _tsched_bv_len = {t: len(g) for t, g in _tsched_bv.items()}

        def _bv_ml_score(slug, team, pos_agg):
            ml = _ml_bv_s.get(slug)
            if ml is None:
                return None
            if pos_agg in ("SP", "RP"):
                return round(float(ml), 1)
            nb = _tsched_bv_len.get(team, 1)
            return round(float(ml) * nb, 1)

        _df_bv["proj_ml"]    = _df_bv.apply(
            lambda r: _bv_ml_score(r["player_slug"], r.get("active_club_slug", ""), r["position_agg"]),
            axis=1,
        )
        _df_bv["proj_score"] = _df_bv["proj_ml"].combine_first(_df_bv["proj_hist"])
    else:
        _df_bv["proj_ml"]    = None
        _df_bv["proj_score"] = _df_bv["proj_hist"]

    _pow_bv  = pd.to_numeric(_df_bv["card_power"], errors="coerce").fillna(1.0)
    _sor_bv  = pd.to_numeric(
        _df_bv.get("next_gw_projected_score", pd.Series(dtype=float)), errors="coerce"
    )
    _base_bv = (
        _sor_bv.fillna(0.0)
        if _bv_src == "Sorare GW+"
        else pd.to_numeric(_df_bv["proj_score"], errors="coerce").fillna(0.0)
    )
    _df_bv["proj_eff"] = (_base_bv * _pow_bv).round(1)

    if _tsched_bv:
        _prob_sp_bv = {
            g["pitcher_slug"]
            for gs in _tsched_bv.values()
            for g in gs if g["pitcher_slug"]
        }
        _is_sp_bv = _df_bv["position_agg"] == "SP"
        _df_bv    = _df_bv[~_is_sp_bv | _df_bv["player_slug"].isin(_prob_sp_bv)].reset_index(drop=True)

    _cl_bv = _df_bv.set_index("card_name").to_dict("index")

    _bv_used_slugs = {
        _cl_bv.get(c, {}).get("player_slug")
        for s, c in _bv_lineup.items()
        if c and s != _bv_active
    }

    _bv_rc = RARITY_COLOR.get(_bv_rar.lower().replace(" ", "_"), "#888")
    try:
        _bv_rc_rgb = f"{int(_bv_rc[1:3],16)},{int(_bv_rc[3:5],16)},{int(_bv_rc[5:7],16)}"
    except Exception:
        _bv_rc_rgb = "136,136,136"

    # ── Sélecteur de slot actif (pleine largeur) ─────────────────────────────
    _bv_slot_labels_opts = [f"{_BV_SLOT_LBL[s]}" if _BV_SLOT_LBL[s] == s else f"{_BV_SLOT_LBL[s]} ({s})" for s in _BV_SLOTS]
    _bv_active_idx = _BV_SLOTS.index(_bv_active) if _bv_active in _BV_SLOTS else 0
    _bv_slot_sel = st.radio(
        "Slot à remplir",
        _bv_slot_labels_opts,
        index=_bv_active_idx,
        horizontal=True,
        key="bv_slot_radio",
        label_visibility="collapsed",
    )
    _bv_active_new = _BV_SLOTS[_bv_slot_labels_opts.index(_bv_slot_sel)]
    if _bv_active_new != _bv_active:
        st.session_state["bv_active"] = _bv_active_new
        st.rerun()
    _bv_active = _bv_active_new

    # ── Layout deux panneaux ──────────────────────────────────────────────────
    _left_bv, _right_bv = st.columns([4, 6], gap="medium")

    with _left_bv:

        def _slot_card_html(slot):
            card   = _bv_lineup.get(slot)
            lbl    = _BV_SLOT_LBL[slot]
            active = slot == _bv_active
            bdr    = _bv_rc if active else "rgba(255,255,255,0.15)"
            glow   = f"box-shadow:0 0 10px rgba({_bv_rc_rgb},0.6);" if active else ""
            bg_act = f"rgba({_bv_rc_rgb},0.12)"

            if card:
                r   = _cl_bv.get(card, {})
                img = r.get("picture_url", "")
                nm  = _slug_name_map.get(r.get("player_slug", ""), card)
                nm  = nm[:14] if len(nm) > 14 else nm
                sc  = float(r.get("proj_eff") or 0.0)
                isc = "#4CAF50" if r.get("is_eligible") else "#FF8C00"
                isl = "IS" if r.get("is_eligible") else "OOS"
                if img:
                    img_html = (
                        f'<img src="{img}" style="width:66px;height:84px;'
                        f'object-fit:cover;object-position:top center;'
                        f'border-radius:5px 5px 0 0;display:block;margin:0 auto">'
                    )
                else:
                    img_html = (
                        f'<div style="width:66px;height:84px;background:rgba(255,255,255,0.07);'
                        f'border-radius:5px 5px 0 0;display:flex;align-items:center;'
                        f'justify-content:center;font-size:10px;color:#888;margin:0 auto">{lbl}</div>'
                    )
                return (
                    f'<div style="width:78px;background:{bg_act};'
                    f'border:1.5px solid {bdr};{glow}border-radius:8px;overflow:hidden">'
                    f'{img_html}'
                    f'<div style="padding:3px 5px;text-align:center">'
                    f'<div style="font-size:7.5px;color:rgba(255,255,255,0.45);font-weight:600">{lbl}</div>'
                    f'<div style="font-size:8px;font-weight:700;color:#fff;white-space:nowrap;'
                    f'overflow:hidden;text-overflow:ellipsis">{nm}</div>'
                    f'<div style="font-size:10px;font-weight:700;color:#4CAF50">{sc:.0f}p</div>'
                    f'<div style="font-size:7px;color:{isc}">{isl}</div>'
                    f'</div></div>'
                )
            else:
                bg_empty = bg_act if active else "rgba(255,255,255,0.02)"
                return (
                    f'<div style="width:78px;height:118px;background:{bg_empty};'
                    f'border:1.5px dashed {bdr};{glow}border-radius:8px;'
                    f'display:flex;flex-direction:column;align-items:center;justify-content:center">'
                    f'<div style="font-size:13px;font-weight:700;'
                    f'color:{"rgba(255,255,255,0.7)" if active else "rgba(255,255,255,0.22)"}">{lbl}</div>'
                    f'<div style="font-size:7px;color:rgba(255,255,255,0.18);margin-top:3px">vide</div>'
                    f'</div>'
                )

        _shtml = {s: _slot_card_html(s) for s in _BV_SLOTS}
        _total_bv = sum(
            float(_cl_bv.get(c, {}).get("proj_eff") or 0)
            for c in _bv_lineup.values() if c
        )
        _n_filled_bv = sum(1 for c in _bv_lineup.values() if c)
        _n_is_bv     = sum(
            1 for c in _bv_lineup.values()
            if c and _cl_bv.get(c, {}).get("is_eligible")
        )

        _diamond_html = f"""
<div style="position:relative;width:100%;height:315px;
  background:linear-gradient(155deg,#080c16 0%,#0c1520 60%,#060e16 100%);
  border-radius:16px;border:1px solid rgba(255,255,255,0.07);overflow:hidden">
  <svg viewBox="0 0 300 280" style="position:absolute;top:0;left:0;width:100%;height:100%;opacity:0.2">
    <ellipse cx="150" cy="95" rx="138" ry="82" fill="#0d3015"/>
    <polygon points="150,35 225,115 150,195 75,115" fill="#2a1a08"/>
    <polygon points="150,195 162,212 150,224 138,212" fill="white" opacity="0.6"/>
    <rect x="144" y="29" width="12" height="12" fill="white" opacity="0.6" transform="rotate(45,150,35)"/>
    <rect x="219" y="109" width="12" height="12" fill="white" opacity="0.6" transform="rotate(45,225,115)"/>
    <rect x="69" y="109" width="12" height="12" fill="white" opacity="0.6" transform="rotate(45,75,115)"/>
    <circle cx="150" cy="115" r="11" fill="#3d2408" opacity="0.9"/>
    <rect x="146" y="112" width="8" height="3" fill="white" opacity="0.5"/>
    <line x1="150" y1="224" x2="5" y2="278" stroke="white" stroke-width="1.5" opacity="0.35"/>
    <line x1="150" y1="224" x2="295" y2="278" stroke="white" stroke-width="1.5" opacity="0.35"/>
    <path d="M 12,278 A 172,195 0 0 1 288,278" fill="none" stroke="#8B7355" stroke-width="7" opacity="0.4"/>
    <line x1="150" y1="35" x2="225" y2="115" stroke="white" stroke-width="0.5" opacity="0.25"/>
    <line x1="225" y1="115" x2="150" y2="195" stroke="white" stroke-width="0.5" opacity="0.25"/>
    <line x1="150" y1="195" x2="75" y2="115" stroke="white" stroke-width="0.5" opacity="0.25"/>
    <line x1="75" y1="115" x2="150" y2="35" stroke="white" stroke-width="0.5" opacity="0.25"/>
  </svg>
  <div style="position:absolute;top:10px;left:50%;transform:translateX(-50%)">{_shtml["OF"]}</div>
  <div style="position:absolute;top:98px;left:4%">{_shtml["MI"]}</div>
  <div style="position:absolute;top:98px;right:4%">{_shtml["CI"]}</div>
  <div style="position:absolute;top:158px;left:1%">{_shtml["Libre"]}</div>
  <div style="position:absolute;top:158px;right:1%">{_shtml["Flex"]}</div>
  <div style="position:absolute;top:200px;left:16%">{_shtml["SP"]}</div>
  <div style="position:absolute;top:200px;right:16%">{_shtml["RP"]}</div>
  <div style="position:absolute;bottom:8px;left:50%;transform:translateX(-50%);
    text-align:center;white-space:nowrap">
    <div style="font-size:10px;color:rgba(255,255,255,0.35)">{_n_is_bv}/7 IS · {_n_filled_bv}/7 slots</div>
    <div style="font-size:19px;font-weight:700;color:{_bv_rc}">{_total_bv:.1f} pts</div>
  </div>
</div>"""
        st.markdown(_diamond_html, unsafe_allow_html=True)

        # ── Slot buttons ──────────────────────────────────────────────────────
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        # Barre visuelle des slots (état rempli/actif)
        _bv_slot_bar = '<div style="display:flex;gap:3px;margin-top:6px">'
        for _sn in _BV_SLOTS:
            _is_act  = _sn == _bv_active
            _is_fill = _bv_lineup.get(_sn) is not None
            _bc  = _bv_rc if _is_act else ("rgba(76,175,80,0.35)" if _is_fill else "rgba(255,255,255,0.08)")
            _tc  = "#fff" if _is_act else ("rgba(255,255,255,0.8)" if _is_fill else "rgba(255,255,255,0.3)")
            _bv_slot_bar += (
                f'<div style="flex:1;text-align:center;padding:5px 0;'
                f'background:{_bc};border-radius:5px;font-size:10px;font-weight:700;'
                f'color:{_tc};white-space:nowrap">'
                f'{"●" if _is_fill else ""}{_BV_SLOT_LBL[_sn]}</div>'
            )
        _bv_slot_bar += "</div>"
        st.markdown(_bv_slot_bar, unsafe_allow_html=True)

        _bv_r1, _bv_r2 = st.columns(2)
        with _bv_r1:
            if st.button("✕ Vider le slot", key="bv_clear_slot", use_container_width=True):
                st.session_state[_bv_lk][_bv_active] = None
                st.rerun()
        with _bv_r2:
            if st.button("🗑️ Tout effacer", key="bv_clear_all", use_container_width=True):
                st.session_state[_bv_lk] = {s: None for s in _BV_SLOTS}
                st.rerun()

    with _right_bv:

        _bv_act_lbl = _BV_SLOT_LBL[_bv_active]
        st.markdown(
            f'<div style="font-size:1.05rem;font-weight:600;margin-bottom:6px">'
            f'Choisis ton '
            f'<span style="color:{_bv_rc};font-size:1.2rem">{_bv_act_lbl}</span>'
            f'<span style="font-size:0.8rem;opacity:0.45"> · {_bv_rar}</span></div>',
            unsafe_allow_html=True,
        )

        _bv_cur = _bv_lineup.get(_bv_active)
        if _bv_cur:
            _bv_cur_r  = _cl_bv.get(_bv_cur, {})
            _bv_cur_nm = _slug_name_map.get(_bv_cur_r.get("player_slug", ""), _bv_cur)
            st.markdown(
                f'<div style="padding:5px 10px;background:rgba(76,175,80,0.1);'
                f'border:1px solid rgba(76,175,80,0.3);border-radius:6px;'
                f'margin-bottom:6px;font-size:0.82rem">'
                f'✅ <b>{_bv_cur_nm}</b> — {float(_bv_cur_r.get("proj_eff") or 0):.0f} pts eff.'
                f'</div>',
                unsafe_allow_html=True,
            )

        _bv_q = st.text_input(
            "Recherche", key="bv_q",
            placeholder="🔍 Nom du joueur...",
            label_visibility="collapsed",
        )

        _valid_pos = _BV_SLOT_POS[_bv_active]
        _df_slot   = _df_bv[_df_bv["position_agg"].isin(_valid_pos)].copy()
        if _bv_q:
            _df_slot = _df_slot[
                _df_slot["card_name"].str.contains(_bv_q, case=False, na=False)
            ]
        _df_slot = _df_slot.sort_values("proj_eff", ascending=False).reset_index(drop=True)

        if _df_slot.empty:
            st.info("Aucun joueur disponible pour ce slot.")
        else:
            _n_bv_show = min(len(_df_slot), 24)
            for _ri in range(0, _n_bv_show, 3):
                _gcols = st.columns(3, gap="small")
                for _ci2, _gc in enumerate(_gcols):
                    if _ri + _ci2 >= _n_bv_show:
                        break
                    _row  = _df_slot.iloc[_ri + _ci2]
                    _cn   = _row["card_name"]
                    _sl   = _row["player_slug"]
                    _nm   = _slug_name_map.get(_sl, _cn)
                    _pos  = _row.get("position_exact", "?")
                    _sc   = float(_row.get("proj_eff") or 0.0)
                    _is   = bool(_row.get("is_eligible", False))
                    _pwr  = float(_row.get("card_power") or 1.0)
                    _img  = _row.get("picture_url", "")
                    _isc  = "#4CAF50" if _is else "#FF8C00"
                    _isl  = "IS" if _is else "OOS"
                    _used = _sl in _bv_used_slugs
                    _sel  = (_bv_lineup.get(_bv_active) == _cn)

                    with _gc:
                        if _img:
                            st.image(_img, use_container_width=True)
                        else:
                            st.markdown(
                                f'<div style="width:100%;height:90px;'
                                f'background:rgba(255,255,255,0.04);'
                                f'border-radius:6px 6px 0 0;display:flex;'
                                f'align-items:center;justify-content:center;'
                                f'font-size:11px;color:#666">{_pos}</div>',
                                unsafe_allow_html=True,
                            )
                        _alpha = "0.32" if (_used and not _sel) else "1"
                        _bg2   = "rgba(76,175,80,0.15)" if _sel else "rgba(255,255,255,0.03)"
                        _bdr2  = f"1px solid rgba(76,175,80,0.4)" if _sel else f"1px solid rgba({_bv_rc_rgb},0.15)"
                        _ml_lbl = "ML" if _row.get("proj_ml") is not None else "~"
                        st.markdown(
                            f'<div style="padding:4px 6px;background:{_bg2};'
                            f'border:{_bdr2};border-radius:0 0 6px 6px;opacity:{_alpha}">'
                            f'<div style="font-size:10px;font-weight:700;white-space:nowrap;'
                            f'overflow:hidden;text-overflow:ellipsis;color:#eee">{_nm}</div>'
                            f'<div style="font-size:9px;color:{_bv_rc}">{_pos} · ×{_pwr:.3f} · {_ml_lbl}</div>'
                            f'<div style="font-size:12px;font-weight:700;color:#4CAF50">{_sc:.0f} pts</div>'
                            f'<div style="font-size:9px;color:{_isc}">{_isl}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        _btn_lbl = "✅ Choisi" if _sel else ("⚠️ Utilisé" if _used else "Choisir →")
                        if st.button(
                            _btn_lbl,
                            key=f"bv_pick_{_cn}",
                            use_container_width=True,
                            disabled=(_used and not _sel),
                        ):
                            if _sel:
                                st.session_state[_bv_lk][_bv_active] = None
                            else:
                                st.session_state[_bv_lk][_bv_active] = _cn
                                _nxt = next(
                                    (s for s in _BV_SLOTS
                                     if st.session_state[_bv_lk].get(s) is None),
                                    None,
                                )
                                if _nxt:
                                    st.session_state["bv_active"] = _nxt
                            st.rerun()

# ── Statusbar (fixée en bas) ──────────────────────────────────────────────────
_last_upd = now_paris.strftime("%d %b %Y — %H:%M")
_filters_summary = f"{categorie} · {sel_stat_label} · {fenetre}"
render_statusbar(_last_upd, _filters_summary)
