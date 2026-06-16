# Workflow de traitement des stories

Ce document décrit comment un agent doit traiter les fichiers de story du dossier `docs/to-do-list`.

## Statuts

Les statuts autorisés sont :

- `À faire` : la story est prête à être lue, mais aucun développement n'a démarré.
- `En cours` : la story est clarifiée et le développement a commencé.
- `Terminé` : toutes les tâches et tous les critères d'acceptation validables sont terminés.

Le statut d'une story est porté par la ligne :

```md
- **Statut** : À faire
```

## Processus obligatoire

1. Lire entièrement le fichier de story.
2. Lire entièrement la spec liée indiquée par `Spec liée`.
3. Lire les autres fichiers explicitement liés par la story ou nécessaires pour comprendre le périmètre : brief projet, modèle de données, code existant, scripts ou documentation pertinente.
4. Identifier les zones d'ombre avant tout développement.
5. Si une zone d'ombre existe, poser les questions nécessaires et ne pas commencer à développer.
6. Après clarification, amender la story si la réponse modifie le périmètre, les tâches ou les critères d'acceptation.
7. Passer le statut de la story à `En cours`.
8. Développer la story en restant strictement dans son périmètre.
9. Ajouter ou mettre à jour les tests adaptés au code modifié.
10. Vérifier le comportement avec les tests ou commandes adaptées.
11. Cocher uniquement les tâches et critères réellement validés.
12. Passer le statut à `Terminé` seulement quand la story est effectivement livrée.

## Règles de clarification

L'agent ne doit pas démarrer une implémentation sur une hypothèse fragile. Si une décision fonctionnelle, technique ou UX n'est pas claire, il doit poser une question avant de modifier le code.

Les clarifications doivent être reportées dans la story quand elles changent l'intention initiale. Une story clarifiée doit rester compréhensible sans relire la discussion.

## Règles de développement

Le développement commence seulement après le passage à `En cours`.

L'agent doit respecter :

- le périmètre de la story ;
- la spec liée ;
- les conventions existantes du projet ;
- le modèle de données existant ;
- les critères d'acceptation de la story.

Les refactors non nécessaires, les changements de comportement hors périmètre et les ajouts d'abstraction prématurés doivent être évités.

## Règles de tests

Tout code livré doit être accompagné de tests quand c'est possible.

Pour chaque fichier de code créé, l'agent doit créer ou mettre à jour un fichier de test correspondant, sauf si le fichier ne contient pas de logique testable. Dans ce cas, l'agent doit expliquer brièvement pourquoi aucun test unitaire n'a été ajouté.

Pour chaque fichier de code modifié, l'agent doit ajouter ou adapter les tests couvrant le comportement changé. Il ne suffit pas de vérifier manuellement une modification qui peut raisonnablement être testée automatiquement.

Les tests doivent privilégier :

- des tests unitaires pour la logique pure, les helpers, les calculs, les parseurs et les transformations ;
- des tests d'API pour les routes backend, avec base SQLite temporaire ou fixtures locales ;
- des tests d'intégration ciblés quand plusieurs modules doivent fonctionner ensemble ;
- des tests UI unitaires pour les composants, hooks ou fonctions frontend quand ils contiennent une logique vérifiable ;
- des tests Playwright pour les parcours navigateur, les pages, la navigation, les états loading/error, les interactions utilisateur et les critères d'acceptation visuels ou fonctionnels.

Playwright fait partie du socle attendu pour les stories UI. La story `07-frontend-playwright-setup.md` doit être traitée après le scaffold frontend et avant les stories UI qui nécessitent des tests navigateur.

Après cette story de setup, l'agent doit considérer Playwright comme installé et configuré. Il doit servir à vérifier l'application telle qu'un utilisateur la voit réellement, idéalement sur au moins un viewport desktop et un viewport mobile quand la story touche au layout.

Playwright ne remplace pas les tests unitaires : il les complète. Les tests unitaires restent préférés pour les règles métier, les calculs et les fonctions isolables.

Les tests ne doivent pas dépendre d'un service externe instable ni de données locales personnelles. Utiliser des fixtures, des bases temporaires ou des mocks quand c'est nécessaire.

Si un test attendu ne peut pas être ajouté dans la story, l'agent doit le signaler explicitement dans le résumé de fin avec la raison et le risque associé.

## Fin de story

Avant de passer une story à `Terminé`, l'agent doit :

- vérifier que chaque tâche cochée correspond à un changement réellement fait ;
- vérifier que chaque critère d'acceptation coché a été testé ou contrôlé ;
- vérifier que les tests pertinents existent et passent ;
- laisser non cochés les éléments non livrés ;
- résumer les vérifications effectuées ;
- signaler clairement les risques ou limites restantes.

Une story ne doit pas être marquée `Terminé` si des critères essentiels restent non validés.
