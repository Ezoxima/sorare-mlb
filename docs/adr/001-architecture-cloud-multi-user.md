# ADR 001 — Architecture cloud multi-user

**Date :** 2026-06-06  
**Statut :** En cours d'implémentation  
**Décideurs :** Gwenael Cochet

---

## Contexte

Le dashboard Sorare MLB existe en version locale (PostgreSQL + Streamlit). L'objectif est d'ouvrir l'app à 20-30 utilisateurs externes inconnus, chacun avec sa propre galerie Sorare et ses propres données (remises, lineups).

---

## Décision

Migration vers une architecture cloud basée sur **Supabase + Streamlit Cloud + GitHub Actions**, en conservant le setup local intact et fonctionnel.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Local (inchangé)                                        │
│  ─────────────────────────────────────────────────────  │
│  PostgreSQL local (EAV, game_score_details natif)        │
│  app.py + data_loaders.py                               │
│  update_data.py (exécution manuelle)                    │
│  data/remises.json                                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Cloud                                                   │
│  ─────────────────────────────────────────────────────  │
│  Supabase PostgreSQL                                    │
│    mlb.*  (toutes tables sauf game_score_details)       │
│    mlb.game_score_details_wide  (format pivotée)        │
│    mlb.user_profiles  (user_id → manager_slug)          │
│    mlb.remises  (remise % par user et par carte)        │
│    auth.users  (Supabase Auth — Google + magic link)    │
│                                                         │
│  Streamlit Cloud                                        │
│    app.py + data_loaders_cloud.py                       │
│    CLOUD_MODE=1 → switche les loaders automatiquement   │
│                                                         │
│  GitHub Actions (cron 7h UTC)                           │
│    update_data.py → DATABASE_URL=Supabase               │
│    WIDE_MODE=1 → écrit en format wide                   │
└─────────────────────────────────────────────────────────┘
```

---

## Choix techniques et justifications

### Supabase plutôt qu'une autre solution

- PostgreSQL natif → migration directe du schéma existant, SQLAlchemy inchangé
- Auth intégrée (Google OAuth + magic link) → pas de lib tierce à maintenir
- Row Level Security natif → isolation des données par user sans code applicatif
- Free tier suffisant pour 20-30 users (~300 MB de données après pivot)

### Pivot de `game_score_details` (EAV → wide)

La table `game_score_details` (1.6 GB en local, format EAV) dépasse le free tier Supabase (500 MB).

**Format EAV local :**
```
(player_slug, game_date, stat, category) → stat_value, points
6.5M lignes
```

**Format wide Supabase :**
```
(player_slug, game_date, category) → 22 colonnes stat_value + 22 colonnes points
459K lignes — 121 MB
```

La BDD locale conserve le format EAV original. Le pivot n'existe que sur Supabase. Rollback immédiat possible en désactivant `CLOUD_MODE`.

### Rollback

Désactiver `CLOUD_MODE` dans l'environnement suffit à faire basculer l'app vers la BDD locale. Aucune modification de la BDD locale n'a été faite.

### Données partagées vs données par user

| Données | Scope | Source |
|---|---|---|
| Scores, matchs, stats pitchers, météo | Partagées (identiques pour tous) | GitHub Actions → Supabase |
| Galerie, prix cartes | Par manager_slug | Phase 1 : ton JWT perso ; Phase 2 : OAuth Sorare |
| Remises % | Par user_id | Éditées dans Tab 2, stockées dans mlb.remises |
| Lineups sauvegardés | Par user_id | À venir |

### Authentification

- **Phase 1 :** Google OAuth + magic link email (Supabase Auth)
- **Phase 2 :** OAuth Sorare natif (quand leur API OAuth sera disponible)

Chaque user fournit son `manager_slug` Sorare lors de l'onboarding → stocké dans `mlb.user_profiles`.

---

## Conséquences

- `data_loaders_cloud.py` remplace les lectures parquet par des requêtes SQL sur Supabase
- `tabs/tab2_cartes.py` conditionné : `CLOUD_MODE` → `mlb.remises`, sinon → `data/remises.json`
- Les scripts `fetch_*.py` sont inchangés — seul `DATABASE_URL` change selon l'environnement
- `game_score_details_wide` nécessite un script d'adaptation dans `data_loaders_cloud.py` (les requêtes EAV deviennent des requêtes wide ou unpivot à la volée)

---

## État d'avancement

- [x] Étape 1 — Supabase créé + Google OAuth configuré
- [x] Étape 2 — Migration BDD (sans game_score_details)
- [x] Étape 2b — Pivot game_score_details → game_score_details_wide (121 MB)
- [ ] Étape 3 — Vérification scripts fetch + variables env
- [ ] Étape 4 — GitHub Actions pipeline
- [ ] Étape 5 — data_loaders_cloud.py
- [ ] Étape 6 — auth.py + flow Google
- [ ] Étape 7 — Remises cloud
- [ ] Étape 8 — Déploiement Streamlit Cloud
- [ ] Étape 9 — Onboarding user
