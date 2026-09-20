---
name: Dev efficace
description: A utiliser pour toute implémentation, correction ou test : petits diffs, localisation ciblée, vérification minimale.
---

# Dev économe (Big Pickle)

## Workflow
1. Localiser avec `glob`/`grep` (motif précis), lire uniquement les sections nécessaires.
2. Implémenter le plus petit diff qui satisfait les critères d'acceptation.
3. Ne toucher que les fichiers du périmètre. Pas de refactor, pas de dépendance nouvelle sans consigne.
4. Vérifier : commande ciblée (test du fichier, build partiel). Éviter les suites complètes sauf demande.
5. Retour court : fichiers modifiés, vérifications exécutées + résultat, suite proposée.

## Anti-gaspillage
- Pas de lecture de fichiers entiers > 300 lignes : lire par plages.
- Pas de `cat`/`read` répété du même fichier.
- Préférer `edit` chirurgical à `write` complet.
- Si blocage > 10 steps : rendre la main avec diagnostic + hypothèse, ne pas boucler.
