# Story — Fondation import inventaire personnages

- **Statut** : À faire
- **Date de création** : 2026-06-19
- **Spec liée** : [docs/data-model/data-model.sql](../data-model/data-model.sql)

## Résumé

Importer les dumps inventaire EverQuest (`<Character>_<server>-Inventory.txt`) pour alimenter l'équipement porté et une liste plate d'items possédés.

## Pourquoi

Les inventaires sont le socle nécessaire pour afficher les personnages, estimer ce qui est vendable et préparer le futur gear upgrade finder. Les dumps contiennent déjà `Location`, `Name`, `ID`, `Count` et `Slots`, donc ils peuvent être importés de façon déterministe.

## Format observé

```text
Location	Name	ID	Count	Slots
Head	Nathsar Helm	5732	1	6
General 1	Ethereal Dreamweave Satchel	52141	1	20
General 1-Slot1	Coral Crescent	25817	2	6
Bank1	Raw Hide	97860	6	6
```

Les items dont le nom finit par `*` sont des items de démarrage/no-trade. Ils doivent être conservés pour refléter l'équipement si nécessaire, mais exclus des valorisations de vente et des files de refresh prix.

## Tâches

- [ ] Ajouter les tables nécessaires au modèle, notamment `inventory_imports` et `character_inventory_items`.
- [ ] Stocker chaque import avec personnage, serveur, fichier source, hash/source, date d'import et version de parser.
- [ ] Ajouter un parser TSV dédié au format inventory dump EQ.
- [ ] Inférer `character_name` et `server` depuis le nom de fichier quand les options CLI ne sont pas fournies.
- [ ] Ajouter une commande CLI `eqmarket import-inventory --file ... --character ... --server ...`.
- [ ] Remplacer l'état courant du personnage à chaque import réussi, tout en gardant l'historique des imports.
- [ ] Importer les emplacements équipés dans `character_equipment` avec gestion des doublons (`Ear`, `Wrist`, `Fingers`).
- [ ] Importer les sacs, la banque et la shared bank dans une liste plate d'items possédés, en conservant le `raw_location` pour audit.
- [ ] Ne pas construire de modèle UI de sac/grille : les emplacements de sac sont secondaires pour le MVP.
- [ ] Parser les augment slots non vides si présents, avec lien vers la location parente ou un flag dédié.
- [ ] Ignorer les lignes `Empty` pour le stockage courant, sauf si elles sont nécessaires au rendu paperdoll.
- [ ] Détecter les items starter/no-trade via le suffixe `*`, conserver le nom brut et normaliser le nom sans l'étoile.
- [ ] Upserter des stubs dans `items` pour les `ID` absents afin que les FK d'équipement/inventaire puissent pointer vers un item connu.
- [ ] Ajouter les items non-starter à la file d'enrichissement existante ou à une file dédiée.
- [ ] Ajouter des fixtures de tests anonymisées couvrant un inventaire quasi vide et un inventaire non vide.

## Critères d'acceptation

- [ ] Le dump Nosebleed-like s'importe sans erreur même avec beaucoup d'emplacements vides.
- [ ] Le dump Dreadnought-like importe l'équipement porté, les items en sacs, la banque et la shared bank.
- [ ] Les items `*` sont marqués comme starter/no-trade et exclus des flux de vente/prix.
- [ ] Un import répété du même personnage remplace son état courant sans dupliquer les lignes courantes.
- [ ] Les `item_id` du dump sont conservés et utilisables même si Lucy n'a pas encore enrichi l'item.
