# Paramètres de la stratégie XRP (hypothèses de test)

Ces valeurs sont configurables dans `config/config.json`. Elles ont été choisies pour rendre le comportement testable et lisible ; elles ne sont pas présentées comme optimales.

## Entrée

- SMA rapide : 7 bougies.
- SMA lent : 25 bougies.
- RSI : 14 bougies, filtre d'achat sous 70 et filtre de vente au-dessus de 30.
- Le signal n'est jamais calculé avec une clôture future. En backtest, il est exécuté à l'ouverture de la bougie suivante.
- Le comparateur `sma_only` ne contient ni RSI ni LLM.

## Exécution et capital

- Capital initial : `1000 EUR` (configurable).
- Allocation cible d'un nouvel achat : `20 %` de l'équité.
- Plafond d'une position : `25 %`; plafond d'exposition totale : `50 %`.
- Commission : `0,1 %` à l'achat et à la vente.
- Spread : `0,2 %`, slippage : `0,05 %`.
- Réserve cash minimale : `50 EUR`; une réserve de frais de sortie est calculée et soustraite du cash disponible.
- Un achat explicite trop grand est refusé sans modifier le registre. Une commande réservée réduit le cash disponible jusqu'à son annulation/fill.

## Sorties et risque

| Paramètre | Défaut | Rôle |
|---|---:|---|
| `max_risk_per_position_pct` | 2 % de l'équité | risque notionnel maximal, converti via le stop |
| `stop_loss_pct` | 10 % | sortie complète de la position sous le seuil |
| niveau 1 | +5 % | vendre 25 % |
| niveau 2 | +10 % | vendre 25 % |
| niveau 3 | +20 % | vendre 20 % |
| reste | 30 % | trailing stop ou durée maximale |
| `trailing_stop_pct` | 8 % | sortie du reste après le niveau 3 |
| `max_position_days` | 30 jours | sortie forcée à échéance |
| `max_daily_loss_pct` | 3 % | bloque les nouveaux achats pour la journée |

Les sorties sont fractionnaires. Une vente crédite le cash **après frais** et le prochain achat ne peut utiliser que ce cash effectivement libéré. Si le stop et une cible sont touchés dans la même bougie de backtest, le stop est prioritaire pour ne pas donner un avantage artificiel.

## Limites

- Le prix et la comptabilité sont en EUR (`XRPEUR`, klines publiques Binance) ; la validité d'un résultat reste bornée par la qualité des données et les hypothèses de frais/liquidité.
- `strategy_mode` (défaut `buy_hold`) peut passer à `sma_rsi` ou `sma_only`. `buy_hold` : une seule entrée en tendance haussière exposant ~95 % du capital (pas d'achats répétés), la seule vente est le stop-loss. Conséquence : drawdown potentiellement élevé (72 % sur 999 jours XRP/EUR), à comparer au buy-and-hold pur (+137,7 % vs +61,8 % net).
- Un volume absent signifie qu'aucun plafond de volume ne peut être vérifié.
- Le slippage est déterministe, pas un modèle probabiliste d'impact de marché.
- Le walk-forward ne réoptimise pas automatiquement les paramètres ; il met en évidence la stabilité hors échantillon.
