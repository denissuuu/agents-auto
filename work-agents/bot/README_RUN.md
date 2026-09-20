# Run économe (Mac)

## Principe
Boucle de fond légère : 1 exécution toutes les 15 s via `run_once.sh`.
Conso faible : 1 appel API / 15 s, < 1 s CPU. (launchd abandonné : refusé par macOS, erreur 78.)

## Start (1 commande)
```bash
nohup bash -c 'while true; do /bin/bash work-agents/bot/run_once.sh; sleep 15; done' > work-agents/bot/loop.out.log 2>&1 &
```

## Stop
```bash
pkill -f "while true; do /bin/bash.*run_once.sh" ; echo stoppé
```

## Logs
```bash
tail -f work-agents/bot/paper.log
```

## Option
Si besoin, `poll` à 15 s dans `config.json` pour cohérence.
