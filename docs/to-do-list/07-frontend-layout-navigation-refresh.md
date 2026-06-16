# Story — Layout, navigation et refresh manuel

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer l'enveloppe applicative : navigation, sélection serveur et refresh manuel.

## Pourquoi

La v1 exclut le live push. Il faut un pattern clair et commun de refresh manuel dans toute l'UI.

## Comment

Créer un layout avec sidebar/topbar, un sélecteur serveur global et un bouton `Refresh` transmis aux pages.

## Tâches

- [ ] Créer `AppLayout`.
- [ ] Ajouter navigation : Dashboard, Deals, Market, Items, Settings.
- [ ] Ajouter sélection serveur, défaut `frostreaver`.
- [ ] Ajouter bouton `Refresh`.
- [ ] Ajouter états loading/error communs.
- [ ] Conserver le serveur choisi en local storage.
- [ ] Prévoir routing frontend.

## Critères d'acceptation

- [ ] Les pages principales sont accessibles via navigation.
- [ ] Le refresh relance les requêtes sans recharger le navigateur.
- [ ] Le serveur actif est appliqué aux requêtes API.
