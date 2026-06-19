# Story — Décodage des slot masks Lucy

- **Statut** : Terminé
- **Date de création** : 2026-06-19
- **Spec liée** : [docs/data-model/data-model.sql](../data-model/data-model.sql)

## Résumé

Normaliser la gestion des emplacements d'équipement Lucy sans transformer la valeur brute en libellé unique.

## Pourquoi

Lucy expose `slots` comme un bitmask entier. Un item peut être porté sur plusieurs emplacements à la fois, y compris des combinaisons exotiques du type `NECK + HEAD + WRIST`. L'application doit conserver cette valeur brute pour les filtres et le futur upgrade finder, tout en exposant un affichage lisible côté API/UI.

## Décisions

- La base stocke la valeur brute Lucy, pas une chaîne `PRIMARY` / `WRIST` unique.
- Le nom de colonne historique `items.slot` peut rester utilisé à court terme, mais son contenu est traité comme un slot mask numérique.
- Les libellés humains sont dérivés à l'affichage et dans les payloads API.
- Le décodage doit retourner tous les bits connus actifs, pas seulement le premier.
- Les bits inconnus ne doivent pas casser l'API : ils doivent être conservés ou exposés comme inconnus.

## Tâches

- [x] Ajouter un helper backend central pour décoder les slot masks Lucy.
- [x] Définir la correspondance connue : `CHARM`, `EAR`, `HEAD`, `FACE`, `NECK`, `SHOULDERS`, `ARMS`, `BACK`, `WRIST`, `RANGE`, `HANDS`, `PRIMARY`, `SECONDARY`, `FINGER`, `CHEST`, `LEGS`, `FEET`, `WAIST`, `POWER_SOURCE`, `AMMO`.
- [x] Gérer les slots dupliqués (`EAR`, `WRIST`, `FINGER`) sans dupliquer inutilement les labels de compatibilité.
- [x] Supporter les combinaisons multi-slots et les masques exotiques.
- [x] Exposer dans les payloads item au moins `slot_mask`, `slot_labels` et `slot_display`, tout en gardant le champ existant `slot` pour compatibilité.
- [x] Utiliser ce helper dans les endpoints item search/detail/tooltip concernés.
- [x] Ajouter des tests unitaires pour les masques simples, multi-slots et inconnus.
- [x] Ajouter des tests API vérifiant que les champs existants ne cassent pas.

## Critères d'acceptation

- [x] Un item `slots = 8192` est affiché comme `PRIMARY`.
- [x] Un item `slots = 24576` est affiché comme `PRIMARY / SECONDARY`.
- [x] Un item `slots = 1536` est affiché comme `WRIST`.
- [x] Un masque exotique retourne tous ses labels connus.
- [x] La DB conserve la valeur brute Lucy et aucun libellé multi-slot n'est persisté comme source de vérité.
