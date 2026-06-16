# Story — Squelette frontend Vite, Tailwind et shadcn

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer le projet frontend React TypeScript avec Tailwind et `shadcn/ui`.

## Pourquoi

Le dashboard doit être moderne, simple à maintenir et cohérent visuellement.

## Comment

Créer `web/`, initialiser Vite, configurer Tailwind, installer shadcn et les composants de base.

## Tâches

- [x] Initialiser `web/` avec Vite React TypeScript.
- [x] Installer Tailwind CSS.
- [x] Initialiser `shadcn/ui`.
- [x] Ajouter `Button`, `Card`, `Table`, `Badge`, `Select`, `Tabs`, `Skeleton`, `HoverCard`.
- [x] Ajouter un client API dans `web/src/lib/api.ts`.
- [x] Configurer un proxy dev vers l'API locale si nécessaire.
- [x] Ajouter scripts `dev`, `build`, `preview`.

## Critères d'acceptation

- [x] `npm run dev` démarre l'UI.
- [x] Une page vide stylée shadcn s'affiche.
- [x] Le frontend peut appeler `GET /api/health`.
