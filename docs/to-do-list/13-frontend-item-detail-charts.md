# Story — Page Item Detail et graphiques

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Créer la page détail d'un item avec stats, prix marché, historique local et graphique.

## Pourquoi

Après avoir repéré un deal ou un item intéressant, l'utilisateur doit pouvoir inspecter toutes les données disponibles.

## Comment

Consommer les endpoints item/prices/listings, puis afficher des sections shadcn et un graphique Recharts basé d'abord sur `market_listings`.

## Tâches

- [x] Créer route frontend `/items/:itemId`.
- [x] Afficher résumé item : nom, item_id, slot, classes, flags.
- [x] Afficher stats : AC, HP, Mana, Endurance, stats primaires, resists, ratio.
- [x] Afficher prix : median, p25, p75, avg, sample size, confidence.
- [x] Afficher équivalent Krono si prix Krono disponible.
- [x] Afficher historique local des listings.
- [x] Ajouter graphique prix local dans le temps.
- [x] Ajouter liens externes Lucy/Magelo/TLP Auctions si construisibles.

## Critères d'acceptation

- [x] Cliquer un item ouvre sa page détail.
- [x] La page fonctionne même si aucun prix marché n'est disponible.
- [x] Le graphique utilise les listings locaux disponibles.
