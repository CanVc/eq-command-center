# Story — Endpoint deals et calcul discount

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer l'endpoint qui liste les annonces sous le prix marché avec un discount calculé.

## Pourquoi

La détection de deals marché est la priorité produit numéro 1. Le frontend doit recevoir une liste déjà calculée et triée.

## Comment

Joindre `market_listings` avec `market_prices` via `item_id`, puis utiliser `median_pp`, fallback `avg_pp`, fallback `p25_pp`.

## Tâches

- [ ] Créer `eqmarket/api/routes/deals.py`.
- [ ] Implémenter `GET /api/deals?server=frostreaver&min_discount=30&limit=100`.
- [ ] Ajouter un filtre `min_price_pp`.
- [ ] Ajouter une option `resolved_only`.
- [ ] Calculer `market_price_pp` avec fallbacks.
- [ ] Calculer `discount_pct`.
- [ ] Trier par discount puis valeur potentielle.
- [ ] Inclure seller, item, `price_raw` pour l'action copier tell.

## Critères d'acceptation

- [ ] Aucun deal n'est retourné si prix listing ou marché est nul.
- [ ] `min_discount` filtre correctement.
- [ ] Chaque résultat contient item, seller, prix vu, prix marché et discount.
