# Story — Monitoring logs EQ temps réel

- **Statut** : Terminé
- **Date de création** : 2026-06-16
- **Date de réalisation** : 2026-06-17
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Ajouter un watcher backend léger qui lit très régulièrement le log EverQuest configuré et alimente `market_listings` avec les nouvelles lignes `/auction` locales.

## Pourquoi

Les opportunités exploitables doivent venir du chat en jeu, avec un personnage connecté. Le flux TLP Auctions sales est trop en retard pour servir de signal temps réel. Le log local redevient donc la source actionnable principale.

## Comportement

- Le backend démarre un watcher `eq-log-watcher` au lancement de l'API.
- Le watcher relit le chemin sauvegardé via Settings.
- Si le fichier n'a jamais été importé, il démarre à la fin du fichier pour éviter un backfill massif au démarrage.
- Ensuite il poll environ toutes les secondes et importe les nouvelles lignes `/auction` via l'importeur incrémental existant.
- Le serveur est inféré depuis le nom `eqlog_<character>_<server>.txt`, avec fallback `frostreaver`.
- L'état runtime expose : watcher, dernière vente lue, offset, et volume du dernier poll.

## UI

Le header affiche maintenant :

- le nombre approximatif d'items locaux dont le prix TLP est manquant/stale ;
- la dernière date de vente `/auction` lue depuis le log EQ.

## Tâches

- [x] Identifier les commandes CLI actuelles liées à l'import de logs.
- [x] Ajouter un watcher backend contrôlé par le lifespan FastAPI.
- [x] Démarrer un nouveau log à EOF pour éviter un vieux backfill automatique.
- [x] Exposer une route `/api/runtime/status`.
- [x] Afficher dans l'UI la dernière vente log et le backlog d'items stale.
- [x] Garder le refresh prix item séparé du watcher log.

## Critères d'acceptation

- [x] Les nouvelles lignes `/auction` locales alimentent `market_listings` sans refresh manuel.
- [x] Le watcher n'importe pas tout un vieux log au premier démarrage.
- [x] L'UI donne une indication du retard prix item et de la dernière vente log lue.
