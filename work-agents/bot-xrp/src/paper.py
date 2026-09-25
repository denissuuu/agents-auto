"""Paper trading XRP : état local et prix publics, aucun ordre réel.

Le seul accès réseau optional est la lecture de données publiques (ticker et
klines). Il n'y a ni endpoint d'ordres, ni clé API, ni dépôt/retrait.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List

try:
    from .config import load_config, validate_config, write_config
    from .portfolio import EPS, Portfolio, load_portfolio, portfolio_from_config, save_portfolio
    from .strategy import (
        decide_buy_hold_with_config, decide_sma_with_config, decide_with_config,
    )
    from . import notify
except ImportError:
    from config import load_config, validate_config, write_config
    from portfolio import EPS, Portfolio, load_portfolio, portfolio_from_config, save_portfolio
    from strategy import (
        decide_buy_hold_with_config, decide_sma_with_config, decide_with_config,
    )
    import notify

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DATA = os.path.join(ROOT, "data")
CONFIG_PATH = os.path.join(ROOT, "config", "config.json")
PORTFOLIO = os.path.join(DATA, "paper_portfolio.json")
LOG = os.path.join(DATA, "paper.log")
TRADES = os.path.join(DATA, "trades.log")


def get_context(config: Dict[str, Any]) -> List[float]:
    """Lit uniquement des klines publiques pour le calcul du signal."""
    symbol = str(config.get("symbol", "XRPEUR")).upper()
    interval = str(config.get("backtest", {}).get("interval", "1h"))
    params = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": 30})
    url = f"https://api.binance.com/api/v3/klines?{params}"
    with urllib.request.urlopen(url, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    closes = [float(row[4]) for row in payload if isinstance(row, list) and len(row) > 4]
    if not closes:
        raise RuntimeError("historique public XRP vide")
    return closes


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _load_state(config: Dict[str, Any], current_price: float) -> Portfolio:
    base = portfolio_from_config(config)
    if os.path.exists(PORTFOLIO):
        return load_portfolio(PORTFOLIO, base, reference_price=current_price)
    return base


def _fill_exit(portfolio: Portfolio, instruction: Any, price: float, timestamp: str) -> bool:
    result = portfolio.sell(
        price,
        quantity=instruction.quantity,
        timestamp=timestamp,
        exit_level=instruction.level,
    )
    return result.executed


def step(config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Exécute un tick paper complet et renvoie le snapshot du registre."""
    config = config or load_config(CONFIG_PATH)
    validate_config(config)
    os.makedirs(DATA, exist_ok=True)

    # Import tardif : le module de prix ne contient qu'un endpoint public.
    try:
        from price import get_price
    except ImportError:
        from .price import get_price

    symbol = str(config.get("symbol", "XRPEUR")).upper()
    current_price = float(get_price(symbol))
    portfolio = _load_state(config, current_price)
    # Un kill switch persisted n'est jamais réactivé implicitement ; le
    # resume est une commande explicite qui met aussi à jour la config.
    if config.get("kill_switch"):
        portfolio.set_kill_switch(True)
    now = _now()
    mode = str(config.get("strategy_mode", "sma_rsi")).lower()
    try:
        history = get_context(config)
        if mode == "sma_only":
            decision = decide_sma_with_config(history, config.get("strategy", {}))
        elif mode == "buy_hold":
            decision = decide_buy_hold_with_config(history, config.get("strategy", {}))
        else:
            decision = decide_with_config(history, config.get("strategy", {}))
        signal = decision["signal"]
        sma_fast = decision["sma_fast"]
        sma_slow = decision["sma_slow"]
        rsi_value = decision.get("rsi", 50.0)
    except (RuntimeError, ValueError, OSError, KeyError):
        history = []
        signal, sma_fast, sma_slow, rsi_value = "HOLD", 0.0, 0.0, 50.0

    executed = False
    reasons: List[str] = []
    # Les sorties de risque sont toujours évaluées, même kill switch actif.
    if signal == "SELL" and mode != "buy_hold":
        result = portfolio.sell(current_price, timestamp=now)
        if result.executed:
            executed = True
            reasons.append("signal_final")
    else:
        allowed = ("stop_loss",) if mode == "buy_hold" else None
        for instruction in portfolio.plan_exits(current_price, now):
            if allowed is not None and instruction.reason not in allowed:
                continue
            if _fill_exit(portfolio, instruction, current_price, now):
                executed = True
                reasons.append(instruction.reason)
        # buy_hold : une seule entrée, on ne ré-achète pas sans cesse (capital limité).
        if signal == "BUY" and not reasons and not (mode == "buy_hold" and portfolio.xrp > EPS):
            result = portfolio.buy(current_price, timestamp=now)
            if result.executed:
                executed = True
                reasons.append("entry")

    portfolio.mark(current_price, now)
    save_portfolio(portfolio, PORTFOLIO)
    snapshot = portfolio.snapshot(current_price)
    line = (
        f"{now} paper=1 symbol={symbol} prix={current_price:.8f} signal={signal} "
        f"SMA7={sma_fast:.8f} SMA25={sma_slow:.8f} RSI={rsi_value:.2f} "
        f"cash={snapshot['cash']:.8f} disponible={snapshot['available_cash']:.8f} "
        f"reserve_fees={snapshot['fee_reserve_cash']:.8f} xrp={snapshot['xrp']:.10f} "
        f"valeur={snapshot['portfolio_value']:.8f} fees={snapshot['total_fees']:.8f} "
        f"pnl_realise={snapshot['realized_pnl']:.8f} pnl_non_realise={snapshot['unrealized_pnl']:.8f} "
        f"kill={int(bool(snapshot['kill_switch']))} daily_halt={int(bool(snapshot['daily_halted']))}\n"
    )
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(line)
    if executed:
        block = (
            f"[{now}] paper XRP signal={signal} prix={current_price:.8f} "
            f"action={','.join(reasons)} valeur={snapshot['portfolio_value']:.8f} {config['quote_currency']}\n"
        )
        with open(TRADES, "a", encoding="utf-8") as handle:
            handle.write(block)
        try:
            notify.alert("Trade XRP simulé", f"{','.join(reasons)} — aucun ordre réel")
        except Exception:
            pass
    print(line.strip())
    return snapshot


def set_kill_switch(enabled: bool) -> None:
    config = load_config(CONFIG_PATH)
    config["kill_switch"] = bool(enabled)
    validate_config(config)
    write_config(config, CONFIG_PATH)
    if not enabled and os.path.exists(PORTFOLIO):
        # --resume est une action humaine explicite : on modifie aussi le
        # registre persistant, sans le faire lors d'un simple tick.
        state = load_portfolio(PORTFOLIO, portfolio_from_config(config))
        state.resume()
        save_portfolio(state, PORTFOLIO)
    print(f"kill_switch={int(bool(enabled))} (paper uniquement)")


def main() -> int:
    if "--kill" in sys.argv:
        set_kill_switch(True)
        return 0
    if "--resume" in sys.argv:
        set_kill_switch(False)
        return 0
    if "--once" not in sys.argv:
        print(
            "usage: paper.py --once | --kill | --resume "
            "(paper-only, aucun ordre réel)"
        )
        return 2
    try:
        step()
    except Exception as exc:
        print(f"erreur paper: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
