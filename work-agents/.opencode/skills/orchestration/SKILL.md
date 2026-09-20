---
name: Orchestration
description: A utiliser pour toute tâche multi-étapes : cadrer, découper, déléguer à chef-projet et dev, synthétiser sans gaspiller de tokens.
---

# Orchestration économe

## Quand charger
Dès que la tâche touche plus d'un fichier ou exige cadrage + implémentation.

## Workflow
1. Reformuler la demande en 2 lignes, identifier le résultat attendu.
2. Si besoin de cadrage : subagent `chef-projet` avec objectif + contexte minimal (pas de dumps complets, que les chemins utiles).
3. Puis subagent `dev` par lot : objectif, fichiers autorisés, critères d'acceptation, interdiction de sortir du périmètre.
4. Un subagent à la fois. Paralléliser uniquement si lots sans fichiers communs.
5. Fusionner les retours en synthèse < 15 lignes.

## Anti-gaspillage
- Ne jamais relire un fichier déjà lu par un subagent : demander son résumé.
- Ne pas transmettre de gros contenus : chemins + extraits ciblés uniquement.
- Résumés exigés des subagents : fichiers, tests, blocages.
- 2 échecs sur un lot = stop + question utilisateur.
