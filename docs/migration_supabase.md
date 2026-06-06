# Migration Supabase — Dashboard Sorare MLB multi-user

> **Objectif :** dupliquer l'app en cloud (Supabase + Streamlit Cloud + GitHub Actions) pour 20-30 users avec auth Google, sans toucher au setup local.

---

## Architecture cible

```
Local (inchangé)                         Cloud
────────────────────────────────         ──────────────────────────────────────────
PostgreSQL local                         Supabase PostgreSQL
  mlb.game_score_details (EAV)            mlb.game_score_details_wide (pivotée)
app.py + data_loaders.py                 app.py + data_loaders_cloud.py
update_data.py (manuel)                  GitHub Actions (cron 7h UTC)
data/remises.json                        mlb.remises (par user_id)
```

> **Principe de sécurité :** la BDD locale n'est jamais modifiée. Rollback = supprimer l'app Supabase.

---

## Étape 1 — Supabase : création du projet

- [ ] Créer un compte sur https://supabase.com
- [ ] Nouveau projet → région la plus proche (pour la France : **Central EU - Frankfurt**) → noter le mot de passe DB
- [ ] Récupérer dans **Settings → API** :
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_KEY`
- [ ] Récupérer dans **Settings → Database** :
  - `DATABASE_URL` (connection string PostgreSQL, mode "Session")
- [ ] Activer Google OAuth :
  - Authentication → Providers → Google → Enable
  - Nécessite un **Client ID** et **Client Secret** Google (voir note ci-dessous)

### Google Cloud Console (pour OAuth)
1. https://console.cloud.google.com → nouveau projet
2. APIs & Services → Credentials → Create OAuth 2.0 Client ID
3. Type : **Web application**
4. Authorized redirect URI : `https://[ref].supabase.co/auth/v1/callback`
5. Copier Client ID + Secret → coller dans Supabase

---

## Étape 2 — Migration de la base de données (toutes les tables sauf game_score_details)

`game_score_details` est exclue du dump — elle sera remplacée par une version pivotée (étape 2b).

```bash
# Dump toutes les tables mlb SAUF game_score_details
pg_dump -n mlb -Fc \
  --exclude-table=mlb.game_score_details \
  -d <local_db_name> -f mlb_backup.dump

# Restore sur Supabase
pg_restore -d "<supabase_database_url>" -n mlb --no-owner --no-acl mlb_backup.dump
```

- [ ] Vérifier dans Supabase Table Editor : `games`, `game_scores`, `players`, `gallery_players`, `card_purchase_prices`, etc.
- [ ] Créer les tables supplémentaires :

```sql
-- Profil utilisateur : lie un compte auth à un manager Sorare
CREATE TABLE mlb.user_profiles (
    user_id      UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    manager_slug TEXT NOT NULL,
    display_name TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Remises persistées par user
CREATE TABLE mlb.remises (
    user_id    UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    card_name  TEXT,
    remise_pct INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, card_name)
);
```

- [ ] Activer Row Level Security :

```sql
ALTER TABLE mlb.user_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "user sees own profile"
    ON mlb.user_profiles FOR ALL USING (auth.uid() = user_id);

ALTER TABLE mlb.remises ENABLE ROW LEVEL SECURITY;
CREATE POLICY "user sees own remises"
    ON mlb.remises FOR ALL USING (auth.uid() = user_id);
```

---

## Étape 2b — Pivot de game_score_details (cloud uniquement)

### Contexte
`game_score_details` en local = format EAV, 6.5M lignes, 1.6 GB.  
En cloud = format wide (1 ligne par player+game), ~592K lignes, ~300 MB estimé.  
**La table locale reste inchangée.**

### Schéma wide (Supabase uniquement)

```sql
CREATE TABLE mlb.game_score_details_wide (
    player_slug   TEXT        NOT NULL,
    game_date     TIMESTAMPTZ NOT NULL,
    gw_int        INTEGER,
    category      TEXT,
    -- Hitting
    hitting_singles          REAL, hitting_singles_pts          REAL,
    hitting_doubles          REAL, hitting_doubles_pts          REAL,
    hitting_triples          REAL, hitting_triples_pts          REAL,
    hitting_home_runs        REAL, hitting_home_runs_pts        REAL,
    hitting_runs             REAL, hitting_runs_pts             REAL,
    hitting_runs_batted_in   REAL, hitting_runs_batted_in_pts   REAL,
    hitting_walks            REAL, hitting_walks_pts            REAL,
    hitting_strikeouts       REAL, hitting_strikeouts_pts       REAL,
    hitting_stolen_bases     REAL, hitting_stolen_bases_pts     REAL,
    hitting_caught_stealing  REAL, hitting_caught_stealing_pts  REAL,
    hitting_hit_by_pitch     REAL, hitting_hit_by_pitch_pts     REAL,
    -- Pitching
    pitching_wins              REAL, pitching_wins_pts              REAL,
    pitching_strikeouts        REAL, pitching_strikeouts_pts        REAL,
    pitching_innings_pitched   REAL, pitching_innings_pitched_pts   REAL,
    pitching_earned_runs       REAL, pitching_earned_runs_pts       REAL,
    pitching_walks             REAL, pitching_walks_pts             REAL,
    pitching_hits_allowed      REAL, pitching_hits_allowed_pts      REAL,
    pitching_holds             REAL, pitching_holds_pts             REAL,
    pitching_saves             REAL, pitching_saves_pts             REAL,
    pitching_relief_appearance REAL, pitching_relief_appearance_pts REAL,
    pitching_hit_batsmen       REAL, pitching_hit_batsmen_pts       REAL,
    pitching_no_hitters        REAL, pitching_no_hitters_pts        REAL,
    PRIMARY KEY (player_slug, game_date, category)
);

CREATE INDEX ON mlb.game_score_details_wide (player_slug);
CREATE INDEX ON mlb.game_score_details_wide (game_date);
CREATE INDEX ON mlb.game_score_details_wide (gw_int);
```

