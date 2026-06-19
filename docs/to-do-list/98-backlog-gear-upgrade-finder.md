# Story — Backlog gear upgrade finder

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Préparer le futur module de recherche d'upgrades d'équipement, sans le développer tant que le socle inventaire/personnages n'est pas livré.

## Pourquoi

Le gear upgrade finder reste important, mais il dépend maintenant explicitement des imports inventaire, du paperdoll équipement, de la résolution des items, des prix et des décisions personnelles `keep/sell/ignore`. Le garder en backlog évite de construire un scoring sur des données incomplètes.

## Position dans le backlog

Cette story est volontairement déplacée en `98` parce qu'elle est régulièrement repoussée derrière des fondations plus urgentes. Elle doit être reprise après les stories inventaire/personnages.

## Dépendances

- Story 16 — Décodage des slot masks Lucy.
- Story 17 — Fondation import inventaire personnages.
- Story 18 — Enrichissement et prix des items d'inventaire.
- Story 19 — API Characters et inventaire courant.
- Story 20 — Page Characters avec paperdoll équipement.
- Story 21 — Valorisation vente des inventaires.
- Story 22 — UI Sell Inventory.

## Tâches

- [ ] Lister les données nécessaires par personnage une fois les imports inventaire disponibles.
- [ ] Valider les tables `characters`, `character_equipment`, `scoring_profiles` et les nouvelles tables d'inventaire.
- [ ] Utiliser le slot mask Lucy comme source de compatibilité item/slot, pas un libellé unique.
- [ ] Définir les premiers profils : tank AC/HP/resists, monk weapons, SK weapons.
- [ ] Définir les filtres : personnage, classe, slot, budget, serveur, source `owned|market|all`.
- [ ] Inclure les candidats provenant des sacs/banques possédés, des listings locaux et des prix TLP Auctions.
- [ ] Afficher les deltas par slot : AC, HP, mana, resists, ratio arme, coût, source.
- [ ] Prévoir une page future `Gear Finder` ou un onglet `Upgrades` dans `Characters`.
- [ ] Reporter l'implémentation tant que les dépendances inventaire ne sont pas terminées.

## Critères d'acceptation

- [ ] La story reste en backlog tant que les stories 16 à 22 ne sont pas terminées.
- [ ] Les prérequis data sont identifiés avant implémentation.
- [ ] Le futur scoring peut comparer équipement actuel, items possédés et marché sans ambiguïté de slot.
