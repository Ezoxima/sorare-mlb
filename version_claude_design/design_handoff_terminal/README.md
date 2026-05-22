# Handoff — Sorare MLB Terminal Redesign

## Overview
Refonte visuelle de l'app **Sorare MLB** (Streamlit, `app.py`) vers un dashboard de type **terminal de trading** : dark, data-dense, monospace. Couvre les deux vues principales :
1. **Défis journaliers** (`tab1`) — galerie classée par stat + top 3 suggestion + tableau triable
2. **Mon équipe** (`tab6` / lineup) — composition lineup avec prédit/réel/diff, distribution ML, banc

Plus une coque (ticker + tabs + sidebar + statusbar + drawer historique) commune à l'app.

## About the Design Files
Les fichiers dans `prototype/` sont des **références de design en HTML/React** — un prototype interactif qui montre l'apparence cible, la hiérarchie de l'information et les interactions. **Ce n'est PAS du code à copier-coller** dans l'app Streamlit.

L'objectif : **recréer ce design dans l'environnement Streamlit existant** (`sorare_mlb/app.py`) en utilisant les patterns déjà en place (`st.markdown(unsafe_allow_html=True)`, `st.columns`, `st.dataframe`, `st.tabs`, `@st.dialog`, etc.), avec injection CSS lourde via `st.markdown`.

Voir [STREAMLIT_PORTING.md](./STREAMLIT_PORTING.md) pour une stratégie de port détaillée, composant par composant.

## Fidelity
**High-fidelity (hifi).** Toutes les valeurs (couleurs, typo, tailles, espacements, bordures) sont finales. Les valeurs numériques affichées dans le prototype sont **factices** mais réalistes — elles proviennent des screenshots de l'app actuelle et de l'inspection du code. Les vraies données viendront des fonctions `load_*` existantes dans `app.py`.

---

## Design Tokens

### Couleurs

| Token | Hex | Usage |
|---|---|---|
| `--bg-0` | `#07090c` | Background app (la couche la plus profonde) |
| `--bg-1` | `#0c1014` | Background sidebar / panels / chrome |
| `--bg-2` | `#11161d` | Background inputs / select / table header / hover |
| `--bg-3` | `#161d26` | Surface active (chip, seg button) |
| `--bg-4` | `#1b232e` | Surface élevée |
| `--line` | `#1f2935` | Bordure de base entre cellules |
| `--line-2` | `#2a3543` | Bordure inputs / borders accentuées |
| `--line-3` | `#3a4654` | Hover border |
| `--fg-0` | `#e6ebf2` | Texte principal |
| `--fg-1` | `#aab4c2` | Texte secondaire |
| `--fg-2` | `#6b7585` | Texte tertiaire (labels) |
| `--fg-3` | `#4a5260` | Texte muted (small caps, captions) |
| `--pos` | `#4ade80` | Vert : gains, IS éligible, played |
| `--neg` | `#ff5d5d` | Rouge : pertes, DNP, IL |
| `--warn` | `#fbbf24` | Ambre : PP (probable pitcher), warnings |
| `--info` | `#5fb3ff` | Cyan : info, SP/RP positions |
| `--accent` | `#6ff0c8` | Mint : highlight primaire, focus, médiane ML |
| `--accent-2` | `#a78bfa` | Violet : FLEX slot, secondaire |

### Rarity (conservées depuis app.py)
| | |
|---|---|
| `unique` | `#ffd166` |
| `super_rare` | `#ff5d5d` |
| `rare` | `#5fb3ff` |
| `limited` | `#c894ff` |

### Typographie
- **Mono** (partout par défaut) : `'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace`
- **Sans** (descriptions occasionnelles, fallback) : `'Inter', system-ui, sans-serif`
- Body : `12px / 1.45`
- Labels (uppercase) : `9-10px / letter-spacing 0.14em`
- Métriques principales : `22px / weight 600 / tabular-nums`
- Headline gros chiffre : `32px / weight 700 / -0.02em letter-spacing`

