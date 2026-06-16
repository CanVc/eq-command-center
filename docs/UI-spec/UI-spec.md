# EQ Command Center — UI Dashboard Spec

## 1. Décisions validées

- **Mode d'exécution** : 100% local pour l'instant.
- **Refresh** : manuel pour l'instant. Pas de WebSocket / live push en v1.
- **UI cible** : dashboard simple, joli, inspiré de TLP Auctions, basé sur `shadcn/ui`.
- **Priorités produit** :
  1. détection deals marché ;
  2. browsing items / stats ;
  3. gear upgrade finder ;
  4. monitoring logs temps réel.
- **Popup item** : afficher au mouseover la description/stats de l'objet et l'icône si possible. Fallback accepté : description/stats sans icône.

---

## 2. Stack proposée

### Frontend

- React + Vite + TypeScript
- Tailwind CSS
- `shadcn/ui`
- Recharts via les composants Chart shadcn
- TanStack Query optionnel, mais utile pour gérer le refresh manuel proprement

### Backend local

- FastAPI exposé uniquement en local : `127.0.0.1`
- SQLite existante : `data/eqmarket.sqlite`
- Lecture seule en v1 côté UI, sauf actions explicites futures comme watchlist/manual override.

### Structure cible

```text
eq-command-center/
  eqmarket/
    api/
      app.py
      db.py
      routes/
        dashboard.py
        deals.py
        items.py
        listings.py
        prices.py
  web/
    src/
      components/
      pages/
      lib/
      App.tsx
    package.json
```

---

## 3. Contraintes v1

- Local only : l'API écoute sur `127.0.0.1`, pas `0.0.0.0` par défaut.
- Refresh manuel : bouton `Refresh` sur les pages principales.
- Ne pas scraper TLP Auctions depuis le navigateur.
- Utiliser les données déjà importées en SQLite via `eqmarket import-tlp-prices`.
- Le dashboard ne lance pas encore le watcher log en arrière-plan.
- Pas d'authentification nécessaire tant que c'est local only.

---

## 4. Pages v1

### 4.1 Dashboard principal

Objectif : voir immédiatement s'il y a des opportunités.

Widgets :

- Listings récents sur le serveur actif.
- Nombre de deals détectés.
- Prix Krono actuel.
- Top discounts récents.
- Items les plus vus récemment.
- Petit graphique prix / temps pour l'item sélectionné ou pour les meilleurs deals.

Composants shadcn :

- `Card`
- `Table`
- `Badge`
- `Button`
- `Tabs`
- `Select`
- `Skeleton`
- `Tooltip` / `HoverCard`

Actions :

- bouton `Refresh` ;
- choix du serveur, défaut `frostreaver` ;
- clic item => page détail item ;
- mouseover item => popup item.

---

### 4.2 Page Deals

Objectif : classer les annonces intéressantes.

Table :

| Colonne | Description |
|---|---|
| Item | Nom + popup mouseover |
| Prix vu | `market_listings.price_pp` |
| Prix marché | `market_prices.median_pp`, ou override manuel plus tard |
| Discount | écart en % |
| Seller | vendeur |
| Date | timestamp listing |
| Score | `listing_scores.deal_score` si disponible, sinon calcul API |
| Actions | copier tell, ouvrir détail item |

Filtres :

- serveur ;
- discount minimum ;
- prix minimum ;
- limit ;
- seulement items résolus / tous.

Action pratique :

```text
/tell {seller} Hi, still selling {item_name} for {price_raw}?
```

---

### 4.3 Page Market / Listings

Objectif : historique brut et debug des annonces EQ logs.

Colonnes :

- timestamp ;
- seller ;
- item ;
- prix raw ;
- prix pp ;
- source ;
- confidence ;
- statut résolu / pending.

Actions :

- recherche texte ;
- filtre serveur ;
- bouton refresh ;
- clic item => détail item.

---

### 4.4 Page Item Detail

Objectif : tout voir sur un item.

Sections :

- résumé item : nom, item_id, slots, classes, flags ;
- stats : AC, HP, Mana, Endurance, stats primaires, resists, damage/delay/ratio, haste ;
- effets item si présents ;
- prix marché : médiane, p25, p75, avg, sample size, confidence ;
- Krono equivalent ;
- historique local des listings ;
- sources : Lucy/Magelo/TLP Auctions si liens disponibles ;
- graphique prix local dans le temps.

Note v1 : l'historique TLP Auctions externe n'est pas forcément persisté en DB. Le graphique v1 peut donc utiliser d'abord `market_listings`. Une v1.1 pourra ajouter une table de cache pour les points d'historique TLP.

---

## 5. Popup item / Magelo

### 5.1 Comportement souhaité

Au mouseover sur un nom d'item :

- afficher la description/stats de l'objet ;
- afficher l'icône si possible ;
- sinon afficher uniquement les stats locales ;
- ne pas bloquer la table si Magelo ne répond pas.

### 5.2 Fonctionnement observé sur TLP Auctions

La page TLP Auctions charge le script Magelo :

```html
<script type="text/javascript" src="https://www.magelocdn.com/pack/eq/en/magelo-bar.js#3"></script>
```

