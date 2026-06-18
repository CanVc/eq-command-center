# Story — Sync incrémental des ventes TLP Auctions

- **Statut** : Annulé / rollback fonctionnel
- **Date de création** : 2026-06-17
- **Date de rollback** : 2026-06-17
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Décision

Ne plus utiliser `TLP Auctions /api/sales` comme source de `market_listings`.

Le flux TLP Auctions a un retard observé de plusieurs minutes par rapport au chat `/auction` en jeu. Pour le use-case principal — détecter vite une opportunité et initier un trade avec un personnage connecté — ce retard rend les ventes TLP peu actionnables.

## Direction retenue

- Le **log EQ local `/auction`** reste la source temps réel prioritaire pour les opportunités.
- TLP Auctions reste utile pour :
  - les liens externes item,
  - le catalogue / item ids,
  - les prix de référence et historiques non temps réel.
- Ne plus insérer de lignes `source = 'tlp_auctions_sales'` dans `market_listings`.
- Ne plus maintenir de curseur `tlp_sales_cursor:*`.

## Rollback appliqué

- Suppression de l'importeur backend TLP sales.
- Suppression de l'endpoint/job de sync sales.
- Suppression de l'appel sales dans le refresh TLP prices.
- Nettoyage de la DB locale :
  - `market_listings.source = 'tlp_auctions_sales'`,
  - `app_settings.key LIKE 'tlp_sales_cursor:%'`,
  - `import_runs.source_name = 'tlp_auctions_sales'`.

## Note

Si on veut plus tard une source non-locale exhaustive, elle devra être traitée comme un flux d'analyse/historique, pas comme signal d'achat réactif.
