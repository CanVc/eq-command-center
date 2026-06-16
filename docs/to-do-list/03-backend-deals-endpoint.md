# Story — Endpoint deals et calcul discount

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer l'endpoint qui liste les annonces sous le prix marché avec un discount calculé.

## Pourquoi

La détection de deals marché est la priorité produit numéro 1. Le frontend doit recevoir une liste déjà calculée et triée.

## Comment

Joindre `market_listings` avec `market_prices` via `item_id`, puis utiliser `median_pp`, fallback `avg_pp`, fallback `p25_pp`.

## Tâches

- [x] Créer `eqmarket/api/routes/deals.py`.
- [x] Implémenter `GET /api/deals?server=frostreaver&min_discount=30&limit=100`.
- [x] Ajouter un filtre `min_price_pp`.
- [x] Ajouter une option `resolved_only`.
- [x] Calculer `market_price_pp` avec fallbacks.
- [x] Calculer `discount_pct`.
- [x] Trier par discount puis valeur potentielle.
- [x] Inclure seller, item, `price_raw` pour l'action copier tell.

## Critères d'acceptation

- [x] Aucun deal n'est retourné si prix listing ou marché est nul.
- [x] `min_discount` filtre correctement.
- [x] Chaque résultat contient item, seller, prix vu, prix marché et discount.