Dans le bundle TLP Auctions, les liens item sont rendus avec :

```html
<a href="#" rel="eq:item:{itemId}">Item Name</a>
```

Puis le frontend appelle :

```js
window.Magelobar?.scan?.()
```

Conclusion : pour reproduire le comportement TLP Auctions, la v1 peut essayer la même intégration native Magelo.

### 5.3 Implémentation proposée

Créer un composant `ItemLink` :

```tsx
<a
  href="#"
  rel={itemId ? `eq:item:${itemId}` : undefined}
  onClick={...}
>
  {name}
</a>
```

Après rendu ou refresh de table :

```tsx
useEffect(() => {
  const timer = setTimeout(() => {
    window.Magelobar?.scan?.()
  }, 100)

  return () => clearTimeout(timer)
}, [items])
```

### 5.4 Fallback local

Si l'objet n'a pas d'`item_id`, ou si Magelo ne charge pas :

- utiliser `HoverCard` shadcn ;
- appeler `GET /api/items/{item_id}/tooltip` ou `GET /api/items/tooltip?name=...` ;
- afficher les stats SQLite disponibles.

Payload tooltip proposé :

```json
{
  "item_id": 10895,
  "name": "Stave of Shielding",
  "icon_url": null,
  "slot": "PRIMARY",
  "classes": "...",
  "ac": 0,
  "hp": 0,
  "mana": 0,
  "damage": 12,
  "delay": 30,
  "ratio": 0.4,
  "flags": "MAGIC",
  "market_price_pp": 50000,
  "last_seen_pp": 42000
}
```

Icône :

- v1 : laisser Magelo gérer si son tooltip natif marche ;
- fallback : afficher stats sans icône ;
- v1.1 : ajouter un cache backend d'icônes si on identifie une URL stable.

---

## 6. API backend v1

Endpoints minimum :

```text
GET /api/health
GET /api/dashboard/summary?server=frostreaver
GET /api/listings/recent?server=frostreaver&limit=100
GET /api/deals?server=frostreaver&min_discount=30&limit=100
GET /api/items/search?q=stave
GET /api/items/{item_id}
GET /api/items/{item_id}/prices?server=frostreaver
GET /api/items/{item_id}/listings?server=frostreaver&limit=100
GET /api/items/{item_id}/tooltip?server=frostreaver
GET /api/krono/latest?server=frostreaver
```

### Calcul deal v1

Source :

- listing : `market_listings.price_pp`
- référence marché : `market_prices.median_pp`, fallback `avg_pp`, fallback `p25_pp`

Formule simple :

```text
discount_pct = 100 * (market_price_pp - listing_price_pp) / market_price_pp
```

Un deal est affiché si :

```text
listing_price_pp > 0
market_price_pp > 0
discount_pct >= min_discount
```

---

## 7. Intégration TLP Auctions

Utilisation v1 :

- import côté CLI existant : `eqmarket import-tlp-prices` ;
- affichage des données stockées dans `market_prices` et `krono_prices` ;
- liens externes possibles vers TLP Auctions avec query item.

À éviter en v1 :

- dépendre du site TLP Auctions à chaque refresh UI ;
- scraper le HTML depuis le navigateur ;
- stocker trop de données externes sans cache clair.

Graphiques inspirés TLP Auctions :

- courbe prix local dans le temps ;
- médiane/p25/p75 sous forme de petites cards ;
- volume d'annonces local ;
- équivalent Krono.

---

## 8. Navigation proposée

```text
Dashboard
Deals
Market
Items
Settings
```

`Settings` v1 peut rester minimal :

- DB path affiché ;
- serveur par défaut ;
- statut Magelo loaded / not loaded ;
- dernier import TLP Auctions depuis `import_runs`.

---

## 9. Phases d'implémentation

### Phase 1 — Backend local

- Ajouter FastAPI.
- Ajouter connecteur SQLite read-only.
- Implémenter health, summary, listings, deals, item tooltip.

### Phase 2 — Squelette frontend

- Vite React TypeScript.
- Tailwind + shadcn.
- Layout app + sidebar/topbar.
- Page Dashboard avec cards et table deals.

### Phase 3 — Deals et listings

- Page Deals complète.
- Page Market/Listings.
- Refresh manuel.
- Filtres simples.

### Phase 4 — Popup item

- Intégration Magelo native : script + `rel="eq:item:{itemId}"` + `Magelobar.scan()`.
- Fallback `HoverCard` local depuis SQLite.

### Phase 5 — Item detail + graphiques

- Page détail item.
- Graphique prix local.
- Cards prix marché / Krono.

---

## 10. Critères d'acceptation MVP

- Lancer l'API localement et ouvrir le dashboard dans le navigateur.
- Voir les derniers listings depuis SQLite.
- Voir une liste de deals avec discount calculé.
- Rafraîchir manuellement les données via bouton.
- Survoler un item résolu et obtenir un tooltip Magelo ou un fallback local.
- Ouvrir une page détail item avec stats et historique local.
- Tout fonctionne sans exposer l'API sur le réseau local.
