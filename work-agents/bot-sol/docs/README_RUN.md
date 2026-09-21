# Run économe (Mac)

## Principe
Boucle de fond légère : 1 exécution toutes les 15 s via `scripts/run_once.sh`.
Conso faible : 1 appel API / 15 s, < 1 s CPU. (launchd abandonné : refusé par macOS, erreur 78.)

## Start (1 commande)
```bash
nohup bash -c 'while true; do /bin/bash work-agents/bot/scripts/run_once.sh; sleep 15; done' > work-agents/bot/data/loop.out.log 2>&1 &
```

## Stop
```bash
pkill -f "while true; do /bin/bash.*run_once.sh" ; echo stoppé
```

## Logs
```bash
tail -f work-agents/bot/data/paper.log
```

## Dashboard
```bash
python3 work-agents/bot/src/dashboard.py && open work-agents/bot/data/dashboard.html
```

## Option
Si besoin, `poll` à 15 s dans `config/config.json` pour cohérence.
