"""Backtest XRP sans look-ahead, avec coûts et registres paper.

Le signal de la bougie ``i`` est calculé avec les clôtures jusqu'à ``i-1`` puis
exécuté à l'ouverture de ``i``. Les stops/take-profit intrabougie sont simulés
de façon conservatrice : si le stop et une cible sont tous deux touchés dans
la même bougie, le stop est prioritaire.
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from .config import load_config, validate_config
    from .portfolio import EPS, ExitInstruction, Portfolio, portfolio_from_config
    from .strategy import decide_buy_hold_with_config, decide_sma_with_config, decide_with_config
except ImportError:
    from config import load_config, validate_config
    from portfolio import EPS, ExitInstruction, Portfolio, portfolio_from_config
    from strategy import decide_buy_hold_with_config, decide_sma_with_config, decide_with_config

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DEFAULT_DATA = os.path.join(ROOT, "data", "xrp_history.csv")
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class BacktestResult:
    strategy: str
    initial_capital: float
    end_value: float
    net_return_pct: float
    buy_hold_return_pct: float
    max_drawdown_pct: float
    trades: int
    fills: int
    win_rate_pct: float
    average_exposure_pct: float
    cash_unused_avg: float
    cash_unused_end: float
    total_fees: float
    realized_pnl: float
    unrealized_pnl: float
    data_start: str
    data_end: str
    candle_count: int
    warnings: List[str]
    equity_curve: List[float]
    fills_log: List[Dict[str, Any]]
    signal_count: int
    out_of_sample: bool = False
    simple_strategy_return_pct: Optional[float] = None
    simple_strategy_max_drawdown_pct: Optional[float] = None

    def as_dict(self, include_curve: bool = True) -> Dict[str, Any]:
        data = asdict(self)
        if not include_curve:
            data.pop("equity_curve", None)
            data.pop("fills_log", None)
        return data


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _parse_timestamp(value: Any, index: int = 0) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"timestamp manquant ligne {index + 2}")
    try:
        numeric = float(text)
        # Binance et la plupart des CSV utilisent des millisecondes.
        if numeric > 10_000_000_000:
            numeric /= 1000.0
        parsed = dt.datetime.fromtimestamp(numeric, tz=dt.timezone.utc)
        return parsed.replace(microsecond=0).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"timestamp invalide ligne {index + 2}: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()


def _row_value(row: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def load_candles(path: str, return_warnings: bool = False) -> List[Candle] | Tuple[List[Candle], List[str]]:
    """Charge un CSV OHLCV local ; aucune donnée n'est téléchargée."""
    warnings: List[str] = []
    candles: List[Candle] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV sans en-tête")
        missing_volume = False
        for index, row in enumerate(reader):
            try:
                timestamp = _parse_timestamp(
                    _row_value(row, "timestamp", "time", "date", "datetime"), index
                )
                open_price = _number(_row_value(row, "open", "o"), 0)
                high = _number(_row_value(row, "high", "h"), 0)
                low = _number(_row_value(row, "low", "l"), 0)
                close = _number(_row_value(row, "close", "c"), 0)
                volume_value = _row_value(row, "volume", "vol", "v")
                volume = _number(volume_value, 0)
                if volume_value in (None, ""):
                    missing_volume = True
                if min(open_price, high, low, close) <= 0:
                    raise ValueError("prix OHLC non positif")
                if high < max(open_price, close, low) or low > min(open_price, close, high):
                    raise ValueError("cohérence OHLC invalide")
                candles.append(Candle(timestamp, open_price, high, low, close, volume))
            except ValueError as exc:
                warnings.append(f"ligne ignorée ({exc})")
        if missing_volume:
            warnings.append("volume absent : hypothèse de liquidité sans plafond par volume")
    if not candles:
        raise ValueError("aucune bougie valide dans le CSV")
    candles.sort(key=lambda item: item.timestamp)
    unique: List[Candle] = []
    duplicate_count = 0
    for candle in candles:
        if unique and unique[-1].timestamp == candle.timestamp:
            duplicate_count += 1
            unique[-1] = candle
        else:
            unique.append(candle)
    if duplicate_count:
        warnings.append(f"{duplicate_count} timestamp(s) dupliqué(s) : une seule valeur conservée")
    candles = unique
    if return_warnings:
        return candles, warnings
    return candles


