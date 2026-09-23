# Bot BTC — paper trading simulé ![SIMULATION](https://img.shields.io/badge/mode-SIMULATION-blue)

Bot pédagogique de trading simulé sur BTC/USDT (données Binance).
Aucun ordre réel n'est envoyé : portefeuille fictif de 1000 $, signaux SMA7/SMA25 + RSI, explications en français, dashboard HTML local.

## Arborescence

```
bot/
├── src/        # price, indicators, strategy, explain, notify, paper, backtest, dashboard, run
├── config/     # config.json
├── scripts/    # run_once.sh (1 itération paper + dashboard)
├── docs/       # README_RUN.md (run économe)
├── tests/      # test_price.py
└── data/       # logs, portefeuille, dashboard (gitignored, local uniquement)
```

## Démarrage rapide

```bash
python3 work-agents/bot/src/paper.py --once
python3 work-agents/bot/src/dashboard.py && open work-agents/bot/data/dashboard.html
bash work-agents/bot/scripts/run_once.sh
```

## Structure

- `src/paper.py` : simule un tick (prix → signal → portefeuille fictif → `data/paper.log`).
- `src/dashboard.py` : génère `data/dashboard.html` (badge SIMULATION).
- `src/strategy.py` + `src/indicators.py` : signal SMA/RSI ; `src/explain.py` : texte FR.
- `config/config.json` : symbole + intervalle ; `scripts/run_once.sh` : paper + dashboard.

## Tests

Lancement des tests unitaires (depuis le dossier du bot) :

```bash
PYTHONPATH=src python3 -m pytest tests/
```

## Disclaimer

Aucun gain garanti, argent fictif : ce bot est une simulation pédagogique, pas un conseil financier.
