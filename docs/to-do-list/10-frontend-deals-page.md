# Story — Page Deals

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer la table dédiée aux deals classés par discount et valeur potentielle.

## Pourquoi

C'est la priorité produit numéro 1 : identifier rapidement les annonces sous-évaluées.

## Comment

Consommer `/api/deals`, afficher les colonnes clés et proposer des filtres simples.

## Tâches

- [ ] Créer `DealsPage`.
- [ ] Afficher item, prix vu, prix marché, discount, seller, date, score, actions.
- [ ] Ajouter filtres : discount min, prix min, limit, resolved only.
- [ ] Ajouter action copier tell.
- [ ] Ajouter badges visuels selon niveau de discount.
- [ ] Brancher refresh manuel.
- [ ] Utiliser `ItemLink` pour popup/détail.

## Critères d'acceptation

- [ ] Les deals sont triés et filtrables.
- [ ] Le tell copié contient seller, item et price raw.
- [ ] La table gère l'état vide proprement.
