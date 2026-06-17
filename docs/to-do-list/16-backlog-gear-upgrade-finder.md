# Story — Backlog gear upgrade finder

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Préparer le futur module de recherche d'upgrades d'équipement, sans le développer dans le MVP UI.

## Pourquoi

La priorité actuelle est le marché et les deals. Le gear upgrade finder reste important, mais doit être isolé pour éviter de grossir le MVP.

## Comment

Documenter les besoins et identifier les dépendances côté données : personnages, équipements, scoring profiles et prix.

## Tâches

- [ ] Lister les données nécessaires par personnage.
- [ ] Valider les tables `characters`, `character_equipment`, `scoring_profiles`.
- [ ] Définir les premiers profils : tank AC/HP, monk weapons, SK weapons.
- [ ] Définir les filtres : classe, slot, budget, serveur.
- [ ] Prévoir une page future `Gear Finder`.
- [ ] Reporter l'implémentation après le MVP deals/items.

## Critères d'acceptation

- [ ] La story reste en backlog tant que Dashboard/Deals/Items ne sont pas terminés.
- [ ] Les prérequis data sont identifiés avant implémentation.
