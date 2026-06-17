# Story — Page Market / Listings

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer la page d'historique brut des annonces locales.

## Pourquoi

Elle permet de vérifier ce que le parser a vu, d'auditer les prix et de retrouver une annonce ancienne.

## Comment

Consommer `/api/listings/recent`, avec recherche texte, filtre serveur et pagination simple.

## Tâches

- [x] Créer `MarketListingsPage`.
- [x] Afficher timestamp, seller, item, price raw, price pp, source, confidence, resolved.
- [x] Ajouter champ recherche texte.
- [x] Ajouter pagination ou bouton `Load more`.
- [x] Brancher refresh manuel.
- [x] Ajouter badge resolved/pending.
- [x] Utiliser `ItemLink` si `item_id` existe.

## Critères d'acceptation

- [x] Les listings récents apparaissent en ordre décroissant.
- [x] Les pending items sont visibles.
- [x] La recherche filtre item ou seller.
