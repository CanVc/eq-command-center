# Story — Setup Playwright pour tests UI

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Installer et configurer Playwright dans le frontend pour que les stories UI puissent être vérifiées dans un vrai navigateur.

## Pourquoi

Les tests unitaires ne suffisent pas pour valider les parcours utilisateur, la navigation, les états loading/error, les comportements responsives et les interactions réelles. Playwright doit devenir le socle de test navigateur avant de développer les pages applicatives.

## Comment

Ajouter Playwright au projet `web/`, créer une configuration e2e stable, définir les commandes npm de test et ajouter un premier test smoke qui valide que l'application démarre.

## Tâches

- [ ] Installer `@playwright/test` dans `web/`.
- [ ] Installer les navigateurs Playwright nécessaires.
- [ ] Créer `web/playwright.config.ts`.
- [ ] Configurer `baseURL` et `webServer` pour lancer l'app Vite automatiquement.
- [ ] Définir au moins un projet desktop Chromium et un projet mobile.
- [ ] Ajouter le script `test:e2e` dans `web/package.json`.
- [ ] Ajouter un premier test smoke dans `web/tests/e2e/`.
- [ ] Ignorer les rapports et artefacts Playwright générés si nécessaire.
- [ ] Documenter la commande de test e2e.

## Critères d'acceptation

- [ ] `npm run test:e2e` fonctionne depuis `web/`.
- [ ] Playwright lance ou réutilise le serveur frontend local automatiquement.
- [ ] Le test smoke passe sur desktop.
- [ ] Le test smoke passe sur mobile.
- [ ] Les stories UI suivantes peuvent supposer Playwright disponible.
