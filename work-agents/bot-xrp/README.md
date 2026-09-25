# Bot XRP — paper trading et backtest sans LLM

> **SIMULATION ONLY** — cette instance ne peut pas envoyer d'ordre réel, déclarer de clé API, effectuer de dépôt ou de retrait. Le mode `paper` est activé par défaut et le live est refusé.

## Objectif

Cette instance XRP spot est indépendante de `bot/`, `bot-btc/` et `bot-sol/`. Elle simule un capital de **1 000 EUR** par défaut (configurable), des quantités fractionnaires et une comptabilité FIFO. Les niveaux et risques ci-dessous sont des hypothèses discutables de test, pas des paramètres optimisés.

Les prix proviennent des klines publiques `XRPEUR` de Binance (lecture seule, aucun ordre). Le capital et les P&L sont comptabilisés dans la même devise que le prix (EUR), ce qui rend les résultats comparables à un compte XRP/EUR, sans conversion.

## Sécurité et invariants

- `config/config.json` doit contenir `mode: "paper"` et `paper: true`; toute autre valeur est refusée.
- Le code ne contient aucun endpoint d'ordres, retrait, dépôt ou gestion de clés.
- `Portfolio` refuse un achat dont le prix, les frais, le slippage, la liquidité et la réserve minima ne tiennent pas dans le cash libre.
- Les commandes en attente réservent leur cash; une autre commande ne peut pas le réutiliser.
- Le prix d'achat/simulation est ajusté du spread et du slippage; les commissions sont prélevées à l'entrée et à la sortie.
- Le kill switch bloque les nouveaux achats; les sorties de risque restent autorisées. `--resume` est une réactivation explicite.
- Les historique et données de `bot/`, `bot-btc/` et `bot-sol/` ne sont pas modifiés.

## Arborescence

```text
bot-xrp/
├── src/
│   ├── config.py       # défauts, validation et garde-fous paper-only
│   ├── portfolio.py    # registre, réserves, fills, P&L, risques/exits
│   ├── strategy.py     # SMA/RSI et comparateur SMA seul (aucun LLM)
│   ├── backtest.py     # CSV/klines publiques, bougie suivante, métriques
│   ├── paper.py        # tick paper et kill switch
│   ├── price.py        # lecture publique du ticker, sans ordre
│   ├── dashboard.py    # dashboard local
│   └── run.py          # lecture de signal paper-only
├── config/config.json
├── tests/
└── docs/
```

## Paramètres par défaut

Les paramètres sont dans `config/config.json` et sont documentés dans [`docs/STRATEGY.md`](docs/STRATEGY.md).

- Capital : `1000 EUR`, `allocation_pct: 0.20`, plafond position `25 %`, exposition totale `50 %`.
- Coûts : commission `0,1 %`, spread `0,2 %`, slippage `0,05 %`, réserve cash `50 EUR` et réserve de frais dédiée.
- Sorties : stop-loss `10 %`, puis cibles discutables `+5 %`, `+10 %`, `+20 %` avec `25 %`, `25 %`, `20 %` de la position; le reste est géré par trailing `8 %` ou durée maximale `30 jours`.
- Risque journalier : `3 %`; risque maximal d'une position : `2 %` de l'équité; durée maximale : `30 jours`.
- Liquidité : plafond `250` par trade et participation du volume configurable.

Ces valeurs protègent le simulateur ; elles ne garantissent aucun gain.

## Paper trading

Depuis `bot-xrp/` :

```bash
PYTHONPATH=src python3 src/paper.py --once
PYTHONPATH=src python3 src/paper.py --kill
PYTHONPATH=src python3 src/paper.py --resume
```

`paper.py` lit éventuellement le ticker et les klines **publiques** pour simuler un tick. Il ne passe jamais par un client d'ordres. Le registre est écrit dans `data/paper_portfolio.json` et le détail des ticks dans `data/paper.log`.

## Backtest réaliste

Le backtest est déterministe et n'effectue aucun accès réseau. Le signal de la bougie `i-1` est exécuté à l'ouverture de `i`; un stop et une cible touchés dans la même bougie donnent la priorité au stop.

Avec un CSV local (colonnes minimales `timestamp,open,high,low,close,volume`) :

```bash
PYTHONPATH=src python3 src/backtest.py --data data/xrp_history.csv
```

Pour lire des données publiques XRP sans clé ni ordre :

```bash
PYTHONPATH=src python3 src/backtest.py --public-data --symbol XRPEUR --interval 1d --json
```

Options utiles :

- `--initial-capital 1000` : change le capital de test ;
- `--strategy sma_only` : comparateur simple sans RSI ni LLM ;
- `--walk-forward --folds 3` : blocs out-of-sample, sans optimisation implicite ;
- `--output data/backtest.json` : sauvegarde du rapport ;
- `--live` : refusé volontairement.

Le rapport contient rendement net après frais, rendement `buy-and-hold`, drawdown maximal, trades/fills, taux de réussite, exposition moyenne, cash inutilisé moyen/final, frais et P&L réalisé/non réalisé. Les avertissements signalent les données manquantes, la liquidité supposée et toute non-comparabilité entre le prix utilisé et la devise de comptabilisation.

## Tests

```bash
cd bot-xrp
PYTHONPATH=src python3 -m pytest tests/ -q
```

Les tests couvrent le cash disponible, achats répétés, réservations, ventes partielles, frais, stop-loss, kill switch, exécution sur bougie suivante, walk-forward et plusieurs régimes de prix sur plusieurs mois. Les données de test sont synthétiques et ne constituent pas une preuve de performance.

## Limites avant tout usage réel

La source de prix est désormais `XRPEUR` (klines publiques Binance) : la devise du prix et la devise de comptabilisation (EUR) coïncident. Il reste à :

1. Utiliser des données historiques avec volumes, spread et Liquidité représentatifs; vérifier la qualité et les gaps.
2. Tester une optimisation walk-forward réelle, des frais variables et des scénarios de slippage/defaut de liquidité.
3. Faire relire la stratégie, la fiscalité, les risques de marché et les contrôles de conformité par des professionnels compétents.
4. Ne jamais ajouter de clé API ou un mode live à ce code sans une revue de sécurité et une autorisation explicite.

**Disclaimer :** simulation pédagogique, pas un conseil financier. Les performances passées ou simulées ne préjugent pas des résultats futurs.
