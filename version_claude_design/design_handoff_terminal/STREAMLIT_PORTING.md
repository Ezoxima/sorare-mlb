# Streamlit Porting Guide — Sorare MLB Terminal

Ce document est destiné à **Claude Code** (ou n'importe quel dev) bossant sur `sorare_mlb/app.py`. Il décrit comment porter le prototype HTML vers Streamlit.

## TL;DR — Stratégie recommandée

**Approche hybride** : Streamlit natif pour les contrôles (sidebar, tabs, dataframe sortable) + **CSS injection massive** via `st.markdown(unsafe_allow_html=True)` pour le thème terminal + `st.dialog` pour le drawer.

Pas besoin de custom component React. Streamlit 1.30+ a tout ce qu'il faut :
- `st.dataframe` avec `on_select='rerun'` + `selection_mode='single-row'` → utilisé déjà dans `app.py` pour le clic ligne
- `@st.dialog(width='large')` → utilisé déjà pour `show_player_chart`
- `st.tabs()` → utilisé déjà
- `st.radio(horizontal=True)` → equivalent du segmented control
- `st.html()` ou `st.markdown(..., unsafe_allow_html=True)` → blocs HTML custom

---

## Étape 1 — Theme global

### 1a. `.streamlit/config.toml`
Forcer le thème dark + accents :

```toml
[theme]
base = "dark"
primaryColor = "#6ff0c8"
backgroundColor = "#07090c"
secondaryBackgroundColor = "#0c1014"
textColor = "#e6ebf2"
font = "monospace"
```

### 1b. CSS injection à top de `app.py`
Remplace le bloc CSS existant (lignes ~17-67) par le contenu de `prototype/styles.css`, adapté pour cibler les conteneurs Streamlit. Ajouter au début :

```python
TERMINAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg-0:#07090c; --bg-1:#0c1014; --bg-2:#11161d; --bg-3:#161d26; --bg-4:#1b232e;
  --line:#1f2935; --line-2:#2a3543; --line-3:#3a4654;
  --fg-0:#e6ebf2; --fg-1:#aab4c2; --fg-2:#6b7585; --fg-3:#4a5260;
  --pos:#4ade80; --neg:#ff5d5d; --warn:#fbbf24; --info:#5fb3ff;
  --accent:#6ff0c8; --accent-2:#a78bfa;
  --r-unique:#ffd166; --r-superrare:#ff5d5d; --r-rare:#5fb3ff; --r-limited:#c894ff;
  --mono:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;
}

/* Reset Streamlit chrome */
html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg-0) !important;
  color: var(--fg-0) !important;
  font-family: var(--mono) !important;
  font-size: 12px;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
  background: var(--bg-1) !important;
  border-right: 1px solid var(--line);
}
.block-container { padding: 1rem 1.5rem !important; max-width: none !important; }

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: var(--bg-1);
  border-bottom: 1px solid var(--line);
  gap: 0;
}
[data-testid="stTabs"] button[role="tab"] {
  font-family: var(--mono) !important;
  font-size: 11px !important;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--fg-2);
  border-right: 1px solid var(--line);
  padding: 8px 16px;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  color: var(--fg-0);
  background: var(--bg-2);
  border-bottom: 2px solid var(--accent) !important;
}

/* Radios → segmented control */
[data-testid="stRadio"] > div { flex-direction: row; gap: 0; border: 1px solid var(--line-2); }
[data-testid="stRadio"] label {
  flex: 1; padding: 6px 8px; font-size: 10px; text-align: center;
  border-right: 1px solid var(--line-2); margin: 0 !important;
}
[data-testid="stRadio"] label:last-child { border-right: none; }

/* Selectbox */
[data-baseweb="select"] > div {
  background: var(--bg-2) !important;
  border: 1px solid var(--line-2) !important;
  border-radius: 0 !important;
  font-family: var(--mono) !important;
  font-size: 11px !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
  border: 1px solid var(--line);
}
[data-testid="stDataFrame"] thead th {
  background: var(--bg-2) !important;
  color: var(--fg-3) !important;
  font-size: 9px !important;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

/* Metric (utilisé par st.metric) */
[data-testid="stMetric"] {
  background: var(--bg-1);
  border: 1px solid var(--line);
  padding: 12px 14px;
}
[data-testid="stMetricLabel"] {
  font-size: 9px !important;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--fg-3) !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important;
  font-size: 22px !important;
  font-weight: 600;
  color: var(--fg-0) !important;
}

/* Coller le reste de styles.css ici (toutes les classes custom : .panel, .pcard, .slot, etc.) */
... [tout le contenu de prototype/styles.css] ...
</style>
"""

st.markdown(TERMINAL_CSS, unsafe_allow_html=True)
```

---

## Étape 2 — Ticker

Streamlit n'a pas de header custom. Solution : injecter un `<div class="ticker">` en haut via `st.markdown` juste après le `set_page_config`. Comme c'est statique côté contenu, le HTML peut être généré côté Python à partir d'un dict.

```python
def render_ticker():
    items = [
        ("GW23", "OPEN", "pos", None),
        ("IL/D7", "12", "neg", "+3"),
        ("PCT.IS", "92.8%", "pos", "+1.2"),
        # ... etc
    ]
    html_items = "".join(
        f'<span class="ticker__item"><span class="sym">{s}</span>'
        f'{"<span class=\\"arrow " + cls + "\\"></span>" if d else ""}'
        f'<span class="val {cls}">{v}</span>'
        f'{"<span class=\\"val " + cls + "\\" style=\\"font-size:10px\\">" + d + "</span>" if d else ""}'
        f'</span>'
        for s, v, cls, d in items
    )
    st.markdown(f"""
    <div class="ticker">
      <div class="ticker__brand"><span class="ticker__brand-dot"></span>SORARE·MLB / TERMINAL</div>
      <div class="ticker__feed"><div class="ticker__feed-inner">{html_items}{html_items}</div></div>
      <div class="ticker__clock">
        <span>UTC <span style="color:var(--fg-0)">{datetime.utcnow().strftime("%H:%M:%S")}</span></span>
        <span class="live">LIVE</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
```

---

## Étape 3 — Sidebar (filtres)

Le code existant (`with st.sidebar:` lignes ~754-810) est déjà très proche. Quelques ajustements :

```python
with st.sidebar:
    st.markdown("""<div class="manager-row">
      <div class="manager-avatar">{}</div>
      <div class="manager-info">
        <div class="name">{}</div>
        <div class="sub">{} cartes · {} lineups</div>
      </div>
    </div>""".format(initials, name, ncards, nlineups), unsafe_allow_html=True)

    categorie = st.radio("Catégorie", ["HITTING", "PITCHING"], horizontal=True)
    # ... reste inchangé, le CSS rendra ça comme segmented control
```

Pour les **chips de position** (qui sont des multi-select compacts), garde `compact_multiselect` mais override le CSS pour qu'ils ressemblent aux chips du prototype.

---

## Étape 4 — Vue Défis journaliers (`tab1`)

### 4a. Headline strip (5 métriques)
Au lieu de 3 `st.columns` + `st.metric`, génère le HTML directement :

```python
with tab1:
    st.markdown(f"""
    <div class="panel" style="margin-bottom:14px">
      <div class="lineup-summary">
        <div class="ls-cell">
          <div class="k">Stat sélectionnée</div>
          <div class="headline">
            <span class="big">{sel_stat_label}</span>
            <span class="label">{sel_stat.replace('_',' ').title()}</span>
          </div>
          <div class="sub" style="margin-top:8px">
            Fenêtre <span style="color:var(--fg-0)">{fenetre}</span> ·
            Catégorie <span style="color:var(--fg-0)">{categorie}</span>
          </div>
        </div>
        <div class="ls-cell">
          <div class="k">Joueurs ce jour</div>
          <div class="v">{len(df_view)}</div>
          <div class="sub">de {len(df)} en galerie</div>
        </div>
        <div class="ls-cell">
          <div class="k">Pred. moyenne</div>
          <div class="v pos">{df_view['predicted'].mean():.1f}</div>
          <div class="sub">σ ±{df_view['predicted'].std():.1f} pts</div>
        </div>
        <!-- etc -->
      </div>
    </div>
    """, unsafe_allow_html=True)
```

### 4b. Top 3 cards
Remplace le `render_player_card` actuel par une version qui génère le HTML du prototype. Voir `prototype/primitives.jsx::PlayerCard`. Génère 3 colonnes :

```python
top3 = df_view.head(3)
cols = st.columns(3)
for i, ((_, row), col) in enumerate(zip(top3.iterrows(), cols)):
    with col:
        st.markdown(render_terminal_card(i, row, sel_stat_label), unsafe_allow_html=True)
```

Pour la **sparkline** dans la card : génère le SVG inline en Python (cf. fonction `gen_sparkline_svg` ci-dessous), inclus dans le HTML.

```python
def gen_sparkline_svg(values, w=200, h=24, color='var(--accent)'):
    if not values: return ''
    mn, mx = min(values), max(values)
    span = max(0.001, mx - mn)
    points = [(i / (len(values)-1) * w, h - ((v-mn)/span) * h) for i, v in enumerate(values)]
    path = " ".join(f"{'M' if i==0 else 'L'}{x:.1f},{y:.1f}" for i,(x,y) in enumerate(points))
    fill_path = f"{path} L{points[-1][0]:.1f},{h} L{points[0][0]:.1f},{h} Z"
    return f"""<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" preserveAspectRatio="none">
      <path d="{fill_path}" fill="{color}" opacity="0.1"/>
      <path d="{path}" fill="none" stroke="{color}" stroke-width="1.2"/>
    </svg>"""
```

### 4c. Tableau classement
Garder `st.dataframe` natif (déjà sortable, déjà clic-row → drawer). Ajouter une colonne `Tendance` avec sparkline. Pour ça, deux options :

**Option A (recommandée)** : utiliser `st.column_config.LineChartColumn` (Streamlit 1.23+) :

```python
df_display = df_view.copy()
df_display['Tendance'] = df_view['spark']  # list of 10 floats per row

event = st.dataframe(
    df_display,
    use_container_width=True,
    hide_index=True,
    on_select='rerun',
    selection_mode='single-row',
    column_config={
        'Tendance': st.column_config.LineChartColumn(width='small', y_min=0),
        sel_stat_label: st.column_config.NumberColumn(format="%.1f"),
        'predicted': st.column_config.NumberColumn('Pred', format="%.1f"),
        'low': st.column_config.NumberColumn('Min', format="%.0f"),
        # ...
    },
)
```

**Option B** : générer un tableau HTML custom (perd le sort natif, mais full control sur le style). Pas recommandé sauf si le rendu de `st.dataframe` ne plaît pas.

---

## Étape 5 — Vue Mon équipe (lineup)

Cette vue n'existe pas encore à 100% dans `app.py` (le code lineup est éparpillé dans tab6/8). C'est l'occasion d'en faire une vraie page propre.

### 5a. Summary panel (5 cellules)
Même approche que headline strip : un seul `st.markdown` qui génère tout.

### 5b. Lineup grid (7 slots)
Pour les **7 cartes côte à côte** : `st.columns(7)` avec dans chaque colonne un `st.markdown` contenant le HTML d'une `SlotCard`. La carte inclut la pred-strip Prédit/Réel/Diff.

```python
def render_slot_card(slot, idx, player):
    rarity = RARITY_COLOR.get(player['rarity'].lower(), '#888')
    team = TEAMS_DICT.get(player['team'], {})
    diff = (player.get('real') - player['predicted']) if player.get('real') else None
    return f"""
    <div class="slot">
      <div class="slot__label"><span>{slot}</span><span class="num">{idx+1:02d}</span></div>
      {render_player_art(player, 140)}
      <div style="padding:8px 10px;border-top:1px solid var(--line)">
        <div style="font-size:12px;font-weight:600;color:var(--fg-0)">{player['name']}</div>
        <div style="margin-top:4px;font-size:10px;color:var(--fg-2)">
          <span class="pos-pill {slot.lower()}">{slot}</span>
          <span class="team-chip">
            <span class="team-dot" style="background:{team.get('primary','#3a4654')}"></span>
            {team.get('name', player['team'])}
          </span>
        </div>
      </div>
      <div class="pred-strip">
        <div class="cell"><div class="k">Prédit</div><div class="v">{player['predicted']:.1f}</div></div>
        <div class="cell"><div class="k">Réel</div><div class="v dim">{f"{player['real']:.1f}" if player.get('real') else '—'}</div></div>
        <div class="cell"><div class="k">Diff</div>
          <div class="v {'pos' if (diff or 0) >= 0 else 'neg' if diff is not None else 'dim'}">
            {'—' if diff is None else f"{'+' if diff>=0 else ''}{diff:.1f}"}
          </div>
        </div>
      </div>
    </div>
    """

cols = st.columns(7)
for slot_info, col in zip(LINEUP_SLOTS, cols):
    with col:
        player = lookup_player(slot_info['fill'])
        st.markdown(render_slot_card(slot_info['slot'], i, player), unsafe_allow_html=True)
```

### 5c. Distribution ML (panel)
Génère le HTML directement avec une boucle Python. Pas besoin de plotly. Chaque ligne :

```python
def render_dist_row(slot, player, max_scale=50):
    start = (player['low'] / max_scale) * 100
    width = ((player['high'] - player['low']) / max_scale) * 100
    mean = (player['predicted'] / max_scale) * 100
    return f"""
    <div style="margin-bottom:10px">
      <div style="display:flex;gap:10px;font-size:11px;align-items:center">
        <span style="width:40px;color:var(--fg-2);font-size:10px;letter-spacing:0.1em">{slot}</span>
        <span style="flex:1;color:var(--fg-0)">{player['name']}</span>
        <span style="color:var(--fg-2);font-size:10px">{player['low']:.0f}–{player['high']:.0f}</span>
        <span style="color:var(--pos);font-weight:600;width:38px;text-align:right">{player['predicted']:.1f}</span>
      </div>
      <div style="position:relative;height:8px;margin-top:4px;background:var(--bg-2);border:1px solid var(--line)">
        <div style="position:absolute;left:{start}%;width:{width}%;top:0;bottom:0;
                    background:linear-gradient(90deg,rgba(95,179,255,0.2),rgba(74,222,128,0.35),rgba(95,179,255,0.2))"></div>
        <div style="position:absolute;left:{mean}%;top:-2px;bottom:-2px;width:2px;
                    background:var(--accent);box-shadow:0 0 4px var(--accent)"></div>
      </div>
    </div>
    """
```

---

## Étape 6 — Drawer historique

Déjà presque en place dans `app.py` via `@st.dialog("📊 Historique joueur", width="large")` (ligne ~585). Il faut juste :

1. Remplacer le titre par le HTML stylé du drawer (avatar + nom + sub + close)
2. Remplacer le graph `plotly` actuel par un styling assorti :

```python
fig.update_layout(
    paper_bgcolor='#0c1014',
    plot_bgcolor='#0c1014',
    font=dict(family='JetBrains Mono', color='#aab4c2', size=10),
    xaxis=dict(gridcolor='#1f2935', tickcolor='#4a5260'),
    yaxis=dict(gridcolor='#1f2935', tickcolor='#4a5260'),
    margin=dict(l=30, r=16, t=16, b=24),
)
# Ligne scores
fig.add_trace(go.Scatter(line=dict(color='#6ff0c8', width=1.5), marker=dict(color='#4ade80', size=6)))
# Ligne moyenne
fig.add_hline(y=mean, line=dict(color='#4a5260', dash='dot'))
# Ligne pred (target)
fig.add_hline(y=target, line=dict(color='#6ff0c8', dash='dash'))
```

Streamlit n'a pas de side-drawer natif. Le `st.dialog` actuel s'ouvre en modal centré. Si tu veux un vrai drawer-side, il faudrait un custom component. Pour le port initial, **garde le modal** — ça fait le job.

---

## Étape 7 — Status bar

Comme le ticker, c'est un bloc HTML statique au bottom. Streamlit ne fournit pas de footer fixe, mais on peut hacker avec `position: fixed; bottom: 0` :

```python
st.markdown(f"""
<div class="statusbar" style="position:fixed;bottom:0;left:0;right:0;z-index:100">
  <span class="statusbar__cell"><span class="dot live"></span><span class="k">CONN</span><span class="v">api.sorare.com</span></span>
  <span class="statusbar__cell"><span class="k">CACHE</span><span class="v">ttl 3600s</span></span>
  <span class="statusbar__cell"><span class="k">FILTERS</span><span class="v">{filters_summary}</span></span>
  <span class="statusbar__spacer"></span>
  <span class="statusbar__cell"><span class="k">LAST.UPD</span><span class="v">{last_upd}</span></span>
</div>
""", unsafe_allow_html=True)

# Et ajoute un padding-bottom au block-container pour pas que la statusbar cache du contenu
```

---

## Étape 8 — Plan d'attaque suggéré pour Claude Code

1. **PR 1 — Theme** : injecter `styles.css` adapté + `config.toml`. Tester sur l'app actuelle sans rien d'autre changer ; tout doit déjà se foncer correctement.
2. **PR 2 — Ticker + statusbar** : ajouter les bandeaux haut/bas.
3. **PR 3 — Sidebar** : adapter le code existant pour passer en segmented controls + chips.
4. **PR 4 — Tab Défis** : refondre tab1 avec headline strip + cards top 3 + tableau enrichi (LineChartColumn).
5. **PR 5 — Tab Mon équipe** : créer la vraie page lineup avec les 7 slots, pred-strip, distribution ML, banc.
6. **PR 6 — Drawer** : restyle plotly + dialog wrapper.
7. **PR 7** : restyle les autres tabs (DB, Vis-à-vis, Projections, etc.) avec les mêmes primitives.

---

## Pièges connus

- **`unsafe_allow_html=True`** : Streamlit sanitize agressivement. Si un attribut n'apparaît pas, c'est probablement filtré. Workaround : `st.components.v1.html(html_string, height=N)` qui rend dans un iframe et accepte tout.
- **CSS `:has()`** : pas supporté partout, éviter.
- **Selecteurs Streamlit** : `[data-testid="..."]` change parfois entre versions. Pin la version de streamlit dans `requirements.txt`.
- **Animations CSS dans `st.markdown`** : OK si le bloc reste monté. Si Streamlit le re-render (rerun), l'animation reprend du début. Pour le ticker, utiliser `st.components.v1.html` pour l'isoler dans un iframe et éviter les re-renders.
- **`st.columns(7)`** : assure-toi que la page est en `layout="wide"` (déjà le cas dans `app.py`).
- **Performance** : si la galerie a >500 joueurs, ne génère pas les sparklines en HTML pour toutes les lignes — utilise `column_config.LineChartColumn` natif.