def _interval_milliseconds(interval: str) -> Optional[int]:
    units = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
    text = str(interval).lower()
    if len(text) < 2 or not text[:-1].isdigit() or text[-1] not in units:
        return None
    return int(text[:-1]) * units[text[-1]]


def fetch_binance_candles(
    symbol: str = "XRPEUR",
    interval: str = "1d",
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 1000,
) -> Tuple[List[Candle], List[str]]:
    """Récupère uniquement des klines publiques, sans clé ni endpoint d'ordres."""
    if not str(symbol).upper().startswith("XRP"):
        raise ValueError("le backtest public ne doit concerner que XRP")
    total_limit = max(1, int(limit))

    def to_ms(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            normalized = _parse_timestamp(value)
            parsed = dt.datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            return int(parsed.timestamp() * 1000)
        except (TypeError, ValueError, OverflowError, OSError) as exc:
            raise ValueError(f"date invalide: {value!r}") from exc

    cursor = to_ms(start)
    end_ms = to_ms(end)
    all_rows: List[Candle] = []
    warnings: List[str] = []
    max_pages = 20
    for _ in range(max_pages):
        remaining = total_limit - len(all_rows)
        if remaining <= 0:
            break
        page_size = min(1000, remaining)
        params = {
            "symbol": str(symbol).upper(), "interval": interval, "limit": page_size
        }
        if cursor is not None:
            params["startTime"] = cursor
        if end_ms is not None:
            params["endTime"] = end_ms
        url = f"{BINANCE_KLINES_URL}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"impossible de lire les klines publiques: {exc}") from exc
        if not isinstance(payload, list) or not payload:
            break
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                warnings.append("ligne Binance inattendue ignorée")
                continue
            try:
                timestamp = dt.datetime.fromtimestamp(
                    int(row[0]) / 1000, tz=dt.timezone.utc
                ).replace(microsecond=0).isoformat()
                candle = Candle(
                    timestamp=timestamp,
                    open=_number(row[1]),
                    high=_number(row[2]),
                    low=_number(row[3]),
                    close=_number(row[4]),
                    volume=_number(row[5]),
                )
            except (TypeError, ValueError, OverflowError, OSError):
                warnings.append("ligne Binance invalide ignorée")
                continue
            valid = (
                min(candle.open, candle.high, candle.low, candle.close) > 0
                and candle.high >= max(candle.open, candle.close, candle.low)
                and candle.low <= min(candle.open, candle.close, candle.high)
            )
            if valid:
                all_rows.append(candle)
        if len(payload) < page_size:
            break
        try:
            next_cursor = int(payload[-1][0]) + 1
        except (TypeError, ValueError, IndexError):
            break
        if cursor is not None and next_cursor <= cursor:
            break
        cursor = next_cursor
        if end_ms is not None and cursor > end_ms:
            break
        time.sleep(0.15)
    all_rows.sort(key=lambda item: item.timestamp)
    unique: List[Candle] = []
    for candle in all_rows:
        if not unique or candle.timestamp != unique[-1].timestamp:
            unique.append(candle)
    # Une kline encore ouverte ne doit pas devenir une clôture historique.
    interval_ms = _interval_milliseconds(interval)
    if interval_ms:
        now_ms = int(time.time() * 1000)
        closed = []
        for candle in unique:
            opened_ms = int(dt.datetime.fromisoformat(candle.timestamp).timestamp() * 1000)
            if opened_ms + interval_ms <= now_ms:
                closed.append(candle)
        if len(closed) != len(unique):
            warnings.append("dernière kline incomplète exclue")
        unique = closed
    if not unique:
        raise ValueError("aucune kline publique XRP reçue")
    return unique, warnings


def fetch_closes(symbol: str = "XRPEUR", interval: str = "1h", limit: int = 100):
    """Compatibilité avec l'ancien module : renvoie les clôtures publiques."""
    candles, _ = fetch_binance_candles(symbol=symbol, interval=interval, limit=limit)
    return [candle.close for candle in candles]


def _signal_for_history(closes: Sequence[float], mode: str, config: Dict[str, Any]) -> Optional[str]:
    strategy_config = config.get("strategy", {})
    try:
        if mode == "sma_only":
            return decide_sma_with_config(list(closes), strategy_config)["signal"]
        if mode == "buy_hold":
            return decide_buy_hold_with_config(list(closes), strategy_config)["signal"]
        return decide_with_config(list(closes), strategy_config)["signal"]
    except (ValueError, ZeroDivisionError):
        return None


def _execute_exit(portfolio: Portfolio, instruction: Any, mid_price: float, timestamp: str) -> None:
    result = portfolio.sell(
        mid_price,
        quantity=instruction.quantity,
        timestamp=timestamp,
        exit_level=instruction.level,
    )
    if not result.executed:
        return


def _process_intrabar_exits(portfolio: Portfolio, candle: Candle, exit_policy: str = "full") -> None:
    """Simule stop, trailing, cibles et durée sur la bougie courante.

    ``exit_policy="hold"`` (mode achat-et-gardé) n'autorise que le stop-loss :
    aucune vente de cible, de durée ou de trailing.
    """
    if portfolio.xrp <= EPS:
        return
    state = portfolio.position_state
    entry = _number(state.get("entry_price"), portfolio.position_entry_price)
    if entry <= 0:
        return
    state["highest_price"] = max(_number(state.get("highest_price"), candle.high), candle.high)

    stop = entry * (1.0 - portfolio.stop_loss_pct)
    if portfolio.stop_loss_pct > 0 and (candle.open <= stop or candle.low <= stop):
        # Gap à la baisse : exécution au pire prix disponible, puis stop.
        _execute_exit(portfolio, ExitInstruction(
            "stop_loss", portfolio.xrp, stop, None
        ), min(candle.open, stop), candle.timestamp)
        return

    if exit_policy == "hold":
        return

    if state.get("trailing_active") and portfolio.trailing_stop_pct > 0:
        trigger = _number(state.get("highest_price"), candle.high) * (
            1.0 - portfolio.trailing_stop_pct
        )
        if candle.open <= trigger or candle.low <= trigger:
            _execute_exit(portfolio, ExitInstruction(
                "trailing_stop", portfolio.xrp, trigger, None
            ), min(candle.open, trigger), candle.timestamp)
            return

    opened = state.get("opened_at")
    if opened and portfolio.max_position_days > 0:
        try:
            opened_time = dt.datetime.fromisoformat(str(opened).replace("Z", "+00:00"))
            current_time = dt.datetime.fromisoformat(candle.timestamp.replace("Z", "+00:00"))
            if opened_time.tzinfo is None:
                opened_time = opened_time.replace(tzinfo=dt.timezone.utc)
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=dt.timezone.utc)
            if (current_time - opened_time).total_seconds() / 86400 >= portfolio.max_position_days:
                _execute_exit(portfolio, ExitInstruction(
                    "max_duration", portfolio.xrp, candle.close, None
                ), candle.close, candle.timestamp)
                return
        except (TypeError, ValueError):
            pass

    # Les cibles sont traitées dans l'ordre ; le stop a déjà été prioritaire.
    while portfolio.xrp > EPS:
        next_level = int(state.get("next_level", 0))
        if next_level >= len(portfolio.profit_levels):
            break
        target = entry * (1.0 + portfolio.profit_levels[next_level])
        if candle.high < target:
            break
        quantity = portfolio.xrp * portfolio.profit_fractions[next_level]
        if quantity <= EPS:
            state["next_level"] = next_level + 1
            continue
        fill = candle.open if candle.open >= target else target
        _execute_exit(portfolio, ExitInstruction(
            f"profit_level_{next_level + 1}", quantity, target, next_level
        ), fill, candle.timestamp)
        if portfolio.xrp <= EPS:
            break
        state = portfolio.position_state


