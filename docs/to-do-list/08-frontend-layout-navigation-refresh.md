# Story — Layout, navigation et refresh manuel

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer l'enveloppe applicative : navigation, sélection serveur et refresh manuel.

## Pourquoi

La v1 exclut le live push. Il faut un pattern clair et commun de refresh manuel dans toute l'UI.

## Comment

Créer un layout avec sidebar/topbar, un sélecteur serveur global et un bouton `Refresh` transmis aux pages.

## Tâches

- [x] Créer `AppLayout`.
- [x] Ajouter navigation : Dashboard, Deals, Market, Items, Settings.
- [x] Ajouter sélection serveur, défaut `frostreaver`.
- [x] Ajouter bouton `Refresh`.
- [x] Ajouter états loading/error communs.
- [x] Conserver le serveur choisi en local storage.
- [x] Prévoir routing frontend.

## Critères d'acceptation

- [x] Les pages principales sont accessibles via navigation.
- [x] Le refresh relance les requêtes sans recharger le navigateur.
- [x] Le serveur actif est appliqué aux requêtes API.
