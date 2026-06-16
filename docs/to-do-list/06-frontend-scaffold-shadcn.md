# Story — Squelette frontend Vite, Tailwind et shadcn

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer le projet frontend React TypeScript avec Tailwind et `shadcn/ui`.

## Pourquoi

Le dashboard doit être moderne, simple à maintenir et cohérent visuellement.

## Comment

Créer `web/`, initialiser Vite, configurer Tailwind, installer shadcn et les composants de base.

## Tâches

- [ ] Initialiser `web/` avec Vite React TypeScript.
- [ ] Installer Tailwind CSS.
- [ ] Initialiser `shadcn/ui`.
- [ ] Ajouter `Button`, `Card`, `Table`, `Badge`, `Select`, `Tabs`, `Skeleton`, `HoverCard`.
- [ ] Ajouter un client API dans `web/src/lib/api.ts`.
- [ ] Configurer un proxy dev vers l'API locale si nécessaire.
- [ ] Ajouter scripts `dev`, `build`, `preview`.

## Critères d'acceptation

- [ ] `npm run dev` démarre l'UI.
- [ ] Une page vide stylée shadcn s'affiche.
- [ ] Le frontend peut appeler `GET /api/health`.