### Script de migration initiale (local → Supabase)

Créer `scripts/migrate_gsd_pivot.py` :

```python
"""Pivote game_score_details local (EAV) → game_score_details_wide sur Supabase."""
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv("D:/git/sorare/.env")

local_engine    = create_engine(os.environ["DATABASE_URL_LOCAL"])
supabase_engine = create_engine(os.environ["DATABASE_URL_SUPABASE"])

print("Chargement local...")
df = pd.read_sql("SELECT * FROM mlb.game_score_details", local_engine)

print(f"{len(df):,} lignes → pivot...")
# Pivot stat_value
wide_val = df.pivot_table(
    index=["player_slug", "game_date", "gw_int", "category"],
    columns="stat", values="stat_value", aggfunc="first"
).reset_index()

# Pivot points
wide_pts = df.pivot_table(
    index=["player_slug", "game_date", "gw_int", "category"],
    columns="stat", values="points", aggfunc="first"
).reset_index()
wide_pts.columns = [f"{c}_pts" if c not in ("player_slug", "game_date", "gw_int", "category") else c
                    for c in wide_pts.columns]

wide = wide_val.merge(wide_pts.drop(columns=["gw_int", "category"], errors="ignore"),
                      on=["player_slug", "game_date"], how="left")

print(f"→ {len(wide):,} lignes wide")
print("Écriture Supabase...")
wide.to_sql("game_score_details_wide", supabase_engine,
            schema="mlb", if_exists="replace", index=False, chunksize=5000, method="multi")
print("Terminé.")
```

- [ ] Ajouter `DATABASE_URL_LOCAL` et `DATABASE_URL_SUPABASE` dans `.env`
- [ ] Exécuter `python scripts/migrate_gsd_pivot.py`
- [ ] Vérifier la taille dans Supabase : doit être < 400 MB
- [ ] Si > 500 MB total → envisager Supabase Pro ($25/mois, 8 GB)

### Adapter les scripts fetch pour le cloud

Les scripts `fetch_scores.py` et `fetch_gw_scores.py` écrivent en EAV en local.  
En cloud (GitHub Actions), ils doivent écrire en wide.

