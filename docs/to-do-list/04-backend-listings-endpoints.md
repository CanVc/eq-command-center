# Story — Endpoints listings et recherche marché

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Exposer l'historique des annonces locales pour la page Market / Listings.

## Pourquoi

Cette page sert au debug, à l'audit des logs EQ et à la navigation dans l'historique brut.

## Comment

Lire `market_listings` avec filtres serveur, texte, limite et pagination simple.

## Tâches

- [ ] Créer `eqmarket/api/routes/listings.py`.
- [ ] Implémenter `GET /api/listings/recent?server=frostreaver&limit=100`.
- [ ] Ajouter recherche texte sur item et seller.
- [ ] Retourner timestamp, seller, item, prix raw, prix pp, source, confidence.
- [ ] Indiquer le statut résolu via `item_id IS NOT NULL`.
- [ ] Prévoir pagination `limit` + `offset`.
- [ ] Trier par timestamp descendant.

## Critères d'acceptation

- [ ] La page Market peut afficher les dernières annonces.
- [ ] La recherche fonctionne sur item et vendeur.
- [ ] Les listings non résolus restent visibles.
