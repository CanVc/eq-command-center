# Story — API Characters et inventaire courant

- **Statut** : À faire
- **Date de création** : 2026-06-19
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Exposer les personnages, leur équipement porté et leur inventaire courant via des endpoints API prêts pour l'UI.

## Pourquoi

L'UI Characters doit afficher une vue paperdoll de l'équipement et une liste simple des sacs/banques. Cette story fournit le contrat API sans encore implémenter la valorisation de vente avancée ni les recommandations d'upgrade.

## Endpoints envisagés

- `GET /api/characters`
- `GET /api/characters/{character_name}`
- `GET /api/characters/{character_name}/equipment`
- `GET /api/characters/{character_name}/inventory`
- `GET /api/characters/{character_name}/imports`

## Tâches

- [ ] Retourner la liste des personnages avec serveur, classe/niveau si connus, dernier import et compteurs simples.
- [ ] Retourner le détail d'un personnage avec métadonnées et fraîcheur d'import.
- [ ] Retourner l'équipement dans un format paperdoll stable, avec slots dupliqués indexés (`EAR_1`, `EAR_2`, `WRIST_1`, etc.).
- [ ] Inclure pour chaque item équipé les champs item utiles : `item_id`, nom, icon, flags, slot mask décodé, stats principales si connues.
- [ ] Retourner l'inventaire possédé sous forme de liste plate groupable, avec filtres `area=carried|bank|shared_bank|all`.
- [ ] Inclure les quantités cumulées par item et, si demandé, les locations brutes.
- [ ] Indiquer clairement les items starter/no-trade détectés à l'import.
- [ ] Indiquer les items non enrichis ou sans prix disponible, sans faire échouer la réponse.
- [ ] Ajouter des tests de contrat API.

## Critères d'acceptation

- [ ] L'API permet d'afficher une page Characters sans requêtes SQL côté frontend.
- [ ] L'équipement porté est stable même pour les slots dupliqués.
- [ ] Les sacs et banques sont disponibles en liste simple, sans structure de grille obligatoire.
- [ ] Les items inconnus ou non enrichis restent visibles avec leur nom brut/importé.
