# Politique de tests

## Objectif

Garder un filet de sécurité simple mais utile pendant le développement du MVP local : API FastAPI, SQLite, parsing de logs EQ et scoring des deals.

## Règle par story

Chaque story doit ajouter ou mettre à jour :

1. des tests d'acceptation sur le comportement livré ;
2. les edge cases principaux ;
3. un test de régression pour chaque bug corrigé.

## Pyramide de tests cible

### 1. Unit tests

Pour la logique pure, rapide à tester :

- parsing des logs EQ ;
- normalisation des noms d'items ;
- parsing des prix (`4k`, `500pp`, `1 krono`, etc.) ;
- calcul de discount ;
- choix du prix de référence : `median_pp`, puis `avg_pp`, puis `p25_pp`.

### 2. Tests d'intégration SQLite/API

Pour les routes FastAPI et les requêtes SQL :

- DB temporaire créée avec le vrai `init_db` ;
- fixtures SQLite minimales par test ;
- vérification des filtres, tris, pagination et cas vides ;
- vérification des réponses propres : `400`, `404`, `503`.

### 3. Contract tests API

Le frontend dépend des payloads. Les tests doivent protéger :

- noms des champs ;
- types ;
- champs nullable (`item_id`, prix absents, `icon_url`) ;
- forme des objets imbriqués comme `item` et `spell`.

### 4. Fixtures réalistes

Les cas de parsing doivent utiliser des extraits anonymisés de logs EverQuest dans `tests/fixtures/logs/`.

Les fixtures doivent couvrir :

- annonces WTS classiques ;
- prix avec unités différentes ;
- annonces WTB ignorées ;
- annonces sans prix ;
- quantités qui ne sont pas des prix (`x4`, `x 500`) ;
- Krono.

### 5. Smoke tests locaux

Un smoke test manuel peut valider rapidement une vraie DB locale :

```bash
.venv/Scripts/python scripts/smoke_api.py --db data/eqmarket.sqlite
```

Ce test ne remplace pas les tests unitaires. Il vérifie surtout que les endpoints critiques répondent avec la DB du développeur.

## Commandes

Tests complets. Le script relance automatiquement avec `.venv/Scripts/python.exe` si le venv local existe :

```bash
python scripts/run_tests.py
```

Tests complets avec sortie détaillée :

```bash
.venv/Scripts/python scripts/run_tests.py --verbose
```

Tests complets + smoke API local :

```bash
.venv/Scripts/python scripts/run_tests.py --smoke --db data/eqmarket.sqlite
```

Smoke API local seul :

```bash
.venv/Scripts/python scripts/smoke_api.py --db data/eqmarket.sqlite
```

## Politique bugfix

Tout bug corrigé doit ajouter un test qui échouait avant la correction.

Exemples :

- duplication d'un item dans `top_seen_items` ;
- CORS bloqué pour Vite ;
- parser qui confond quantité et prix ;
- prix de marché fallback incorrect ;
- item absent qui ne retourne pas une 404 propre.
