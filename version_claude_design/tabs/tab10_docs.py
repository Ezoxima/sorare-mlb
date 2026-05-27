import streamlit as st


def render(ctx: dict) -> None:
    st.title("📖 Documentation du dashboard Sorare MLB")
    st.caption("Référence complète : architecture, onglets, méthodes de prédiction et règles Sorare.")

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
