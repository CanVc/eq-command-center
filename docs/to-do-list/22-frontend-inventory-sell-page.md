# Story — UI Sell Inventory

- **Statut** : À faire
- **Date de création** : 2026-06-19
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Ajouter une vue UI pour consulter les items vendables issus des inventaires, leur valeur estimée et leur statut manuel.

## Pourquoi

La valorisation backend n'est utile que si elle permet rapidement de décider quoi vendre, quoi garder et quels items manquent de prix.

## Tâches

- [ ] Ajouter un onglet `Sell` dans le détail personnage ou une page dédiée accessible depuis `Characters`.
- [ ] Afficher une table triable : item, quantité, personnage, zone, prix unitaire, valeur totale, confiance, source du prix, statut.
- [ ] Ajouter des filtres : personnage, zone, statut, avec prix/sans prix, no-drop probable.
- [ ] Ajouter les actions `keep`, `sell`, `ignore` et édition de note si le backend le permet.
- [ ] Afficher un résumé : valeur totale estimée, valeur vendable, items sans prix, items exclus.
- [ ] Permettre une vue globale tous personnages.
- [ ] Réutiliser les composants item tooltip/liens existants.
- [ ] Ajouter des tests Playwright pour tri, filtre et changement de statut.

## Critères d'acceptation

- [ ] L'utilisateur voit immédiatement les items les plus intéressants à vendre.
- [ ] Les items exclus/no-drop/starter ne sont pas mélangés aux candidats vendables par défaut.
- [ ] Les statuts manuels sont visibles et persistants après refresh.
- [ ] La vue reste utilisable même quand beaucoup d'items n'ont pas encore de prix.
