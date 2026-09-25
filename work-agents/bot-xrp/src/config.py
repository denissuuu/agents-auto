"""Configuration sûre et valeurs par défaut du simulateur XRP.

Le programme est volontairement paper-only : ``paper`` doit rester vrai et
``mode`` doit valoir ``paper``. Les paramètres de marché sont des hypothèses
de simulation, pas des niveaux recommandés ou optimisés.
"""
from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "paper",
    "paper": True,
    "symbol": "XRPEUR",
    "quote_currency": "EUR",
    "price_currency": "EUR",
    "strategy_mode": "sma_rsi",
    "initial_capital": 1000.0,
    "poll_interval_sec": 60,
    "kill_switch": False,
    "strategy": {
        "fast": 7,
        "slow": 25,
        "rsi": 14,
    },
    "execution": {
        "fee_rate": 0.001,
        "spread": 0.002,
        "slippage": 0.0005,
        "max_notional_per_trade": 250.0,
        "min_notional": 5.0,
        "allocation_pct": 0.20,
        "max_position_pct": 0.25,
        "max_total_exposure_pct": 0.50,
        "min_cash_reserve": 50.0,
        "fee_reserve_multiplier": 1.10,
        "participation_rate": 1.0,
    },
    "risk": {
        "stop_loss_pct": 0.10,
        "max_daily_loss_pct": 0.03,
        "max_risk_per_position_pct": 0.02,
        "max_position_days": 30,
        "profit_levels": [0.05, 0.10, 0.20],
        "profit_fractions": [0.25, 0.25, 0.20],
        "trailing_stop_pct": 0.08,
    },
    # Mode achat-et-gardé : expose presque tout le capital en une seule
    # entrée (pas d'achats répétés qui épuisent les 1 000 EUR en frais).
    "buy_hold": {
        "allocation_pct": 0.95,
        "max_position_pct": 0.95,
        "max_total_exposure_pct": 0.95,
        "max_notional_per_trade": 1000000.0,
        "max_risk_per_position_pct": 0.10,
    },
    "backtest": {
        "interval": "1d",
        "data_file": "data/xrp_history.csv",
        "public_data": False,
        "warmup_bars": 26,
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Fusionne récursivement sans modifier les objets fournis."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: str | None = None) -> Dict[str, Any]:
    """Charge la configuration et complète les valeurs absentes."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = path or os.path.join(root, "config", "config.json")
    raw: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    return deep_merge(DEFAULT_CONFIG, raw)


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Valide les garde-fous et les paramètres de risque."""
    if config.get("paper") is not True or config.get("mode") != "paper":
        raise ValueError("Mode live interdit : conserver paper=true et mode=paper")

    symbol = str(config.get("symbol", "")).upper()
    if not symbol.startswith("XRP"):
        raise ValueError("Cette instance ne trade que XRP spot")
    strategy_mode = str(config.get("strategy_mode", "sma_rsi")).lower()
    if strategy_mode not in ("sma_rsi", "sma_only", "buy_hold"):
        raise ValueError("strategy_mode doit être sma_rsi, sma_only ou buy_hold")
    quote = str(config.get("quote_currency", "EUR")).upper()
    if not symbol.endswith(quote):
        raise ValueError(
            f"le prix {symbol} doit être libellé dans la devise de comptabilisation "
            f"{quote} (ex. XRPEUR pour EUR)"
        )

    capital = float(config.get("initial_capital", 0))
    if capital <= 0:
        raise ValueError("initial_capital doit être > 0")

    execution = config.get("execution", {})
    risk = config.get("risk", {})
    for name in ("fee_rate", "spread", "slippage", "allocation_pct",
                 "max_position_pct", "max_total_exposure_pct",
                 "min_cash_reserve", "fee_reserve_multiplier"):
        if float(execution.get(name, 0)) < 0:
            raise ValueError(f"Paramètre négatif : execution.{name}")
    if float(execution.get("spread", 0)) / 2.0 + float(execution.get("slippage", 0)) >= 1:
        raise ValueError("spread + slippage rendent la vente impossible")
    if float(execution.get("fee_rate", 0)) >= 1:
        raise ValueError("fee_rate doit être < 1")
    if float(execution.get("max_position_pct", 0)) <= 0:
        raise ValueError("max_position_pct doit être > 0")
    if float(execution.get("max_total_exposure_pct", 0)) <= 0:
        raise ValueError("max_total_exposure_pct doit être > 0")
    if float(execution.get("allocation_pct", 0)) <= 0:
        raise ValueError("allocation_pct doit être > 0")
    if float(execution.get("min_notional", 0)) < 0:
        raise ValueError("min_notional doit être >= 0")

    buy_hold = config.get("buy_hold") or {}
    for name in ("allocation_pct", "max_position_pct", "max_total_exposure_pct",
                 "max_risk_per_position_pct"):
        value = float(buy_hold.get(name, 0))
        if not 0 < value <= 1.0:
            raise ValueError(f"buy_hold.{name} doit être dans (0, 1]")
    if float(buy_hold.get("max_notional_per_trade", 0)) < 0:
        raise ValueError("buy_hold.max_notional_per_trade doit être >= 0")

    levels = list(risk.get("profit_levels", []))
    fractions = list(risk.get("profit_fractions", []))
    if len(levels) != len(fractions) or not levels:
        raise ValueError("profit_levels et profit_fractions doivent être non vides et de même longueur")
    if any(float(level) <= 0 for level in levels):
        raise ValueError("Les niveaux de profit doivent être > 0")
    if any(float(frac) < 0 or float(frac) > 1 for frac in fractions):
        raise ValueError("Les fractions de sortie doivent être dans [0, 1]")
    if sum(float(frac) for frac in fractions) > 1.0 + 1e-9:
        raise ValueError("La somme des fractions de sortie dépasse 1")
    for name in ("stop_loss_pct", "max_daily_loss_pct", "trailing_stop_pct",
                 "max_risk_per_position_pct"):
        if float(risk.get(name, 0)) < 0:
            raise ValueError(f"Paramètre négatif : risk.{name}")
    if float(risk.get("max_position_days", 0)) <= 0:
        raise ValueError("max_position_days doit être > 0")
    return config


def write_config(config: Dict[str, Any], path: str) -> None:
    """Écrit une configuration de façon atomique."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.replace(temporary)