### Spacing
| Échelle | px |
|---|---|
| tight | 4 |
| sm | 6 |
| md | 8 |
| base | 10 |
| lg | 14 |
| xl | 18 |
| 2xl | 22 |

### Borders & corners
- **Aucun `border-radius`** — terminal aesthetic, tout en coins droits.
- Bordures 1px partout, couleur `--line`.
- Accents fins (left-border 2px) pour signaler hiérarchie (top-3 cards).

### Shadows
- Aucune ombre diffuse. Seulement des `box-shadow` sous le drawer (`-20px 0 60px rgba(0,0,0,0.5)`) et des glow néon ponctuels :
  - `0 0 8px var(--accent)` (point pulse, médiane ML)
  - `0 0 6px var(--pos)` (live dot)

---

## Screens / Views

### Layout global

```
┌──────────────────────────────────────────────────────────────────────┐
│ TICKER (36px) : brand · feed scrollant · clock UTC/PAR · LIVE       │
├──────────────────────────────────────────────────────────────────────┤
│ TABS (44px) : 9 onglets numérotés · spacer · Documentation · ⟳     │
├──────────┬───────────────────────────────────────────────────────────┤
│          │                                                          │
│ SIDEBAR  │ CONTENT                                                  │
│ (260px)  │ (fluide)                                                 │
│          │                                                          │
├──────────┴───────────────────────────────────────────────────────────┤
│ STATUSBAR (24px) : conn · view · cache · filters · last-upd · v     │
└──────────────────────────────────────────────────────────────────────┘
```

Grid CSS sur `.shell` : `grid-template-rows: 36px 44px 1fr 24px`.

### 1. Ticker (top bar)
- Background `--bg-1`, border-bottom `--line`.
- **Brand** à gauche, point pulse vert + nom monospace `SORARE·MLB / TERMINAL`.
- **Feed** au milieu : items horizontaux, scrolling animation `translateX(-50%)` sur 80s, pause au hover. Items dupliqués pour boucle infinie.
- Chaque item : `<sym>` + flèche pos/neg + `<val>` colorée + delta optionnel.
- Items réalistes basés sur l'app : `GW23 OPEN`, `IL/D7 12 +3`, `PCT.IS 92.8%`, `CARDS 347`, `SO5.SCR 193.8 +8.4`, `PP.TOD 8/30`, `NXT.LOCK 2j 21h`, `ML.σ 5.42`, `RANK #41 ▲12`, `REWARD $8.40`.
- **Clock** à droite, pinned avec `flex-shrink: 0`.
- ⚠️ `.ticker__feed` doit avoir `overflow: hidden` + `min-width: 0` pour clipper le scroll.

### 2. Tabs (navigation)
- 9 onglets correspondant aux tabs Streamlit actuels (Défis, Équipe, Cartes, DB, Vis-à-vis, Projections, Compétitions, Lineups, Marché).
- Chaque tab : numéro 2 chiffres (`01`, `02`…) en `--fg-3` + label UPPERCASE en `--fg-2`.
- Tab actif : background `--bg-2`, label en `--fg-0`, numéro en `--accent`, border-bottom 2px `--accent`.
- Actions à droite : `Documentation [?]` et `⟳ Refresh [R]` (avec kbd hints).

### 3. Sidebar (filtres)
Sections séparées par `border-bottom: 1px solid --line`, chacune avec un `.side-title` en uppercase 9px letter-spacing 0.14em.

#### Section Manager
- Manager-row : avatar carré 28×28 en gradient `--accent → --accent-2`, initiales du manager, nom en `--fg-0`, sub (`347 cartes · 12 lineups`) en `--fg-2`.

