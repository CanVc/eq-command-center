# Story — Page Market / Listings

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer la page d'historique brut des annonces locales.

## Pourquoi

Elle permet de vérifier ce que le parser a vu, d'auditer les prix et de retrouver une annonce ancienne.

## Comment

Consommer `/api/listings/recent`, avec recherche texte, filtre serveur et pagination simple.

## Tâches

- [ ] Créer `MarketListingsPage`.
- [ ] Afficher timestamp, seller, item, price raw, price pp, source, confidence, resolved.
- [ ] Ajouter champ recherche texte.
- [ ] Ajouter pagination ou bouton `Load more`.
- [ ] Brancher refresh manuel.
- [ ] Ajouter badge resolved/pending.
- [ ] Utiliser `ItemLink` si `item_id` existe.

## Critères d'acceptation

- [ ] Les listings récents apparaissent en ordre décroissant.
- [ ] Les pending items sont visibles.
- [ ] La recherche filtre item ou seller.
