# Story — Endpoints items, prix et tooltip fallback

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Exposer les données item nécessaires à la recherche, au détail item et au fallback tooltip local.

## Pourquoi

Le popup Magelo peut échouer ou être indisponible. L'UI doit toujours pouvoir afficher les stats locales depuis SQLite.

## Comment

Lire `items`, `market_prices`, `market_listings`, et éventuellement `item_effects` / `spells` pour construire des payloads compacts.

## Tâches

- [x] Créer `eqmarket/api/routes/items.py`.
- [x] Implémenter `GET /api/items/search?q=stave`.
- [x] Implémenter `GET /api/items/{item_id}`.
- [x] Implémenter `GET /api/items/{item_id}/prices?server=frostreaver`.
- [x] Implémenter `GET /api/items/{item_id}/listings?server=frostreaver&limit=100`.
- [x] Implémenter `GET /api/items/{item_id}/tooltip?server=frostreaver`.
- [x] Ajouter fallback `GET /api/items/tooltip?name=...`.
- [x] Retourner `icon_url: null` en v1 si aucune URL stable n'est disponible.

## Critères d'acceptation

- [x] Une recherche item retourne nom et item_id.
- [x] Le tooltip local contient stats clés et derniers prix disponibles.
- [x] Un item absent retourne une 404 propre.
