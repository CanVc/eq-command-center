# Story — Popup item Magelo et fallback local

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Afficher un tooltip item au mouseover, idéalement via Magelo, avec fallback shadcn local.

## Pourquoi

Le popup item est central pour browser les listings sans ouvrir une page détail à chaque fois.

## Comment

Reproduire l'intégration observée sur TLP Auctions : script Magelo, liens `rel="eq:item:{itemId}"`, puis `window.Magelobar.scan()`. Si Magelo n'est pas disponible, afficher un `HoverCard` local depuis l'API.

## Tâches

- [x] Charger `https://www.magelocdn.com/pack/eq/en/magelo-bar.js#3`.
- [x] Créer `ItemLink` réutilisable.
- [x] Rendre `rel="eq:item:{itemId}"` quand `item_id` existe.
- [x] Appeler `window.Magelobar?.scan?.()` après rendu des listes.
- [x] Détecter le cas Magelo non chargé.
- [x] Créer fallback `HoverCard` alimenté par `/api/items/{item_id}/tooltip`.
- [x] Afficher stats clés et prix marché dans le fallback.
- [x] Ne pas bloquer l'affichage si le tooltip échoue.

## Critères d'acceptation

- [x] Survoler un item résolu déclenche un tooltip Magelo ou local.
- [x] Les items sans item_id affichent au minimum le fallback par nom si possible.
- [x] Une panne Magelo ne casse pas la page.
