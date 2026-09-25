"""Registre et moteur d'exécution paper-only pour BTC spot.

Ce module ne contient aucun client d'ordres. Il conserve le cash, la quantité
BTC, les frais, les P&L et les réservations ; chaque achat est vérifié avant
mutation de l'état.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

EPS = 1e-10
SCHEMA_VERSION = 2


class TradingError(RuntimeError):
    """Erreur de sécurité ou d'état du registre."""


@dataclass
class TradeResult:
    executed: bool
    side: str
    reason: str
    quantity: float = 0.0
    price: float = 0.0
    notional: float = 0.0
    fee: float = 0.0
    cash_delta: float = 0.0
    realized_pnl: float = 0.0

    @property
    def ok(self) -> bool:
        return self.executed


@dataclass
class PositionLot:
    quantity: float
    entry_price: float
    cost_basis: float
    opened_at: Optional[str] = None
    entry_fee: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "cost_basis": self.cost_basis,
            "opened_at": self.opened_at,
            "entry_fee": self.entry_fee,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionLot":
        return cls(
            quantity=float(data.get("quantity", 0.0)),
            entry_price=float(data.get("entry_price", 0.0)),
            cost_basis=float(data.get("cost_basis", 0.0)),
            opened_at=data.get("opened_at"),
            entry_fee=float(data.get("entry_fee", 0.0)),
        )


@dataclass
class ExitInstruction:
    reason: str
    quantity: float
    target_price: Optional[float] = None
    level: Optional[int] = None


@dataclass
class PendingOrder:
    order_id: int
    side: str
    quantity: float
    reference_price: float
    reserved_cash: float
    fee: float
    timestamp: Optional[str] = None
    status: str = "reserved"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "side": self.side,
            "quantity": self.quantity,
            "reference_price": self.reference_price,
            "reserved_cash": self.reserved_cash,
            "fee": self.fee,
            "timestamp": self.timestamp,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingOrder":
        return cls(
            order_id=int(data.get("order_id", 0)),
            side=str(data.get("side", "BUY")),
            quantity=float(data.get("quantity", 0.0)),
            reference_price=float(data.get("reference_price", 0.0)),
            reserved_cash=float(data.get("reserved_cash", 0.0)),
            fee=float(data.get("fee", 0.0)),
            timestamp=data.get("timestamp"),
            status=str(data.get("status", "reserved")),
        )


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: Optional[str]) -> Optional[_dt.datetime]:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


