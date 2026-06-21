# Story — Gear upgrade finder dans Characters

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Date de réalisation** : 2026-06-21
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Implémenter une première version du module de recherche d'upgrades d'équipement directement dans la page `Characters`, sous forme d'onglet `Upgrades` lié au personnage sélectionné.

## Pourquoi

Le gear upgrade finder dépend des imports inventaire, du paperdoll équipement, de la résolution des items, des prix et des décisions personnelles `keep/sell/ignore`. Les stories 16 à 22 sont maintenant terminées, donc le finder peut comparer l'équipement porté, les items possédés et le marché pour un personnage donné.

## Décision UX

L'upgrade est directement lié à un personnage. La v1 doit donc être un onglet `Upgrades` dans `Characters`, pas une page globale séparée.

## Dépendances

- Story 16 — Décodage des slot masks Lucy. Terminé.
- Story 17 — Fondation import inventaire personnages. Terminé.
- Story 18 — Enrichissement et prix des items d'inventaire. Terminé.
- Story 19 — API Characters et inventaire courant. Terminé.
- Story 20 — Page Characters avec paperdoll équipement. Terminé.
- Story 21 — Valorisation vente des inventaires. Terminé.
- Story 22 — UI Sell Inventory. Terminé.

## Tâches

- [x] Ajouter un endpoint `GET /api/characters/{character_name}/upgrades`.
- [x] Utiliser le slot mask Lucy comme source de compatibilité item/slot, pas un libellé unique.
- [x] Définir les premiers profils : `auto`, `tank`, `monk`, `sk`.
- [x] Définir les filtres : slot, budget, source `owned|market|all`, profil.
- [x] Inclure les candidats provenant des sacs/banques possédés, des listings locaux et des prix TLP Auctions.
- [x] Afficher les deltas par slot : AC, HP, mana, resists, ratio arme, coût, source.
- [x] Ajouter un onglet `Upgrades` dans `Characters`.
- [x] Ajouter les tests API, frontend helper et Playwright nécessaires.

## Critères d'acceptation

- [x] Un personnage importé peut voir des candidats d'upgrade par slot.
- [x] Les candidats incompatibles avec le slot ou la classe ne sont pas proposés.
- [x] Les items possédés, les listings locaux et les références marché peuvent apparaître avec une source explicite.
- [x] Les filtres slot, budget, source et profil changent la réponse affichée.
- [x] Le scoring compare équipement actuel, items possédés et marché sans ambiguïté de slot.
