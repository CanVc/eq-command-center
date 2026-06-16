# Story — Page Dashboard

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Construire la page d'accueil qui résume les opportunités marché.

## Pourquoi

L'utilisateur doit voir immédiatement s'il y a quelque chose d'intéressant à acheter ou surveiller.

## Comment

Consommer `/api/dashboard/summary`, afficher des cards shadcn, une table top deals et un petit bloc tendances.

## Tâches

- [x] Créer `DashboardPage`.
- [x] Afficher cards : listings récents, deals détectés, prix Krono, dernier refresh.
- [x] Afficher top discounts récents.
- [x] Afficher top items les plus vus.
- [x] Brancher le bouton refresh manuel.
- [x] Ajouter skeletons pendant chargement.
- [x] Utiliser `ItemLink` pour les noms d'items.

## Critères d'acceptation

- [x] La page charge avec des données SQLite réelles.
- [x] Le dashboard reste utilisable si certaines métriques sont vides.
- [x] Les items affichés peuvent ouvrir le détail ou le popup.
