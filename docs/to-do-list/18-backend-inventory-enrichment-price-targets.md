# Story — Enrichissement et prix des items d'inventaire

- **Statut** : Terminé
- **Date de création** : 2026-06-19
- **Spec liée** : [docs/data-model/data-model.sql](../data-model/data-model.sql)

## Résumé

Brancher les items importés depuis les inventaires dans les pipelines d'enrichissement Lucy et de refresh prix TLP Auctions.

## Pourquoi

L'import inventaire crée une liste d'items possédés, mais beaucoup d'entre eux peuvent n'exister que sous forme de stub local. Pour afficher les stats, détecter le no-drop réel et valoriser les sacs, il faut enrichir ces items et les considérer comme cibles de prix.

## Tâches

- [x] Ajouter une sélection des items d'inventaire non enrichis à traiter par Lucy.
- [x] Permettre l'enrichissement direct par `item_id` quand le dump fournit déjà l'ID.
- [x] Garder le fallback par nom normalisé pour les cas sans ID.
- [x] Ne pas envoyer les items starter `*` dans les refresh prix.
- [x] Importer les flags Lucy utiles (`NO_DROP`, `NO_RENT`, `MAGIC`, etc.) sur les stubs enrichis.
- [x] Étendre la sélection des cibles TLP Auctions pour inclure les items d'inventaire pertinents.
- [x] Éviter de polluer le refresh prix avec nourriture, eau, containers vides ou items explicitement ignorés quand c'est identifiable.
- [x] Exposer dans les stats de refresh le nombre d'items provenant des inventaires.
- [x] Ajouter des tests pour un item connu par ID, un item connu seulement par nom et un starter ignoré.

## Critères d'acceptation

- [x] Un item importé par `item_id` peut être enrichi depuis Lucy sans dépendre d'une recherche textuelle.
- [x] Un item d'inventaire enrichi peut recevoir un prix dans `market_prices`.
- [x] Les items starter/no-trade issus du suffixe `*` ne déclenchent pas de refresh prix.
- [x] Le comportement existant pour les listings marché reste inchangé.
