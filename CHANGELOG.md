# Changelog

Toutes les modifications notables du dépôt sont documentées ici.
Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Les versions suivent [SemVer](https://semver.org/lang/fr/).

## [Unreleased]

### Ajouté
- Tests minimaux pytest pour chaque bot (indicators : sma, rsi) dans `bot/`, `bot-sol/`, `bot-xrp/`.
- Scripts d'ops multi-bots (`start_all.sh`, `status_all.sh`).
- Instruction "Tests" dans les README des 4 bots.
- Étape de vérification syntaxe Python dans la CI.

## [1.0.0] - 2026-09-23

### Ajouté
- Bots de trading paper multi-crypto : `bot/` (base), `bot-btc/`, `bot-sol/`, `bot-xrp/` — chacun avec `src/` (price, strategy, indicators, paper, dashboard, notify, backtest, explain), config, scripts `run_once.sh` et README.
- README racine et workflow GitHub Actions (tests pytest par bot).
- Historique de développement : stratégie SMA + RSI, notification, dashboard, simulation BTC, extension SOL puis XRP.