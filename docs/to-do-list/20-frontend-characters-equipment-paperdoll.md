# Story — Page Characters avec paperdoll équipement

- **Statut** : Terminé
- **Date de création** : 2026-06-19
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer la page `Characters` avec une présentation de l'équipement inspirée de la fenêtre inventaire EverQuest, et une liste simple pour les sacs/banques.

## Pourquoi

L'équipement porté est plus lisible avec une disposition visuelle proche d'EQ. En revanche les sacs n'ont pas besoin d'être reproduits en grille : une liste groupée par item suffit pour l'estimation et la recherche.

## UI cible

- Colonne gauche : résumé personnage, serveur, classe/niveau si connus, dernier import, compteurs.
- Zone centrale : paperdoll équipement EQ-like.
- Zone droite ou onglets : inventaire porté/sacs/banque sous forme de liste.

## Tâches

- [x] Ajouter une route/page `Characters` dans la navigation.
- [x] Afficher la liste des personnages et sélectionner un personnage.
- [x] Construire un composant `EquipmentPaperdoll` avec les slots EQ principaux.
- [x] Gérer les slots dupliqués : oreilles, poignets, doigts.
- [x] Afficher les items équipés avec nom, icône placeholder ou icon connue, tooltip item existant si disponible.
- [x] Griser ou badger les items starter/no-trade importés avec `*`.
- [x] Afficher l'inventaire hors équipement en liste groupée par item, pas en grille de sacs.
- [x] Prévoir des onglets ou filtres `Carried`, `Bank`, `Shared Bank`, `All`.
- [x] Gérer les états vide, non importé, chargement et erreur API.
- [x] Ajouter des tests Playwright sur desktop et au moins un viewport mobile raisonnable.

## Critères d'acceptation

- [x] Un personnage importé affiche son équipement dans une vue paperdoll compréhensible.
- [x] Les sacs/banques sont consultables en liste simple.
- [x] Les items starter/no-trade sont visibles mais clairement distingués.
- [x] L'UI ne suppose pas que les données Lucy/prix sont déjà disponibles.
