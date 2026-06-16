# Story — Page Dashboard

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Construire la page d'accueil qui résume les opportunités marché.

## Pourquoi

L'utilisateur doit voir immédiatement s'il y a quelque chose d'intéressant à acheter ou surveiller.

## Comment

Consommer `/api/dashboard/summary`, afficher des cards shadcn, une table top deals et un petit bloc tendances.

## Tâches

- [ ] Créer `DashboardPage`.
- [ ] Afficher cards : listings récents, deals détectés, prix Krono, dernier refresh.
- [ ] Afficher top discounts récents.
- [ ] Afficher top items les plus vus.
- [ ] Brancher le bouton refresh manuel.
- [ ] Ajouter skeletons pendant chargement.
- [ ] Utiliser `ItemLink` pour les noms d'items.

## Critères d'acceptation

- [ ] La page charge avec des données SQLite réelles.
- [ ] Le dashboard reste utilisable si certaines métriques sont vides.
- [ ] Les items affichés peuvent ouvrir le détail ou le popup.