def _buy_hold_return(candles: Sequence[Candle], config: Dict[str, Any]) -> float:
    if not candles:
        return 0.0
    portfolio = portfolio_from_config(config)
    first = candles[0]
    last = candles[-1]
    buy_price = portfolio._execution_price(first.open, "BUY")
    quantity = config["initial_capital"] / (buy_price * (1.0 + portfolio.fee_rate))
    sell_price = portfolio._execution_price(last.close, "SELL")
    ending = quantity * sell_price * (1.0 - portfolio.fee_rate)
    return (ending / config["initial_capital"] - 1.0) * 100.0


def run_backtest(
    candles: Sequence[Candle],
    config: Optional[Dict[str, Any]] = None,
    strategy_mode: str = "sma_rsi",
    start_index: int = 0,
    end_index: Optional[int] = None,
    warnings: Optional[Iterable[str]] = None,
) -> BacktestResult:
    """Exécute un backtest déterministe et sans accès réseau."""
    if not candles:
        raise ValueError("aucune bougie")
    cfg = copy.deepcopy(config or load_config())
    validate_config(cfg)
    if strategy_mode == "auto":
        strategy_mode = str(cfg.get("strategy_mode", "sma_rsi")).lower()
    if strategy_mode not in ("sma_rsi", "sma_only", "buy_hold"):
        raise ValueError("stratégie inconnue")
    cfg["strategy_mode"] = strategy_mode
    start_index = max(0, min(int(start_index), len(candles) - 1))
    end_index = len(candles) if end_index is None else min(len(candles), max(start_index + 1, int(end_index)))
    if end_index <= start_index:
        raise ValueError("période out-of-sample vide")
    portfolio = portfolio_from_config(cfg)
    closes = [candle.close for candle in candles]
    configured_warmup = int(cfg.get("backtest", {}).get("warmup_bars", 26))
    if strategy_mode == "sma_rsi":
        warmup = max(
            configured_warmup,
            int(cfg.get("strategy", {}).get("slow", 25))
            + int(cfg.get("strategy", {}).get("rsi", 14))
            + 1,
        )
    else:
        warmup = max(configured_warmup, int(cfg.get("strategy", {}).get("slow", 25)))
    if len(candles) <= warmup:
        raise ValueError(
            f"historique insuffisant : {len(candles)} bougies, minimum {warmup + 1}"
        )

    equity_curve: List[float] = []
    exposure_values: List[float] = []
    cash_values: List[float] = []
    fills_log: List[Dict[str, Any]] = []
    signal_count = 0
    pending_signal: Optional[str] = None
    if start_index > 0:
        pending_signal = _signal_for_history(closes[:start_index], strategy_mode, cfg)
        if pending_signal:
            signal_count += 1

    for index in range(start_index, end_index):
        candle = candles[index]
        # Le signal disponible vient exclusivement des bougies précédentes.
        if pending_signal == "BUY":
            # buy_hold : une seule entrée ; on ne ré-achète pas sans cesse
            # tant qu'une position est déjà ouverte (capital limité).
            if strategy_mode == "buy_hold" and portfolio.xrp > EPS:
                pass
            else:
                result = portfolio.buy(
                    candle.open,
                    volume=candle.volume,
                    timestamp=candle.timestamp,
                )
                if result.executed:
                    fills_log.append({
                        "timestamp": candle.timestamp, "side": "BUY",
                        "quantity": result.quantity, "price": result.price,
                        "notional": result.notional, "fee": result.fee,
                    })
        elif pending_signal == "SELL":
            result = portfolio.sell(candle.open, timestamp=candle.timestamp)
            if result.executed:
                fills_log.append({
                    "timestamp": candle.timestamp, "side": "SELL",
                    "quantity": result.quantity, "price": result.price,
                    "notional": result.notional, "fee": result.fee,
                    "realized_pnl": result.realized_pnl,
                })

        _process_intrabar_exits(
            portfolio, candle,
            exit_policy="hold" if strategy_mode == "buy_hold" else "full",
        )
        portfolio.mark(candle.close, candle.timestamp)
        value = portfolio.portfolio_value(candle.close)
        equity_curve.append(value)
        exposure_values.append(
            portfolio.position_value(candle.close) / value * 100.0 if value > EPS else 0.0
        )
        cash_values.append(portfolio.available_cash)

        # Cette_CLOSE est connue seulement maintenant ; son signal sera exécuté
        # à l'ouverture de l'index suivant, jamais à cette_close.
        next_signal = _signal_for_history(closes[:index + 1], strategy_mode, cfg)
        if next_signal:
            pending_signal = next_signal
            signal_count += 1
        else:
            pending_signal = None

    last_index = end_index - 1
    portfolio.mark(candles[last_index].close, candles[last_index].timestamp)
    end_value = portfolio.portfolio_value(candles[last_index].close)
    initial = float(cfg["initial_capital"])
    net_return = (end_value / initial - 1.0) * 100.0 if initial else 0.0
    peak = 0.0
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > EPS:
            max_dd = max(max_dd, (peak - value) / peak * 100.0)
    all_warnings = list(warnings or [])
    if start_index > 0:
        all_warnings.append("période out-of-sample : aucun signal exécuté avant start_index")
    if portfolio.daily_halted:
        all_warnings.append("au moins une journée a été bloquée par max_daily_loss_pct")
    quote = str(cfg.get("quote_currency", "EUR")).upper()
    if quote and not str(cfg.get("symbol", "XRPEUR")).upper().endswith(quote):
        all_warnings.append(
            f"le prix {cfg.get('symbol')} n'est pas libellé en {cfg.get('quote_currency')} : "
            "P&L non comparable à la devise de comptabilisation"
        )
    return BacktestResult(
        strategy=strategy_mode,
        initial_capital=initial,
        end_value=end_value,
        net_return_pct=net_return,
        buy_hold_return_pct=_buy_hold_return(candles[start_index:end_index], cfg),
        max_drawdown_pct=max_dd,
        trades=portfolio.closed_trades,
        fills=portfolio.fills,
        win_rate_pct=(100.0 * portfolio.wins / portfolio.closed_trades
                      if portfolio.closed_trades else 0.0),
        average_exposure_pct=(sum(exposure_values) / len(exposure_values)
                              if exposure_values else 0.0),
        cash_unused_avg=(sum(cash_values) / len(cash_values) if cash_values else 0.0),
        cash_unused_end=portfolio.available_cash,
        total_fees=portfolio.total_fees,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=portfolio.unrealized_pnl(candles[last_index].close),
        data_start=candles[start_index].timestamp,
        data_end=candles[last_index].timestamp,
        candle_count=end_index - start_index,
        warnings=all_warnings,
        equity_curve=equity_curve,
        fills_log=fills_log,
        signal_count=signal_count,
        out_of_sample=start_index > 0,
    )


