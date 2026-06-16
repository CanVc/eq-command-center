# Story — Page Settings locale

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer une page settings minimale pour diagnostiquer l'environnement local.

## Pourquoi

Comme l'application dépend d'une DB locale, de Magelo et d'importeurs CLI, une page de statut évite de chercher les problèmes à l'aveugle.

## Comment

Afficher des infos simples retournées par l'API ou calculées côté frontend.

## Tâches

- [ ] Créer `SettingsPage`.
- [ ] Afficher chemin DB utilisé par l'API.
- [ ] Afficher serveur par défaut / serveur actif.
- [ ] Afficher statut Magelo loaded / not loaded.
- [ ] Afficher dernier import TLP Auctions depuis `import_runs`.
- [ ] Afficher statut API health.
- [ ] Garder la page read-only en v1.

## Critères d'acceptation

- [ ] L'utilisateur peut confirmer quelle DB est utilisée.
- [ ] Le statut Magelo est visible.
- [ ] Le dernier import TLP Auctions est visible si présent.