class Portfolio:
    """Compte paper BTC avec comptabilité FIFO et contrôle de solvabilité."""

    def __init__(
        self,
        initial_capital: float = 1000.0,
        symbol: str = "BTCEUR",
        quote_currency: str = "EUR",
        fee_rate: float = 0.001,
        spread: float = 0.002,
        slippage: float = 0.0005,
        max_notional_per_trade: float = 250.0,
        min_notional: float = 5.0,
        allocation_pct: float = 0.20,
        max_position_pct: float = 0.25,
        max_total_exposure_pct: float = 0.50,
        max_risk_per_position_pct: float = 0.02,
        min_cash_reserve: float = 50.0,
        fee_reserve_multiplier: float = 1.10,
        participation_rate: float = 1.0,
        stop_loss_pct: float = 0.10,
        max_daily_loss_pct: float = 0.03,
        max_position_days: float = 30.0,
        profit_levels: Optional[Iterable[float]] = None,
        profit_fractions: Optional[Iterable[float]] = None,
        trailing_stop_pct: float = 0.08,
        paper: bool = True,
        kill_switch: bool = False,
    ) -> None:
        self.initial_capital = _number(initial_capital)
        self.symbol = str(symbol).upper()
        self.quote_currency = str(quote_currency)
        self.fee_rate = _number(fee_rate)
        self.spread = _number(spread)
        self.slippage = _number(slippage)
        self.max_notional_per_trade = _number(max_notional_per_trade)
        self.min_notional = _number(min_notional)
        self.allocation_pct = _number(allocation_pct)
        self.max_position_pct = _number(max_position_pct)
        self.max_total_exposure_pct = _number(max_total_exposure_pct)
        self.max_risk_per_position_pct = _number(max_risk_per_position_pct, 0.02)
        self.min_cash_reserve = _number(min_cash_reserve)
        self.fee_reserve_multiplier = _number(fee_reserve_multiplier, 1.0)
        self.participation_rate = _number(participation_rate, 1.0)
        self.stop_loss_pct = _number(stop_loss_pct)
        self.max_daily_loss_pct = _number(max_daily_loss_pct)
        self.max_position_days = _number(max_position_days, 30.0)
        self.profit_levels = [float(x) for x in (profit_levels or [0.05, 0.10, 0.20])]
        self.profit_fractions = [float(x) for x in (profit_fractions or [0.25, 0.25, 0.20])]
        self.trailing_stop_pct = _number(trailing_stop_pct)
        self.paper = bool(paper)
        self.kill_switch = bool(kill_switch)

        if self.initial_capital <= 0:
            raise ValueError("initial_capital doit être > 0")
        if not self.symbol.startswith("BTC"):
            raise ValueError("Seul BTC spot est autorisé")
        if not self.paper:
            raise TradingError("Le trading live est désactivé")
        if not 0 <= self.fee_rate < 1:
            raise ValueError("fee_rate doit être dans [0, 1)")
        if self.spread < 0 or self.slippage < 0:
            raise ValueError("spread et slippage doivent être >= 0")
        if self.spread / 2.0 + self.slippage >= 1:
            raise ValueError("spread + slippage doivent laisser un prix de vente positif")
        if len(self.profit_levels) != len(self.profit_fractions):
            raise ValueError("Niveaux et fractions de sortie doivent être alignés")
        if not self.profit_levels or any(x <= 0 for x in self.profit_levels):
            raise ValueError("Niveaux de sortie invalides")
        if any(x < 0 or x > 1 for x in self.profit_fractions):
            raise ValueError("Fractions de sortie invalides")
        if sum(self.profit_fractions) > 1 + EPS:
            raise ValueError("Fractions de sortie supérieures à 100%")
        if self.max_risk_per_position_pct < 0:
            raise ValueError("max_risk_per_position_pct doit être >= 0")

        self.cash = self.initial_capital
        self.reserved_cash = 0.0
        self.fee_reserve_cash = 0.0
        self.positions: List[PositionLot] = []
        self.position_state: Dict[str, Any] = {}
        self.pending_orders: List[PendingOrder] = []
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.closed_trades = 0
        self.wins = 0
        self.losses = 0
        self.fills = 0
        self.last_price = 0.0
        self.daily_date: Optional[str] = None
        self.daily_start_equity: Optional[float] = None
        self.daily_halted = False
        self._next_order_id = 1

    # ------------------------------------------------------------------
    # États et propriétés comptables
    # ------------------------------------------------------------------
    @property
    def btc(self) -> float:
        return sum(lot.quantity for lot in self.positions)

    @property
    def position_cost_basis(self) -> float:
        return sum(lot.cost_basis for lot in self.positions)

    @property
    def available_cash(self) -> float:
        return self.cash - self.reserved_cash - self.fee_reserve_cash

    @property
    def free_cash(self) -> float:
        return self.available_cash

    @property
    def position_entry_price(self) -> float:
        quantity = self.btc
        return self.position_cost_basis / quantity if quantity > EPS else 0.0

    def position_value(self, price: float) -> float:
        return self.btc * _number(price)

    def portfolio_value(self, price: float) -> float:
        return self.cash + self.position_value(price)

    def unrealized_pnl(self, price: float) -> float:
        return self.position_value(price) - self.position_cost_basis

    def total_pnl(self, price: float) -> float:
        return self.realized_pnl + self.unrealized_pnl(price)

    def snapshot(self, price: Optional[float] = None) -> Dict[str, Any]:
        mark = _number(price, self.last_price)
        value = self.portfolio_value(mark)
        return {
            "initial_capital": self.initial_capital,
            "currency": self.quote_currency,
            "symbol": self.symbol,
            "cash": self.cash,
            "available_cash": self.available_cash,
            "reserved_cash": self.reserved_cash,
            "fee_reserve_cash": self.fee_reserve_cash,
            "btc": self.btc,
            "position_value": self.position_value(mark),
            "portfolio_value": value,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl(mark),
            "total_fees": self.total_fees,
            "closed_trades": self.closed_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate_pct": (100.0 * self.wins / self.closed_trades
                             if self.closed_trades else 0.0),
            "fills": self.fills,
            "kill_switch": self.kill_switch,
            "daily_halted": self.daily_halted,
        }

    def _assert_invariants(self) -> None:
        if self.cash < -EPS:
            raise TradingError("cash ne peut pas être négatif")
        if self.btc < -EPS or any(lot.quantity < -EPS for lot in self.positions):
            raise TradingError("BTC ne peut pas être négatif")
        if self.reserved_cash < -EPS or self.fee_reserve_cash < -EPS:
            raise TradingError("réservation négative")
        if self.reserved_cash + self.fee_reserve_cash > self.cash + EPS:
            raise TradingError("réservation supérieure au cash disponible")
        for lot in self.positions:
            if lot.cost_basis < -EPS or lot.entry_price <= 0:
                raise TradingError("lot BTC incohérent")

    def _check_buy_allowed(self) -> Optional[str]:
        if not self.paper:
            return "live_trading_forbidden"
        if self.kill_switch:
            return "kill_switch"
        if self.daily_halted:
            return "daily_loss_limit"
        return None

    def _execution_price(self, mid_price: float, side: str) -> float:
        mid = _number(mid_price)
        if mid <= 0 or not math.isfinite(mid):
            raise ValueError("prix médian invalide")
        half_spread = self.spread / 2.0
        if side == "BUY":
            return mid * (1.0 + half_spread + self.slippage)
        return mid * (1.0 - half_spread - self.slippage)

    def _required_fee_reserve(self, additional_basis: float = 0.0) -> float:
        basis = self.position_cost_basis + max(0.0, additional_basis)
        return basis * self.fee_rate * self.fee_reserve_multiplier

    def _recalculate_fee_reserve(self) -> None:
        required = self._required_fee_reserve()
        # La réserve est une contrainte de cash, jamais une dette implicite.
        self.fee_reserve_cash = min(self.cash, max(0.0, required))

    def _capacity_notional(self, mid_price: float) -> float:
        equity = max(0.0, self.portfolio_value(mid_price))
        current_value = self.position_value(mid_price)
        position_capacity = max(0.0, equity * self.max_position_pct - current_value)
        total_capacity = max(0.0, equity * self.max_total_exposure_pct - current_value)
        risk_capacity = equity * self.max_risk_per_position_pct
        if self.stop_loss_pct > EPS:
            risk_capacity /= self.stop_loss_pct
        risk_capacity = max(0.0, risk_capacity - current_value)
        return min(position_capacity, total_capacity, risk_capacity)

    def _plan_buy(
        self,
        mid_price: float,
        desired_notional: Optional[float] = None,
        quantity: Optional[float] = None,
        volume: Optional[float] = None,
    ) -> Optional[Dict[str, float]]:
        reason = self._check_buy_allowed()
        if reason:
            return None
        mid = _number(mid_price)
        if mid <= 0 or not math.isfinite(mid):
            return None

        exec_price = self._execution_price(mid, "BUY")
        if exec_price <= 0:
            return None
        if quantity is not None:
            requested_qty = _number(quantity)
            if requested_qty <= 0:
                return None
            gross = requested_qty * exec_price
        else:
            equity = self.portfolio_value(mid)
            requested_notional = _number(
                desired_notional,
                equity * self.allocation_pct,
            )
            requested_notional = min(requested_notional, self._capacity_notional(mid))
            if self.max_notional_per_trade > 0:
                requested_notional = min(requested_notional, self.max_notional_per_trade)
            if volume is not None and self.participation_rate > 0:
                requested_notional = min(
                    requested_notional,
                    max(0.0, _number(volume) * self.participation_rate * mid),
                )
            if requested_notional <= 0:
                return None
            requested_qty = requested_notional / exec_price

        gross = requested_qty * exec_price
        fee = gross * self.fee_rate
        total = gross + fee
        # La réserve de frais de sortie est calculée avant de dépenser.
        projected_basis = self.position_cost_basis + total
        required_reserve = max(
            self.min_cash_reserve,
            self.fee_reserve_cash,
            projected_basis * self.fee_rate * self.fee_reserve_multiplier,
        )
        # Une réserve fixe (ex. 50 EUR) ne doit pas bloquer un petit capital
        # (compte à 10 EUR) : la réserve est plafonnée à 20 % du capital initial.
        required_reserve = min(required_reserve, max(0.0, self.initial_capital * 0.20))
        budget = self.cash - self.reserved_cash - required_reserve
        if budget <= EPS:
            return None
        if total > budget + EPS:
            if quantity is not None:
                return None
            requested_qty = budget / (exec_price * (1.0 + self.fee_rate))
            gross = requested_qty * exec_price
            fee = gross * self.fee_rate
            total = gross + fee
        if requested_qty <= EPS:
            return None
        if quantity is not None:
            if self.max_notional_per_trade > 0 and gross > self.max_notional_per_trade + EPS:
                return None
            if volume is not None and self.participation_rate > 0:
                liquidity_notional = max(0.0, _number(volume) * self.participation_rate * mid)
                if gross > liquidity_notional + EPS:
                    return None
        if gross < self.min_notional:
            return None
        if requested_qty * exec_price > self._capacity_notional(mid) + EPS:
            if quantity is not None:
                return None
            requested_qty = self._capacity_notional(mid) / exec_price
            gross = requested_qty * exec_price
            fee = gross * self.fee_rate
            total = gross + fee
            if gross < self.min_notional or total > budget + EPS:
                return None
        return {
            "mid_price": mid,
            "execution_price": exec_price,
            "quantity": requested_qty,
            "gross": gross,
            "fee": fee,
            "total": total,
        }

    # ------------------------------------------------------------------
    # Achats, réservations et ventes
    # ------------------------------------------------------------------
    def _apply_buy(self, plan: Dict[str, float], timestamp: Optional[str]) -> TradeResult:
        quantity = plan["quantity"]
        execution_price = plan["execution_price"]
        gross = plan["gross"]
        fee = plan["fee"]
        total = plan["total"]
        self.cash -= total
        self.positions.append(
            PositionLot(
                quantity=quantity,
                entry_price=execution_price,
                cost_basis=total,
                opened_at=timestamp or _iso_now(),
                entry_fee=fee,
            )
        )
        self.total_fees += fee
        self.fills += 1
        self.last_price = plan["mid_price"]
        if not self.position_state:
            self.position_state = {
                "entry_price": execution_price,
                "initial_quantity": quantity,
                "highest_price": plan["mid_price"],
                "next_level": 0,
                "trailing_active": False,
                "opened_at": timestamp or _iso_now(),
            }
        else:
            old_qty = _number(self.position_state.get("initial_quantity"))
            self.position_state["entry_price"] = (
                (old_qty * _number(self.position_state.get("entry_price"))
                 + quantity * execution_price) / (old_qty + quantity)
                if old_qty + quantity > EPS else execution_price
            )
            self.position_state["initial_quantity"] = old_qty + quantity
            self.position_state["highest_price"] = max(
                _number(self.position_state.get("highest_price")),
                plan["mid_price"],
            )
        self._recalculate_fee_reserve()
        self._assert_invariants()
        return TradeResult(
            executed=True,
            side="BUY",
            reason="filled",
            quantity=quantity,
            price=execution_price,
            notional=gross,
            fee=fee,
            cash_delta=-total,
        )

    def buy(
        self,
        mid_price: float,
        desired_notional: Optional[float] = None,
        quantity: Optional[float] = None,
        volume: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> TradeResult:
        """Remplit un achat immédiatement, sans jamais dépasser le cash libre."""
        plan = self._plan_buy(mid_price, desired_notional, quantity, volume)
        if plan is None:
            return TradeResult(False, "BUY", self._check_buy_allowed() or "insufficient_cash_or_liquidity")
        return self._apply_buy(plan, timestamp)

    def reserve_buy(
        self,
        mid_price: float,
        desired_notional: Optional[float] = None,
        quantity: Optional[float] = None,
        volume: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> Optional[PendingOrder]:
        """Réserve un achat afin qu'une autre commande ne réutilise pas le cash."""
        plan = self._plan_buy(mid_price, desired_notional, quantity, volume)
        if plan is None:
            return None
        order = PendingOrder(
            order_id=self._next_order_id,
            side="BUY",
            quantity=plan["quantity"],
            reference_price=plan["mid_price"],
            reserved_cash=plan["total"],
            fee=plan["fee"],
            timestamp=timestamp,
        )
        self._next_order_id += 1
        self.reserved_cash += order.reserved_cash
        self.pending_orders.append(order)
        self._assert_invariants()
        return order

    def cancel_order(self, order: PendingOrder) -> bool:
        if order.status != "reserved" or order not in self.pending_orders:
            return False
        self.reserved_cash = max(0.0, self.reserved_cash - order.reserved_cash)
        self.pending_orders.remove(order)
        order.status = "cancelled"
        self._assert_invariants()
        return True

    def fill_reserved_buy(
        self,
        order: PendingOrder,
        mid_price: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> TradeResult:
        """Simule le fill d'un achat réservé ; la réservation est consommée une fois."""
        if order.status != "reserved" or order not in self.pending_orders:
            return TradeResult(False, "BUY", "order_not_reserved")
        reference = _number(mid_price, order.reference_price)
        plan = {
            "mid_price": reference,
            "execution_price": self._execution_price(reference, "BUY"),
            "quantity": order.quantity,
            "gross": order.quantity * self._execution_price(reference, "BUY"),
            "fee": 0.0,
            "total": 0.0,
        }
        plan["fee"] = plan["gross"] * self.fee_rate
        plan["total"] = plan["gross"] + plan["fee"]
        # Une hausse du prix ne peut pas faire déborder la réservation.
        if plan["total"] > order.reserved_cash + EPS:
            return TradeResult(False, "BUY", "reserved_cash_insufficient")
        self.reserved_cash = max(0.0, self.reserved_cash - order.reserved_cash)
        self.pending_orders.remove(order)
        order.status = "filled"
        return self._apply_buy(plan, timestamp or order.timestamp)

    def _consume_cost_basis(self, quantity: float) -> float:
        remaining = quantity
        removed = 0.0
        while remaining > EPS and self.positions:
            lot = self.positions[0]
            take = min(lot.quantity, remaining)
            ratio = take / lot.quantity if lot.quantity > EPS else 0.0
            removed += lot.cost_basis * ratio
            lot.quantity -= take
            lot.cost_basis -= lot.cost_basis * ratio
            remaining -= take
            if lot.quantity <= EPS:
                self.positions.pop(0)
        if remaining > EPS:
            raise TradingError("vente supérieure à la quantité BTC détenue")
        return removed

    def sell(
        self,
        mid_price: float,
        quantity: Optional[float] = None,
        fraction: Optional[float] = None,
        timestamp: Optional[str] = None,
        exit_level: Optional[int] = None,
    ) -> TradeResult:
        """Vente spotfractionnaire ; les sorties de risque restent autorisées si le kill switch est actif."""
        if not self.paper:
            return TradeResult(False, "SELL", "live_trading_forbidden")
        held = self.btc
        if held <= EPS:
            return TradeResult(False, "SELL", "no_position")
        if quantity is None and fraction is None:
            sell_qty = held
        elif quantity is None:
            sell_fraction = _number(fraction)
            if sell_fraction <= 0 or sell_fraction > 1 + EPS:
                return TradeResult(False, "SELL", "invalid_fraction")
            sell_qty = min(held, held * sell_fraction)
        else:
            sell_qty = min(held, _number(quantity))
        if sell_qty <= EPS:
            return TradeResult(False, "SELL", "invalid_quantity")
        exec_price = self._execution_price(mid_price, "SELL")
        gross = sell_qty * exec_price
        fee = gross * self.fee_rate
        proceeds = gross - fee
        removed_basis = self._consume_cost_basis(sell_qty)
        realized = proceeds - removed_basis
        self.cash += proceeds
        self.realized_pnl += realized
        self.total_fees += fee
        self.closed_trades += 1
        if realized > EPS:
            self.wins += 1
        elif realized < -EPS:
            self.losses += 1
        self.fills += 1
        self.last_price = _number(mid_price)
        if self.btc <= EPS:
            self.position_state = {}
        elif exit_level is not None:
            next_level = int(exit_level) + 1
            self.position_state["next_level"] = max(
                int(self.position_state.get("next_level", 0)), next_level
            )
            if next_level >= len(self.profit_levels):
                self.position_state["trailing_active"] = True
        self._recalculate_fee_reserve()
        self._assert_invariants()
        return TradeResult(
            executed=True,
            side="SELL",
            reason="filled",
            quantity=sell_qty,
            price=exec_price,
            notional=gross,
            fee=fee,
            cash_delta=proceeds,
            realized_pnl=realized,
        )

    # ------------------------------------------------------------------
    # Risque et sorties progressives
    # ------------------------------------------------------------------
    def _age_days(self, now: Optional[str]) -> float:
        opened = _parse_time(self.position_state.get("opened_at"))
        current = _parse_time(now)
        if not opened or not current:
            return 0.0
        return max(0.0, (current - opened).total_seconds() / 86400.0)

    def plan_exits(
        self,
        mid_price: float,
        now: Optional[str] = None,
    ) -> List[ExitInstruction]:
        """Retourne les sorties déclenchées sans passer un ordre réel."""
        if self.btc <= EPS:
            return []
        mark = _number(mid_price)
        if mark <= 0:
            return []
        if not self.position_state:
            self.position_state = {
                "entry_price": self.position_entry_price,
                "initial_quantity": self.btc,
                "highest_price": mark,
                "next_level": 0,
                "trailing_active": False,
                "opened_at": now or _iso_now(),
            }
        self.position_state["highest_price"] = max(
            _number(self.position_state.get("highest_price"), mark), mark
        )
        entry = _number(self.position_state.get("entry_price"), self.position_entry_price)
        if entry <= 0:
            return []
        stop_price = entry * (1.0 - self.stop_loss_pct)
        if self.stop_loss_pct > 0 and mark <= stop_price:
            return [ExitInstruction("stop_loss", self.btc, stop_price)]
        if self.max_position_days > 0 and self._age_days(now) >= self.max_position_days:
            return [ExitInstruction("max_duration", self.btc, mark)]

        highest = _number(self.position_state.get("highest_price"), mark)
        if self.position_state.get("trailing_active") and self.trailing_stop_pct > 0:
            trailing_price = highest * (1.0 - self.trailing_stop_pct)
            if mark <= trailing_price:
                return [ExitInstruction("trailing_stop", self.btc, trailing_price)]

        instructions: List[ExitInstruction] = []
        next_level = int(self.position_state.get("next_level", 0))
        while next_level < len(self.profit_levels):
            level = self.profit_levels[next_level]
            target = entry * (1.0 + level)
            if mark < target:
                break
            fraction = self.profit_fractions[next_level]
            qty = min(self.btc, self.btc * fraction)
            if qty > EPS:
                instructions.append(ExitInstruction(
                    f"profit_level_{next_level + 1}", qty, target, next_level
                ))
            next_level += 1
        return instructions

    def mark(self, mid_price: float, timestamp: Optional[str] = None) -> None:
        """Marque le portefeuille et applique la limite de perte journalière."""
        price = _number(mid_price)
        if price <= 0:
            return
        self.last_price = price
        day = (timestamp or _iso_now())[:10]
        equity = self.portfolio_value(price)
        if day != self.daily_date:
            self.daily_date = day
            self.daily_start_equity = equity
            self.daily_halted = False
        elif self.daily_start_equity is None:
            self.daily_start_equity = equity
        if self.daily_start_equity and self.max_daily_loss_pct > 0:
            if equity <= self.daily_start_equity * (1.0 - self.max_daily_loss_pct):
                self.daily_halted = True

    def set_kill_switch(self, enabled: bool = True) -> None:
        self.kill_switch = bool(enabled)
        self._assert_invariants()

    def resume(self) -> None:
        """Réactivation explicite ; aucune reprise automatique n'est faite."""
        self.kill_switch = False
        self.daily_halted = False

    # ------------------------------------------------------------------
    # Persistance JSON
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": "paper" if self.paper else "live",
            "symbol": self.symbol,
            "quote_currency": self.quote_currency,
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "available_cash": self.available_cash,
            "btc": self.btc,
            "position_value": self.position_value(self.last_price),
            "portfolio_value": self.portfolio_value(self.last_price),
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl(self.last_price),
            "total_fees": self.total_fees,
            "closed_trades": self.closed_trades,
            "wins": self.wins,
            "losses": self.losses,
            "reserved_cash": self.reserved_cash,
            "fee_reserve_cash": self.fee_reserve_cash,
            "positions": [lot.to_dict() for lot in self.positions],
            "position_state": dict(self.position_state),
            "pending_orders": [order.to_dict() for order in self.pending_orders],
            "realized_pnl": self.realized_pnl,
            "total_fees": self.total_fees,
            "closed_trades": self.closed_trades,
            "wins": self.wins,
            "losses": self.losses,
            "fills": self.fills,
            "last_price": self.last_price,
            "daily_date": self.daily_date,
            "daily_start_equity": self.daily_start_equity,
            "daily_halted": self.daily_halted,
            "kill_switch": self.kill_switch,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        initial_capital: Optional[float] = None,
        reference_price: Optional[float] = None,
        **kwargs: Any,
    ) -> "Portfolio":
        """Recharge un registre, avec migration conservative des anciens BTC."""
        capital = _number(data.get("initial_capital", initial_capital or 0), 0)
        if capital <= 0:
            capital = _number(initial_capital, 1000.0)
        obj = cls(initial_capital=capital, **kwargs)
        obj.cash = max(0.0, _number(data.get("cash", capital), capital))
        raw_positions = data.get("positions")
        if isinstance(raw_positions, list) and raw_positions:
            obj.positions = [PositionLot.from_dict(item) for item in raw_positions]
        else:
            legacy_qty = max(0.0, _number(data.get("btc", 0)))
            if legacy_qty > EPS:
                entry = _number(reference_price, 0.0)
                if entry <= 0:
                    entry = _number(data.get("last_price"), 1.0)
                if entry <= 0:
                    entry = 1.0
                obj.positions = [PositionLot(
                    quantity=legacy_qty,
                    entry_price=max(EPS, entry),
                    cost_basis=legacy_qty * max(EPS, entry),
                    opened_at=None,
                )]
        obj.positions = [lot for lot in obj.positions if lot.quantity > EPS]
        state = data.get("position_state")
        if isinstance(state, dict) and state:
            obj.position_state = dict(state)
        elif obj.positions:
            obj.position_state = {
                "entry_price": obj.position_entry_price,
                "initial_quantity": obj.btc,
                "highest_price": _number(data.get("last_price"), obj.position_entry_price),
                "next_level": 0,
                "trailing_active": False,
                "opened_at": obj.positions[0].opened_at or _iso_now(),
            }
        obj.reserved_cash = max(0.0, _number(data.get("reserved_cash", 0)))
        raw_pending = data.get("pending_orders", [])
        if isinstance(raw_pending, list):
            obj.pending_orders = [PendingOrder.from_dict(item) for item in raw_pending
                                  if item.get("status", "reserved") == "reserved"]
        obj._next_order_id = max(
            [order.order_id for order in obj.pending_orders] + [0]
        ) + 1
        obj.realized_pnl = _number(data.get("realized_pnl", 0))
        obj.total_fees = _number(data.get("total_fees", 0))
        obj.closed_trades = int(_number(data.get("closed_trades", data.get("trades", 0))))
        obj.wins = int(_number(data.get("wins", 0)))
        obj.losses = int(_number(data.get("losses", 0)))
        obj.fills = int(_number(data.get("fills", obj.closed_trades)))
        obj.last_price = _number(data.get("last_price", reference_price or 0))
        obj.daily_date = data.get("daily_date")
        obj.daily_start_equity = data.get("daily_start_equity")
        obj.daily_halted = bool(data.get("daily_halted", False))
        obj.kill_switch = bool(data.get("kill_switch", False))
        obj._recalculate_fee_reserve()
        # Un ancien fichier peut avoir une réserve incohérente ; on la borne
        # au cash plutôt que de fabriquer un découvert.
        if obj.reserved_cash + obj.fee_reserve_cash > obj.cash + EPS:
            obj.reserved_cash = max(0.0, obj.cash - obj.fee_reserve_cash)
        obj._assert_invariants()
        return obj


def load_portfolio(path: str, portfolio: Portfolio, reference_price: Optional[float] = None) -> Portfolio:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return portfolio
    return Portfolio.from_dict(
        data,
        initial_capital=portfolio.initial_capital,
        reference_price=reference_price,
        symbol=portfolio.symbol,
        quote_currency=portfolio.quote_currency,
        fee_rate=portfolio.fee_rate,
        spread=portfolio.spread,
        slippage=portfolio.slippage,
        max_notional_per_trade=portfolio.max_notional_per_trade,
        min_notional=portfolio.min_notional,
        allocation_pct=portfolio.allocation_pct,
        max_position_pct=portfolio.max_position_pct,
        max_total_exposure_pct=portfolio.max_total_exposure_pct,
        max_risk_per_position_pct=portfolio.max_risk_per_position_pct,
        min_cash_reserve=portfolio.min_cash_reserve,
        fee_reserve_multiplier=portfolio.fee_reserve_multiplier,
        participation_rate=portfolio.participation_rate,
        stop_loss_pct=portfolio.stop_loss_pct,
        max_daily_loss_pct=portfolio.max_daily_loss_pct,
        max_position_days=portfolio.max_position_days,
        profit_levels=portfolio.profit_levels,
        profit_fractions=portfolio.profit_fractions,
        trailing_stop_pct=portfolio.trailing_stop_pct,
        paper=True,
    )


def save_portfolio(portfolio: Portfolio, path: str) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="portfolio-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(portfolio.to_dict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def portfolio_from_config(config: Dict[str, Any]) -> Portfolio:
    """Construit un registre depuis la configuration validée."""
    execution = dict(config.get("execution", {}))
    risk = dict(config.get("risk", {}))
    if str(config.get("strategy_mode", "")).lower() == "buy_hold":
        # Le mode achat-et-gardé expose presque tout le capital d'un coup ;
        # il surcharge allocation, plafonds et budget de risque.
        overrides = config.get("buy_hold") or {}
        for name in ("allocation_pct", "max_position_pct",
                     "max_total_exposure_pct", "max_notional_per_trade"):
            if name in overrides:
                execution[name] = overrides[name]
        if "max_risk_per_position_pct" in overrides:
            risk["max_risk_per_position_pct"] = overrides["max_risk_per_position_pct"]
    return Portfolio(
        initial_capital=float(config.get("initial_capital", 1000.0)),
        symbol=str(config.get("symbol", "BTCEUR")),
        quote_currency=str(config.get("quote_currency", "EUR")),
        fee_rate=float(execution.get("fee_rate", 0.001)),
        spread=float(execution.get("spread", 0.002)),
        slippage=float(execution.get("slippage", 0.0005)),
        max_notional_per_trade=float(execution.get("max_notional_per_trade", 250.0)),
        min_notional=float(execution.get("min_notional", 5.0)),
        allocation_pct=float(execution.get("allocation_pct", 0.20)),
        max_position_pct=float(execution.get("max_position_pct", 0.25)),
        max_total_exposure_pct=float(execution.get("max_total_exposure_pct", 0.50)),
        max_risk_per_position_pct=float(risk.get("max_risk_per_position_pct", 0.02)),
        min_cash_reserve=float(execution.get("min_cash_reserve", 50.0)),
        fee_reserve_multiplier=float(execution.get("fee_reserve_multiplier", 1.10)),
        participation_rate=float(execution.get("participation_rate", 1.0)),
        stop_loss_pct=float(risk.get("stop_loss_pct", 0.10)),
        max_daily_loss_pct=float(risk.get("max_daily_loss_pct", 0.03)),
        max_position_days=float(risk.get("max_position_days", 30)),
        profit_levels=risk.get("profit_levels", [0.05, 0.10, 0.20]),
        profit_fractions=risk.get("profit_fractions", [0.25, 0.25, 0.20]),
        trailing_stop_pct=float(risk.get("trailing_stop_pct", 0.08)),
        paper=True,
        kill_switch=bool(config.get("kill_switch", False)),
    )