def run_walk_forward(
    candles: Sequence[Candle],
    config: Optional[Dict[str, Any]] = None,
    folds: int = 3,
    strategy_mode: str = "sma_rsi",
) -> List[BacktestResult]:
    """Évalue plusieurs blocs out-of-sample sans optimiser les paramètres."""
    if len(candles) < 4:
        raise ValueError("trop peu de bougies pour walk-forward")
    folds = max(2, int(folds))
    cfg = copy.deepcopy(config or load_config())
    warmup = max(
        int(cfg.get("backtest", {}).get("warmup_bars", 26)),
        int(cfg.get("strategy", {}).get("slow", 25))
        + int(cfg.get("strategy", {}).get("rsi", 14))
        + 1,
    )
    start = warmup
    if len(candles) <= start + folds * 2:
        raise ValueError("trop peu de bougies pour walk-forward")
    segment = (len(candles) - start) // folds
    results: List[BacktestResult] = []
    for fold in range(folds):
        first = start + fold * segment
        last = len(candles) if fold == folds - 1 else start + (fold + 1) * segment
        if last - first < 2:
            continue
        result = run_backtest(
            candles, config=cfg, strategy_mode=strategy_mode,
            start_index=first, end_index=last,
            warnings=[f"walk-forward fold {fold + 1}/{folds}"]
        )
        result.out_of_sample = True
        results.append(result)
    return results