- [ ] Créer `scripts/fetch_scores_cloud.py` (wrapper qui pivote avant d'écrire)
- [ ] Ou ajouter une variable `WIDE_MODE=1` dans les scripts existants pour brancher sur le format wide

---

## Étape 3 — Scripts fetch : zéro changement pour le local

```bash
# .env  (local — inchangé)
DATABASE_URL_LOCAL=postgresql://...local...
DATABASE_URL=postgresql://...local...      # les scripts existants utilisent DATABASE_URL

# GitHub Secrets  (CI/CD Supabase)
DATABASE_URL=postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres
SORARE_JWT=[ton JWT personnel]
```

- [ ] Vérifier que tous les `fetch_*.py` lisent `DATABASE_URL` depuis l'environnement (pas hardcodé)

---

## Étape 4 — GitHub Actions : pipeline de données partagées

- [ ] Créer `.github/workflows/update_data.yml` :

```yaml
name: Update shared data
on:
  schedule:
    - cron: "0 7 * * *"
  workflow_dispatch:
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python update_data.py
        env:
          DATABASE_URL: ${{ secrets.SUPABASE_DATABASE_URL }}
          SORARE_JWT: ${{ secrets.SORARE_JWT }}
          WIDE_MODE: "1"
```

- [ ] Ajouter secrets GitHub : `SUPABASE_DATABASE_URL`, `SORARE_JWT`
- [ ] Tester un run manuel

---

## Étape 5 — Couche de données cloud (`data_loaders_cloud.py`)

`data_loaders.py` lit des parquets → incompatible Streamlit Cloud.  
`data_loaders_cloud.py` expose les **mêmes fonctions** mais lit depuis Supabase via SQLAlchemy.  
Les fonctions qui utilisaient `game_score_details` lisent `game_score_details_wide` et dépivotent si nécessaire (ou sont réécrites pour le format wide).

- [ ] Créer `data_loaders_cloud.py`
- [ ] Switcher dans `app.py` :

```python
import os
if os.getenv("CLOUD_MODE"):
    from data_loaders_cloud import *
else:
    from data_loaders import *
```

- [ ] Tester en local avec `CLOUD_MODE=1` et `DATABASE_URL` → Supabase

---

## Étape 6 — Auth Supabase (`auth.py`)

- [ ] `pip install supabase` → ajouter dans `requirements.txt`
- [ ] Créer `auth.py` :

```python
import os, streamlit as st
from supabase import create_client

def get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])

def require_auth():
    sb = get_supabase()
    params = st.query_params
    if "access_token" in params:
        session = sb.auth.set_session(params["access_token"], params.get("refresh_token", ""))
        st.session_state["user"] = session.user
        st.query_params.clear()
        st.rerun()
    if "user" in st.session_state:
        return st.session_state["user"]
    st.title("Sorare MLB Dashboard")
    if st.button("Se connecter avec Google"):
        r = sb.auth.sign_in_with_oauth({"provider": "google"})
        st.markdown(f'<meta http-equiv="refresh" content="0; url={r.url}">', unsafe_allow_html=True)
    st.caption("Ou")
    email = st.text_input("Email (magic link)")
    if st.button("Envoyer le lien") and email:
        sb.auth.sign_in_with_otp({"email": email})
        st.success("Lien envoyé — vérifiez votre boîte mail.")
    return None
```

- [ ] Dans `app.py` cloud : `user = require_auth()` en premier, `if not user: st.stop()`

---

## Étape 7 — Remises : JSON → Supabase (cloud uniquement)

```python
# Dans tab2_cartes.py, conditionné sur CLOUD_MODE
def load_remises_cloud(user_id, sb) -> dict:
    rows = sb.table("remises").select("card_name,remise_pct").eq("user_id", user_id).execute()
    return {r["card_name"]: r["remise_pct"] for r in rows.data}

def save_remise_cloud(user_id, card_name, remise_pct, sb):
    sb.table("remises").upsert(
        {"user_id": user_id, "card_name": card_name, "remise_pct": remise_pct}
    ).execute()
```

- [ ] Conditionner : `CLOUD_MODE` → Supabase, sinon → `data/remises.json` (inchangé)
- [ ] Tester : éditer remise → vérifier dans Supabase Table Editor

---

## Étape 8 — Déploiement Streamlit Cloud

- [ ] `st.secrets` dans Streamlit Cloud dashboard :

```toml
CLOUD_MODE       = "1"
SUPABASE_URL     = "https://[ref].supabase.co"
SUPABASE_ANON_KEY = "eyJ..."
DATABASE_URL     = "postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres"
```

- [ ] Authentication → URL Configuration dans Supabase :
  - Site URL = `https://[ton-app].streamlit.app`
  - Redirect URLs → ajouter `https://[ton-app].streamlit.app`
- [ ] Déployer → tester : login Google → galerie → remises

---

## Étape 9 — Onboarding user

```python
def check_onboarding(user_id, sb):
    result = sb.table("user_profiles").select("manager_slug").eq("user_id", user_id).execute()
    if result.data:
        return result.data[0]["manager_slug"]
    st.title("Bienvenue !")
    slug = st.text_input("Votre manager slug Sorare (ex: mon-pseudo-123)")
    if st.button("Confirmer") and slug:
        sb.table("user_profiles").insert({"user_id": user_id, "manager_slug": slug}).execute()
        st.rerun()
    return None
```

- [ ] Intégrer dans `app.py` après `require_auth()`
- [ ] Filtrer `gallery_players` sur `manager_slug` de l'user connecté

---

## Checklist finale

- [ ] Login Google fonctionne
- [ ] Magic link fonctionne
- [ ] Chaque user voit uniquement sa galerie
- [ ] Remises persistées par user dans Supabase
- [ ] `game_score_details_wide` < 400 MB dans Supabase
- [ ] Total BDD Supabase < 500 MB (free tier)
- [ ] GitHub Actions tourne chaque matin sur Supabase en format wide
- [ ] Setup local **inchangé** et fonctionnel
- [ ] Rollback testé : désactiver `CLOUD_MODE` → retour BDD locale immédiat

---

## Ordre d'exécution

| # | Étape | Durée est. |
|---|---|---|
| 1 | Créer Supabase + Google OAuth | 30 min |
| 2 | Migration BDD (sans game_score_details) | 30 min |
| 2b | Pivot game_score_details + script migration | 2h |
| 3 | Vérifier scripts fetch + variables env | 30 min |
| 4 | GitHub Actions pipeline | 1h |
| 5 | `data_loaders_cloud.py` | 2-3h |
| 6 | `auth.py` + flow Google | 1-2h |
| 7 | Remises cloud | 30 min |
| 8 | Deploy + tests | 1h |
| 9 | Onboarding | 1h |

**Total estimé : ~10h réparties sur plusieurs sessions.**

---

## Rollback

Si Supabase ne convient pas à n'importe quelle étape :
1. Supprimer `CLOUD_MODE` de l'environnement (ou mettre à `"0"`)
2. L'app reprend `data_loaders.py` + BDD locale automatiquement
3. La BDD locale n'a jamais été touchée
