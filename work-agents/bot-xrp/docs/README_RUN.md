# Run paper XRP économe

Ce dossier est une simulation locale. `paper.py` ne contient aucun ordre réel et `run.py` refuse le mode continu.

## Un tick

```bash
cd /Users/juliamenard/Desktop/denis-code/work-agents/bot-xrp
PYTHONPATH=src python3 src/paper.py --once
```

Le tick peut lire le ticker/klines publics pour calculer un signal. En cas d'échec réseau, il n'effectue pas d'achat. Les fichiers locaux sont `data/paper_portfolio.json`, `data/paper.log` et `data/trades.log`.

## Kill switch

```bash
PYTHONPATH=src python3 src/paper.py --kill
# après vérification manuelle uniquement :
PYTHONPATH=src python3 src/paper.py --resume
```

`--kill` bloque les achats; les sorties de risque restent possibles. `--resume` est explicite.

## Backtest hors réseau

```bash
PYTHONPATH=src python3 src/backtest.py --data data/xrp_history.csv --json
PYTHONPATH=src python3 src/backtest.py --walk-forward --folds 3 --json
```

Si le fichier local manque, le programme propose `--public-data`, qui lit uniquement les klines publiques XRPEUR. Cette option ne peut passer aucun ordre et ne lit aucune clé.

## Stop

Il n'y a pas de boucle launchd à démarrer. Ne pas lancer de trading réel.
