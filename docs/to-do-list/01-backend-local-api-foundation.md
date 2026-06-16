# Story — Fondation backend local FastAPI

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Mettre en place l'API locale FastAPI qui servira les données SQLite au frontend.

## Pourquoi

L'UI doit rester 100% locale. Le navigateur ne doit pas lire SQLite directement : une API locale crée une frontière propre entre React et les données existantes.

## Comment

Créer un module `eqmarket/api/` avec une app FastAPI, un connecteur SQLite read-only en v1, et un endpoint de santé.

## Tâches

- [ ] Ajouter `fastapi` et `uvicorn` aux dépendances.
- [ ] Créer `eqmarket/api/app.py`.
- [ ] Créer `eqmarket/api/db.py` pour ouvrir SQLite avec `row_factory`.
- [ ] Forcer l'écoute locale par défaut sur `127.0.0.1`.
- [ ] Ajouter `GET /api/health`.
- [ ] Prévoir un paramètre DB path, défaut `data/eqmarket.sqlite`.
- [ ] Documenter la commande de lancement.

## Critères d'acceptation

- [ ] `GET /api/health` retourne `ok`.
- [ ] L'API démarre localement.
- [ ] Le chemin DB utilisé est visible ou loggé.
