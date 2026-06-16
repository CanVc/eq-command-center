# Story — Page Deals

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer la table dédiée aux deals classés par discount et valeur potentielle.

## Pourquoi

C'est la priorité produit numéro 1 : identifier rapidement les annonces sous-évaluées.

## Comment

Consommer `/api/deals`, afficher les colonnes clés et proposer des filtres simples.

## Tâches

- [x] Créer `DealsPage`.
- [x] Afficher item, prix vu, prix marché, discount, seller, date, score, actions.
- [x] Ajouter filtres : discount min, prix min, limit, resolved only.
- [x] Ajouter action copier tell.
- [x] Ajouter badges visuels selon niveau de discount.
- [x] Brancher refresh manuel.
- [x] Utiliser `ItemLink` pour popup/détail.

## Critères d'acceptation

- [x] Les deals sont triés et filtrables.
- [x] Le tell copié contient seller, item et price raw.
- [x] La table gère l'état vide proprement.
