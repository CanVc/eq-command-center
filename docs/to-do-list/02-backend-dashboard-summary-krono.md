# Story — Endpoints dashboard summary et Krono

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Fournir les métriques de synthèse nécessaires à la page Dashboard.

## Pourquoi

Le dashboard doit donner une vue immédiate du marché sans charger toutes les tables côté frontend.

## Comment

Ajouter des routes qui agrègent `market_listings`, `market_prices`, `krono_prices` et éventuellement `import_runs`.

## Tâches

- [x] Créer `eqmarket/api/routes/dashboard.py`.
- [x] Implémenter `GET /api/dashboard/summary?server=frostreaver`.
- [x] Implémenter `GET /api/krono/latest?server=frostreaver`.
- [x] Compter les listings récents du serveur actif.
- [x] Compter les deals récents avec le calcul discount v1.
- [x] Retourner les top items les plus vus récemment.
- [x] Retourner les top discounts récents.
- [x] Gérer le cas où `krono_prices` est vide.

## Critères d'acceptation

- [x] Le dashboard peut charger un payload unique de summary.
- [x] L'absence de prix Krono ne casse pas la réponse.
- [x] Toutes les métriques sont filtrées par serveur.