def _format_result(result: BacktestResult) -> str:
    warnings = " | ".join(result.warnings) if result.warnings else "aucune"
    simple = (
        f"{result.simple_strategy_return_pct:.2f}%"
        if result.simple_strategy_return_pct is not None else "n/a"
    )
    return (
        f"Stratégie={result.strategy} | net={result.net_return_pct:.2f}% "
        f"| buy&hold={result.buy_hold_return_pct:.2f}% "
        f"| maxDD={result.max_drawdown_pct:.2f}% "
        f"| trades={result.trades} (fills={result.fills}) "
        f"| réussite={result.win_rate_pct:.1f}% "
        f"| SMA seul={simple} "
        f"| exposition={result.average_exposure_pct:.1f}% "
        f"| cash inutilisé moyen={result.cash_unused_avg:.2f} "
        f"| frais={result.total_fees:.2f}\n"
        f"Données={result.data_start} -> {result.data_end} ({result.candle_count} bougies) "
        f"| P&L réalisé={result.realized_pnl:.2f} "
        f"| P&L non réalisé={result.unrealized_pnl:.2f} "
        f"| alertes={warnings}"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest XRP paper-only, sans ordre réel")
    parser.add_argument("--data", help="CSV OHLCV local")
    parser.add_argument("--public-data", action="store_true",
                        help="lire les klines publiques Binance (aucun ordre, aucune clé)")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--interval", default=None)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--initial-capital", type=float, default=None)
    parser.add_argument("--strategy", choices=("sma_rsi", "sma_only", "buy_hold"), default="auto")
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--output", help="écrire le résultat JSON")
    parser.add_argument("--live", action="store_true", help="refusé : le live est interdit")
    args = parser.parse_args(argv)
    if args.live:
        print("REFUS : trading live interdit ; utilisez seulement paper/backtest", file=sys.stderr)
        return 2

    config = load_config()
    validate_config(config)
    if args.symbol:
        config["symbol"] = args.symbol.upper()
    if args.initial_capital is not None:
        if args.initial_capital <= 0:
            parser.error("--initial-capital doit être > 0")
        config["initial_capital"] = args.initial_capital
    if args.interval:
        config.setdefault("backtest", {})["interval"] = args.interval
    strategy_mode = args.strategy
    if strategy_mode == "auto":
        strategy_mode = str(config.get("strategy_mode", "sma_rsi")).lower()

    warnings: List[str] = []
    if args.data:
        path = args.data if os.path.isabs(args.data) else os.path.join(ROOT, args.data)
        candles, warnings = load_candles(path, return_warnings=True)
    elif args.public_data:
        candles, warnings = fetch_binance_candles(
            symbol=config["symbol"],
            interval=config.get("backtest", {}).get("interval", "1d"),
            start=args.start,
            end=args.end,
        )
        warnings.append("source=klines publiques Binance (lecture seule, aucun ordre)")
    else:
        path = config.get("backtest", {}).get("data_file", DEFAULT_DATA)
        if not os.path.isabs(path):
            path = os.path.join(ROOT, path)
        if not os.path.exists(path):
            print(
                "Aucune donnée locale. Fournir --data fichier.csv ou --public-data "
                "(klines publiques uniquement).", file=sys.stderr
            )
            return 2
        candles, warnings = load_candles(path, return_warnings=True)

    if args.walk_forward:
        results = run_walk_forward(
            candles, config=config, folds=args.folds, strategy_mode=strategy_mode
        )
        if strategy_mode == "sma_rsi":
            simple_results = run_walk_forward(
                candles, config=config, folds=args.folds, strategy_mode="sma_only"
            )
            for primary, simple in zip(results, simple_results):
                primary.simple_strategy_return_pct = simple.net_return_pct
                primary.simple_strategy_max_drawdown_pct = simple.max_drawdown_pct
    else:
        primary = run_backtest(
            candles, config=config, strategy_mode=strategy_mode, warnings=warnings
        )
        if strategy_mode == "sma_rsi":
            simple = run_backtest(candles, config=config, strategy_mode="sma_only")
            primary.simple_strategy_return_pct = simple.net_return_pct
            primary.simple_strategy_max_drawdown_pct = simple.max_drawdown_pct
        results = [primary]
    payload = [result.as_dict(include_curve=False) for result in results]
    if args.as_json:
        rendered = json.dumps(payload if len(payload) != 1 else payload[0],
                              ensure_ascii=False, indent=2)
    else:
        rendered = "\n".join(_format_result(result) for result in results)
    print(rendered)
    if args.output:
        out = args.output if os.path.isabs(args.output) else os.path.join(ROOT, args.output)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
