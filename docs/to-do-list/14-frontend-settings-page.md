# Story — Page Settings locale

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer une page settings minimale pour diagnostiquer l'environnement local.

## Pourquoi

Comme l'application dépend d'une DB locale, de Magelo et d'importeurs CLI, une page de statut évite de chercher les problèmes à l'aveugle.

## Comment

Afficher des infos simples retournées par l'API ou calculées côté frontend.

## Tâches

- [x] Créer `SettingsPage`.
- [x] Afficher chemin DB utilisé par l'API.
- [x] Afficher serveur par défaut / serveur actif.
- [x] Afficher statut Magelo loaded / not loaded.
- [x] Afficher dernier import TLP Auctions depuis `import_runs`.
- [x] Afficher statut API health.
- [x] Garder la page read-only en v1.

## Critères d'acceptation

- [x] L'utilisateur peut confirmer quelle DB est utilisée.
- [x] Le statut Magelo est visible.
- [x] Le dernier import TLP Auctions est visible si présent.
