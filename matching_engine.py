"""A limit order book matching engine with price-time priority.

This module has no Streamlit (or any UI) dependency, so it can be unit tested
on its own. ``order_book.py`` is the Streamlit front end that uses it.

Matching rules
--------------
* **Price priority:** a buy matches the lowest-priced sell first; a sell
  matches the highest-priced buy first.
* **Time priority:** among orders at the same price, the one that arrived
  first matches first (FIFO).
* **Trade price:** trades execute at the *resting* order's price, so an
  incoming order can receive a better price than the one it asked for.
* **Market orders:** match against whatever is available. Any unfilled
  remainder is cancelled, never rested in the book.
"""

from __future__ import annotations

import heapq
import itertools
import math
import numbers
from dataclasses import dataclass
from typing import Optional

BUY = "buy"
SELL = "sell"

OPEN = "open"
FILLED = "filled"
CANCELLED = "cancelled"


@dataclass
class Order:
    """A single order. ``price`` is ``None`` for a market order."""

    order_id: int
    side: str
    price: Optional[float]
    quantity: int  # original size
    remaining: int  # unfilled size
    sequence: int  # arrival order, used for time priority
    status: str = OPEN

    @property
    def is_market(self) -> bool:
        return self.price is None

    @property
    def filled(self) -> int:
        return self.quantity - self.remaining


@dataclass(frozen=True)
class Trade:
    """One execution between an incoming (aggressor) and a resting order."""

    trade_id: int
    aggressor_side: str  # side of the incoming order that triggered the trade
    price: float  # the resting order's price
    quantity: int
    aggressor_order_id: int
    resting_order_id: int


@dataclass
class OrderResult:
    """What happened to an order when it was submitted."""

    order: Order
    trades: list[Trade]

    @property
    def filled_quantity(self) -> int:
        return sum(t.quantity for t in self.trades)

    @property
    def outcome(self) -> str:
        """One of: filled, partially_filled, resting, cancelled."""
        order = self.order
        if order.remaining == 0:
            return "filled"
        if order.status == OPEN:
            return "partially_filled" if self.trades else "resting"
        return "cancelled"  # unfilled remainder of a market order


class OrderBook:
    """Limit order book supporting limit orders, market orders and cancels."""

    def __init__(self) -> None:
        # Heap entries are (price_key, sequence, order). ``sequence`` is unique,
        # so ties on price are broken by arrival time and Order objects are
        # never compared with each other.
        self._buys: list[tuple[float, int, Order]] = []  # price_key = -price
        self._sells: list[tuple[float, int, Order]] = []  # price_key = +price
        self._orders: dict[int, Order] = {}  # open orders only
        self._next_order_id = 0
        self._sequence = itertools.count()
        self._next_trade_id = 0
        self.trades: list[Trade] = []

    # ------------------------------------------------------------------ submit

    def add_order(self, side: str, price: Optional[float], quantity: int) -> OrderResult:
        """Submit an order. Use ``price=None`` for a market order.

        Raises ``ValueError`` for an invalid side, price or quantity.
        """
        self._validate(side, price, quantity)
        order = Order(
            order_id=self._next_order_id,
            side=side,
            price=None if price is None else float(price),
            quantity=int(quantity),
            remaining=int(quantity),
            sequence=next(self._sequence),
        )
        self._next_order_id += 1

        trades = self._match(order)

        if order.remaining == 0:
            order.status = FILLED
        elif order.is_market:
            order.status = CANCELLED  # never rest a market order
        else:
            self._rest(order)
        return OrderResult(order=order, trades=trades)

    def cancel_order(self, order_id: int) -> bool:
        """Cancel an open order. Returns False if it is unknown or already done."""
        order = self._orders.pop(order_id, None)
        if order is None:
            return False
        order.status = CANCELLED
        # The stale heap entry is skipped lazily when it reaches the top.
        return True

    # ------------------------------------------------------------------- views

    def best_bid(self) -> Optional[float]:
        order = self._peek(self._buys)
        return order.price if order else None

    def best_ask(self) -> Optional[float]:
        order = self._peek(self._sells)
        return order.price if order else None

    def spread(self) -> Optional[float]:
        bid, ask = self.best_bid(), self.best_ask()
        if bid is None or ask is None:
            return None
        return ask - bid

    def get_book(self) -> tuple[list[Order], list[Order]]:
        """Open (buys, sells), each in matching order: best price, then oldest."""
        buys = sorted(e for e in self._buys if e[2].status == OPEN)
        sells = sorted(e for e in self._sells if e[2].status == OPEN)
        return [e[2] for e in buys], [e[2] for e in sells]

    def depth(self) -> tuple[list[tuple[float, int]], list[tuple[float, int]]]:
        """Total open quantity per price level as (bids, asks), best price first."""
        buys, sells = self.get_book()
        return _aggregate(buys), _aggregate(sells)

    # --------------------------------------------------------------- internals

    @staticmethod
    def _validate(side: str, price: Optional[float], quantity: int) -> None:
        if side not in (BUY, SELL):
            raise ValueError(f"side must be '{BUY}' or '{SELL}', got {side!r}")
        if isinstance(quantity, bool) or not isinstance(quantity, numbers.Integral) or quantity <= 0:
            raise ValueError(f"quantity must be a positive integer, got {quantity!r}")
        if price is not None and not (math.isfinite(price) and price > 0):
            raise ValueError(f"price must be a positive number, got {price!r}")

    def _rest(self, order: Order) -> None:
        if order.side == BUY:
            heapq.heappush(self._buys, (-order.price, order.sequence, order))
        else:
            heapq.heappush(self._sells, (order.price, order.sequence, order))
        self._orders[order.order_id] = order

    @staticmethod
    def _peek(heap: list[tuple[float, int, Order]]) -> Optional[Order]:
        """Best open order on one side, discarding cancelled/filled leftovers."""
        while heap and heap[0][2].status != OPEN:
            heapq.heappop(heap)
        return heap[0][2] if heap else None

    @staticmethod
    def _crosses(incoming: Order, resting: Order) -> bool:
        if incoming.is_market:
            return True
        if incoming.side == BUY:
            return resting.price <= incoming.price
        return resting.price >= incoming.price

    def _match(self, incoming: Order) -> list[Trade]:
        opposite = self._sells if incoming.side == BUY else self._buys
        trades: list[Trade] = []
        while incoming.remaining > 0:
            resting = self._peek(opposite)
            if resting is None or not self._crosses(incoming, resting):
                break
            quantity = min(incoming.remaining, resting.remaining)
            incoming.remaining -= quantity
            resting.remaining -= quantity
            trade = Trade(
                trade_id=self._next_trade_id,
                aggressor_side=incoming.side,
                price=resting.price,
                quantity=quantity,
                aggressor_order_id=incoming.order_id,
                resting_order_id=resting.order_id,
            )
            self._next_trade_id += 1
            trades.append(trade)
            self.trades.append(trade)
            if resting.remaining == 0:
                resting.status = FILLED
                self._orders.pop(resting.order_id, None)
                heapq.heappop(opposite)
        return trades


def _aggregate(orders: list[Order]) -> list[tuple[float, int]]:
    levels: dict[float, int] = {}
    for order in orders:  # already sorted best-first, dict keeps that order
        levels[order.price] = levels.get(order.price, 0) + order.remaining
    return list(levels.items())
