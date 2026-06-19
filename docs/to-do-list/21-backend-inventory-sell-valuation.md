# Story — Valorisation vente des inventaires

- **Statut** : À faire
- **Date de création** : 2026-06-19
- **Spec liée** : [docs/data-model/data-model.sql](../data-model/data-model.sql)

## Résumé

Calculer une estimation de valeur pour les items possédés en sacs/banque et fournir des statuts manuels `keep`, `sell`, `ignore`.

## Pourquoi

Une fois les inventaires importés, l'application doit aider à identifier ce qui est potentiellement vendable, combien cela vaut, et ce qui doit être conservé malgré une valeur de marché élevée.

## Règles MVP

- Exclure l'équipement porté de la liste de vente.
- Exclure les items starter/no-trade détectés via `*`.
- Exclure ou déprioriser les items `NO_DROP` connus via Lucy.
- Grouper par personnage + item, puis permettre une vue globale tous personnages.
- Utiliser les prix disponibles dans l'ordre : override manuel, `market_prices`, listings locaux récents si pertinent.
- Afficher la confiance et les items sans prix.

## Tâches

- [ ] Ajouter une table de décisions personnelles, par exemple `inventory_item_decisions`, pour `keep`, `sell`, `ignore`, notes et scope.
- [ ] Ajouter un endpoint `GET /api/characters/{character_name}/sell-candidates`.
- [ ] Ajouter un endpoint global `GET /api/inventory/sell-candidates`.
- [ ] Ajouter des endpoints pour modifier le statut manuel d'un item.
- [ ] Calculer quantité, prix unitaire estimé, valeur totale, source du prix et confiance.
- [ ] Séparer les items vendables, ignorés, à garder, no-drop probables et sans prix.
- [ ] Garder les containers/nourriture/eau hors des recommandations par défaut quand identifiable.
- [ ] Ajouter des tests pour le grouping, les exclusions starter/no-drop et les statuts manuels.

## Critères d'acceptation

- [ ] L'utilisateur peut obtenir une liste triée des items potentiellement vendables.
- [ ] Les items `*` et `NO_DROP` ne polluent pas la valeur vendable par défaut.
- [ ] Les quantités stackées sont correctement agrégées.
- [ ] Un statut manuel `keep`, `sell` ou `ignore` influence les réponses suivantes.
