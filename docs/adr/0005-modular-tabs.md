# ADR 0005 — Découpage de app.py monolithique en modules tabs/

**Status:** Accepted

## Context

`app.py` a atteint ~3800 lignes. Chaque session de développement charge l'intégralité
du fichier en contexte (pour l'IA et pour les humains), ce qui rend la navigation
difficile et consomme des tokens inutilement. Les onglets sont fonctionnellement
indépendants — il n'y a pas de raison de les maintenir dans le même fichier.

## Decision

Découper `app.py` en modules indépendants :

```
app.py                  # orchestrateur léger : config, chargement global, appel des tabs
data_loaders.py         # toutes les fonctions de chargement et constantes partagées
tabs/
  tab1_defis.py
  tab2_cartes.py
  tab3_database.py
  ...
```

Structure implémentée dans `version_claude_design/` comme branche de migration.
Chaque module de tab reçoit les données dont il a besoin via des paramètres explicites.

## Consequences

- Chaque tab est lisible et modifiable sans charger les 3800 lignes.
- `data_loaders.py` centralise les fonctions de chargement et les constantes
  partagées (FENETRE_OPTIONS, RARITY_ORDER, PARIS_TZ, etc.).
- La migration depuis `app.py` monolithique se fait progressivement —
  `version_claude_design/` coexiste avec `app.py` pendant la transition.
- Les fonctions internes à un tab (ex: `_tb_suggest` dans Tab 8) restent
  dans le fichier du tab, pas dans `data_loaders.py`.
