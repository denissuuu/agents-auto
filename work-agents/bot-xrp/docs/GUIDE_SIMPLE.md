# Guide simple — XRP simulé

Ce bot est un exercice XRP spot avec 1 000 EUR fictifs. Il n'utilise aucune clé API et n'envoie aucun ordre.

## Voir un tick

```bash
cd /Users/juliamenard/Desktop/denis-code/work-agents/bot-xrp
PYTHONPATH=src python3 src/paper.py --once
```

La sortie indique le prix public, le cash, la quantité XRP, la valeur, les frais et les P&L. Le prix est lu en `XRPEUR` (klines publiques Binance, lecture seule) ; il n'est pas un ordre réel.

## Tester une stratégie

```bash
PYTHONPATH=src python3 src/backtest.py --public-data --interval 1d --json
```

Le signal est exécuté à la bougie suivante, avec spread, slippage et commissions. Le rapport compare la stratégie à buy-and-hold et peut être découpé en walk-forward.

## Se protéger

- `--kill` : arrêter les nouveaux achats.
- `--resume` : reprise manuelle explicite après vérification.
- Capital, frais, liquidité, stop-loss et réserves : voir `config/config.json` et `docs/STRATEGY.md`.
- Un résultat de simulation n'est pas un conseil financier.
