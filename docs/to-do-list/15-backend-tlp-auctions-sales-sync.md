# Story — Sync incrémental des ventes TLP Auctions

- **Statut** : À faire
- **Date de création** : 2026-06-17
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Passer à une source principale `TLP Auctions` pour les annonces récentes : synchroniser régulièrement les ventes WTS pricées depuis `/api/sales`, puis utiliser le log EQ local surtout comme seed/fallback.

## Pourquoi

Le log local dépend du personnage connecté et rate les annonces vues pendant les périodes offline. TLP Auctions possède déjà un flux global des annonces récentes par serveur. Avec un sync incrémental, on peut récupérer toutes les nouvelles annonces depuis le dernier refresh au lieu de se limiter arbitrairement aux 1000 dernières.

## Hypothèse API

Endpoint observé :

```text
GET https://tlp-auctions.com/api/sales?serverName=Frostreaver&page=1&pageSize=200&isBuy=false&pricedOnly=true
```

Notes :

- `pageSize` semble capé à `200` côté TLP Auctions.
- Les résultats sont renvoyés du plus récent au plus ancien.
- Les champs utiles incluent `id`, `itemId`, `item`, `auctioneer`, `transactionType`, `platPrice`, `kronoPrice`, `datetime`, `rawGuid`.
- Si un filtre `since`/`from datetime` existe côté API, l'utiliser. Sinon, paginer jusqu'à retomber avant le dernier curseur local.

## Comment

Créer un importeur `tlp_auctions_sales` incrémental :

1. Lire le curseur du dernier sync réussi par serveur : `last_datetime` + idéalement `last_id`.
2. Appeler `/api/sales` page par page avec `pageSize=200`, `isBuy=false`, `pricedOnly=true`.
3. Upsert chaque vente dans `market_listings` avec `source = 'tlp_auctions_sales'`.
4. Continuer tant que les annonces reçues sont plus récentes que le curseur précédent.
5. Stopper quand toute une page est plus ancienne/égale au curseur, avec une marge d'overlap pour les égalités de datetime.
6. Dédupliquer via `seen_hash` basé sur `tlp_sale:{server}:{id}` ou `rawGuid/itemId/datetime/price` si `id` manque.
7. Écrire un `import_runs` et mettre à jour le curseur seulement à la fin d'un run réussi.

## Tâches

- [ ] Ajouter un modèle client `TlpSale` et `TlpAuctionsClient.get_sales(...)`.
- [ ] Ajouter une fonction backend `sync_tlp_sales(db_path, server, since_cursor, max_pages)`.
- [ ] Stocker le curseur par serveur (`app_settings` ou table dédiée) : dernier `datetime` + dernier `id` traité.
- [ ] Upsert les ventes TLP dans `market_listings` sans casser les entrées `eq_log` existantes.
- [ ] Convertir les prix Krono si `kronoPrice > 0` avec le dernier prix Krono connu.
- [ ] Ajouter une route/job API pour lancer ce sync, réutilisable par l'auto-refresh 5 minutes.
- [ ] Faire utiliser ce sync par l'auto-refresh avant le refresh des prix item stale.
- [ ] Ajouter tests unitaires : pagination, arrêt sur curseur datetime, déduplication, reprise après échec.

## Critères d'acceptation

- [ ] Un refresh récupère toutes les nouvelles ventes TLP Auctions depuis le dernier sync réussi, sans limite fixe à 1000.
- [ ] `market_listings` contient les annonces TLP récentes même si aucun personnage n'était connecté.
- [ ] Relancer deux fois le sync ne crée pas de doublons.
- [ ] En cas d'échec au milieu de la pagination, le curseur n'avance pas.
- [ ] L'auto-refresh 5 minutes peut s'appuyer sur ce sync incrémental.