#### Section Filtres galerie
- **Catégorie** (`HITTING` / `PITCHING`) : segmented control `.seg` (2 boutons côte à côte, l'actif a un underline `--accent`).
- **Statistique** : select natif stylé `.select` (background `--bg-2`, border `--line-2`, custom arrow via background-image).
- **Fenêtre** (5/10/20G) : segmented control 3 boutons.
- **Objectif** : `input[type=number]` `.num-input`.

#### Section Saison / Position / Rareté
- **Saison** (TOUS/IS/Classic) : segmented control 3.
- **Position** : chips cliquables (`SP, RP, CI, MI, OF, TOUS`) — chip actif = background `--bg-4`, color `--accent`, border `--accent`.
- **Rareté** : chips colorées par rareté (couleur de la rareté quand actif).

#### Section Calendrier
- Select jour de match (Tous les jours / Aujourd'hui / Demain / etc.).

#### Section Alertes
- Liste compacte avec dot + LABEL + texte. Couleur dot selon type (warn / info / pos).

### 4. Statusbar (bottom)
Cellules séparées par `border-right: 1px solid --line`. Chaque cellule : `<k>` en `--fg-3` + `<v>` en `--fg-1`. Cellules :
- `● CONN api.sorare.com`
- `VIEW <tab actif>`
- `CACHE ttl 3600s`
- `FILTERS <résumé des filtres>` (mise à jour live)
- spacer
- `LAST.UPD 22 mai 2026 — 23:12 UTC`
- `v 2.3.7-mlb`

### 5. Vue Défis journaliers (`view: defis`)

#### 5a. Headline strip (panel pleine largeur)
Grid 5 colonnes :
| K | V |
|---|---|
| Stat sélectionnée | Big (32px) abbréviation + label nom complet · sub `Fenêtre 10 matchs · Catégorie HITTING` |
| Joueurs ce jour | gros chiffre · sub `de N en galerie` |
| Pred. moyenne | gros chiffre en `--pos` · sub `σ ±5.4 pts` |
| Pred. max | gros chiffre · sub nom du joueur top |
| Composition | `<isCount> / <ppCount>` (vert/orange) · sub `IS éligibles / Probable Pitchers` |

Border 1px `--line` autour du panel, séparateurs verticaux internes.

#### 5b. Top 3 (suggestion d'alignement)
Panel avec header `Suggestion d'alignement | TOP 3 | tri par <stat> | ● LIVE`.

Grid 3 colonnes de `PlayerCard` :
- Border-left 2px accent variable (or/mint/cyan pour rank 1/2/3).
- Header card : rang (#1, #2, #3) coloré + nom + sub (équipe · poste · âge) + dot rareté à droite.
- **Art** (placeholder, voir composant ci-bas) : 110px de haut, gradient couleurs équipe, monogramme nom de famille en gros, étiquette rareté coin TR, n° série coin BL.
- **Row 3 cellules** : Stat avg / ML Pred (en `--pos`) / Range (lo–hi en `--fg-2`).
- **Sparkline** : 10 derniers matchs, fill semi-transparent + ligne `--accent`.
- **Meta** : tags `LIMITED IS PP` + à droite `vs PIT · 23:35`.

#### 5c. Toolbar
Une barre horizontale `--bg-2` au-dessus du tableau :
- `CLASSEMENT <N> joueurs`
- séparateur 1px
- command-bar `/` `filtrer par nom, équipe…` `⌘K`
- séparateur
- `tri <key> <dir>`
- spacer
- toggles : `Sparklines` (on), `Cachés IL` (off)

#### 5d. Tableau
- `position: sticky` sur thead.
- Colonnes : `# · Joueur · Poste · Équipe · Rareté · Saison · Avg · Pred · Range · Tendance · Heure · Adversaire`.
- Tri au clic sur n'importe quelle col (toggle asc/desc), indicateur ▲/▼ + color `--accent` sur la col triée.
- Ligne sélectionnée : background `rgba(111,240,200,0.06)`, color `--fg-0`.
- Row click → ouvre drawer historique.
- Mini-bars dans `Tendance` (sparkline mini, 70×18px).

### 6. Vue Mon équipe (`view: equipe`)

#### 6a. Lineup summary (panel pleine largeur)
Header : `Lineup actuelle | GW 23 | CLASSIC | LIMITED CHAMPION | … Verrouillage 2j 21h ●`.

Grid 5 cellules :
1. **Score prédit total** : big number `pts` · `Eff. ×power: XX pts` · checks `✓ IS 7/7` `✓ Club max 4/6` `✓ 7/7 slots`
2. **Slots remplis** : `7/7` · sub liste positions
3. **IS éligibles** : `7/7` en `--pos`
4. **Club max** : `4/6` · sub nom du club
5. **Reward attendue** : `$8.40` en `--warn` · sub `Palier 51-100 · 193.8 pts`

#### 6b. Toolbar composition
Idem défis : labels, chips `Cartes / Liste / Diamant`, toggle `Afficher verrouillage`, actions `⤓ Export PNG` / `★ Sauvegarder`.

#### 6c. Lineup grid (7 slots SP/RP/CI/MI/OF/FLEX/LIBRE)
Grid `repeat(7, 1fr)` gap 12px. Chaque `SlotCard` :
- Label slot en header (UPPERCASE + numéro `01`–`07`)
- Art placeholder 140px (cf. composant)
- Nom + pos-pill colorée par poste + team-chip avec dot couleur équipe
- **pred-strip** 3 cells : `Prédit | Réel | Diff` (Diff vert si positif, rouge sinon, dim si pas encore joué).

Couleurs pos-pill : SP/RP = info bleu, CI/MI = accent mint, OF = warn ambre, FLEX = violet, LIBRE = rouge.

#### 6d. Distribution ML (panel demi-largeur gauche)
Pour chaque slot une ligne :
- Label slot · nom joueur · `lo–hi` · `pred` (à droite)
- Barre horizontale 8px : background `--bg-2`, segment ML rempli entre `low/maxScale` et `high/maxScale` en gradient, médiane = trait 2px `--accent` avec glow.
- Légende en bas : gradient = intervalle ML, trait = médiane prédite, total à droite.

#### 6e. Banc & candidats (panel demi-largeur droite)
Tableau : `Joueur | Poste | Équipe | Pred | Avg | Tendance | Match`. Mêmes patterns que tableau Défis.

### 7. Drawer historique
- Slide-in depuis la droite (`translateX` 220ms easing custom), width 560px max-width 92vw.
- Overlay derrière `rgba(0,0,0,0.6)` + click-to-close.
- `Esc` ferme aussi.
- Header : avatar gradient équipe + nom big + sub `équipe · pos · âge · rareté · #serial` + bouton fermer.
- **Section Performance (20 derniers matchs)** : KPI row `Moyenne | σ | L5 | Tendance | Pred GW23` puis ScoreChart SVG (180px haut) :
  - Grid horizontale (4 lignes pointillées)
  - Y-labels axe gauche
  - Ligne moy `--fg-3` pointillée
  - Ligne pred `--accent` pointillée
  - Polyline scores (vert si ≥ moy, ambre si <), points 2.5r
  - DNP : bande rouge translucide pleine hauteur + `×` rouge en bas
- **Section Détail** : table reverse chrono (Date · GW · Status · Score · STAT)
- **Section Prochain match** : grid 4 (Adversaire / Heure / Intervalle / Probable).

---

## Interactions & Behavior

| Action | Effet |
|---|---|
| Clic tab haut | Change `active`, rerender content |
| Clic chip filter (saison/poste/rareté) | Toggle live, refiltre tableaux et top 3 |
| Clic colonne header table | Tri (toggle asc/desc), indicateur ▲/▼ |
| Clic ligne table OU carte top 3 OU carte slot OU ligne banc | Ouvre drawer historique pour ce joueur |
| Clic overlay drawer / bouton ✕ / touche Esc | Ferme drawer |
| Hover ticker | Pause animation scroll |
| Hover row table | Background `--bg-2` |

### Animations
- Drawer slide-in : `220ms cubic-bezier(0.2, 0.8, 0.2, 1)` translateX 20→0 + opacity 0→1
- Overlay fade-in : `160ms ease-out`
- Pulse dot : `2s ease-in-out infinite` (opacity 1↔0.4)
- Ticker scroll : `80s linear infinite` (translateX 0 → -50%)
- Hover transitions : `120ms` sur color/background/border-color

### Responsive
**Le prototype est conçu pour desktop ≥1380px.** Sur Streamlit, c'est OK puisque le dashboard est utilisé en desktop. En mobile, les grids 5/7 colonnes basculeraient en stack vertical via media queries, mais non couvert ici.

---

## State Management (côté Streamlit)
Mappage vers `st.session_state` :

| State React | st.session_state | Source de vérité |
|---|---|---|
| `active` (tab) | géré par `st.tabs()` natif | — |
| `filters.categorie` | `st.session_state['categorie']` | `st.radio('Catégorie', ['HITTING', 'PITCHING'])` |
| `filters.stat` | déduit du selectbox | `st.selectbox('Statistique', ...)` |
| `filters.fenetre` | `st.session_state['fenetre']` | `st.radio('Fenêtre', [5,10,20])` |
| `filters.saison` | `st.session_state['tab1_saison']` (déjà existe) | `st.radio('Saison', ['TOUS','IS','Classic'])` |
| `filters.poste` | `st.session_state['tab1_poste']` (déjà existe) | `st.selectbox('Poste', ...)` |
| `filters.rarities` | `st.session_state['filter_rar']` (déjà existe) | `compact_multiselect` |
| `history` (drawer ouvert) | `st.session_state['_tab1_sel']` (déjà existe) | `st.dataframe(... on_select='rerun')` + `@st.dialog` |
| `sortKey/sortDir` | déduit du clic sur header (Streamlit `st.dataframe` gère natif) | — |

Les fonctions `load_*` existantes restent la source de données ; seul l'affichage change.

---

## Assets
Aucun asset binaire requis. Le prototype utilise :
- **Google Fonts** : `JetBrains Mono` (400/500/600/700) et `Inter` (idem)
- **SVG inline** pour sparklines et chart historique (généré côté React)
- **CSS gradients** pour fond cartes joueurs (couleurs équipe)
- **Placeholders monogramme** au lieu des vraies photos cartes Sorare (cf. décision « card_treatment »)

Pour intégrer les vraies images cartes Sorare plus tard : remplacer le composant `PlayerArt` par un `<img>` pointant vers l'URL Sorare CDN (ces URLs sont accessibles via l'API GraphQL `cards.pictureUrl`).

---

## Files

Le prototype complet est dans `prototype/` :
- `Sorare MLB Terminal.html` — entry HTML, charge React + Babel + tous les modules
- `styles.css` — **toute la feuille de style** (design tokens en haut, ~600 lignes). Cette CSS est ce qu'il faut **adapter et injecter via `st.markdown` dans `app.py`**.
- `data.js` — données factices + constantes (TEAMS, RARITY, STATS_AVAILABLE, TABS). Sert de schéma de référence pour mapper aux DataFrames pandas existants.
- `primitives.jsx` — `Sparkline`, `MiniBar`, `PlayerArt`, `PlayerCard`, `SlotCard`, `teamGradient`
- `shell.jsx` — `Ticker`, `Tabs`, `Sidebar`, `StatusBar`, `Alert`
- `drawer.jsx` — `HistoryDrawer`, `ScoreChart` (le graph SVG remplace `plotly.graph_objects.Figure` actuel)
- `defis.jsx` — `DefisView` (équivalent `tab1`)
- `equipe.jsx` — `EquipeView` (équivalent vue lineup)
- `app.jsx` — root, gère état global

Voir [STREAMLIT_PORTING.md](./STREAMLIT_PORTING.md) pour le mapping ligne-à-ligne.

## Notes
- Le projet Streamlit cible est dans `sorare_mlb/app.py`. Toutes les fonctions `load_*`, constantes `POSITION_*`, `RARITY_*`, `FENETRE_OPTIONS` doivent être préservées.
- Le composant `render_player_card` existant (ligne ~542 de `app.py`) est à remplacer par un équivalent qui produit le HTML du `PlayerCard` du prototype.
- Le graph plotly `show_player_chart` (ligne ~585) à remplacer par un équivalent (plotly avec le même styling — fond `#0c1014`, axes `#6b7585`, ligne `#6ff0c8`) OU un SVG inline injecté en `st.markdown`.
