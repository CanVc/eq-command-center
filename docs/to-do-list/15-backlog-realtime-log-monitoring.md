# Story — Backlog monitoring logs temps réel

- **Statut** : À faire
- **Date de création** : 2026-06-16
- **Spec liée** : [docs/UI-spec/UI-spec.md](../UI-spec/UI-spec.md)

## Résumé

Préparer le futur monitoring temps réel des logs EQ, sans l'intégrer au MVP UI.

## Pourquoi

La v1 utilise un refresh manuel et ne lance pas le watcher log depuis le dashboard. Le temps réel est une priorité plus basse et doit rester séparé.

## Comment

Documenter l'évolution possible : lancement contrôlé du watcher, statut visible dans l'UI, puis WebSocket ou polling plus tard.

## Tâches

- [ ] Identifier les commandes CLI actuelles liées à l'import de logs.
- [ ] Définir les informations de statut à afficher : fichier log, dernier offset, dernière ligne importée.
- [ ] Prévoir une route API future pour statut watcher.
- [ ] Prévoir une action future démarrer/arrêter watcher si nécessaire.
- [ ] Reporter WebSocket/live push après le MVP refresh manuel.

## Critères d'acceptation

- [ ] Aucun comportement temps réel n'est requis pour le MVP.
- [ ] Les besoins futurs sont isolés dans cette story backlog.
