import math
import random

import pytest

from matching_engine import BUY, CANCELLED, FILLED, OPEN, SELL, OrderBook


# ---------------------------------------------------------------- resting orders


def test_limit_order_with_no_counterparty_rests():
    book = OrderBook()
    result = book.add_order(BUY, 100, 5)

    assert result.trades == []
    assert result.outcome == "resting"
    assert book.best_bid() == 100
    assert book.best_ask() is None
    assert book.spread() is None


def test_spread_is_ask_minus_bid():
    book = OrderBook()
    book.add_order(BUY, 99, 1)
    book.add_order(SELL, 101, 1)

    assert book.spread() == 2


def test_order_ids_are_sequential_from_zero():
    book = OrderBook()
    ids = [book.add_order(BUY, 100, 1).order.order_id for _ in range(3)]
    assert ids == [0, 1, 2]


# --------------------------------------------------------------------- matching


def test_buy_crossing_a_sell_trades_at_the_resting_price():
    book = OrderBook()
    book.add_order(SELL, 100, 5)
    result = book.add_order(BUY, 105, 5)  # willing to pay more than needed

    assert [(t.price, t.quantity) for t in result.trades] == [(100, 5)]
    assert result.outcome == "filled"
    assert book.best_bid() is None and book.best_ask() is None


def test_sell_crossing_a_buy_trades_at_the_resting_price():
    book = OrderBook()
    book.add_order(BUY, 100, 5)
    result = book.add_order(SELL, 95, 5)

    assert [(t.price, t.quantity) for t in result.trades] == [(100, 5)]
    assert result.trades[0].aggressor_side == SELL


def test_orders_that_do_not_cross_do_not_trade():
    book = OrderBook()
    book.add_order(SELL, 101, 5)
    result = book.add_order(BUY, 100, 5)

    assert result.trades == []
    assert book.best_bid() == 100 and book.best_ask() == 101


def test_partial_fill_leaves_remainder_of_the_resting_order():
    book = OrderBook()
    book.add_order(BUY, 100, 10)
    result = book.add_order(SELL, 100, 4)

    assert result.outcome == "filled"
    buys, _ = book.get_book()
    assert [(o.price, o.remaining) for o in buys] == [(100, 6)]


def test_partial_fill_rests_the_remainder_of_the_incoming_order():
    book = OrderBook()
    book.add_order(SELL, 100, 3)
    result = book.add_order(BUY, 100, 10)

    assert result.outcome == "partially_filled"
    assert result.filled_quantity == 3
    buys, sells = book.get_book()
    assert [(o.price, o.remaining) for o in buys] == [(100, 7)]
    assert sells == []


def test_price_priority_best_price_matches_first():
    book = OrderBook()
    book.add_order(SELL, 101, 5)
    book.add_order(SELL, 100, 5)  # arrives later but is the better price
    result = book.add_order(BUY, 105, 7)

    assert [(t.price, t.quantity) for t in result.trades] == [(100, 5), (101, 2)]


def test_time_priority_earlier_order_at_same_price_matches_first():
    book = OrderBook()
    first = book.add_order(SELL, 100, 5).order
    second = book.add_order(SELL, 100, 5).order
    result = book.add_order(BUY, 100, 5)

    assert [t.resting_order_id for t in result.trades] == [first.order_id]
    assert first.status == FILLED
    assert second.status == OPEN and second.remaining == 5


def test_time_priority_on_the_buy_side_too():
    book = OrderBook()
    first = book.add_order(BUY, 100, 5).order
    second = book.add_order(BUY, 100, 5).order
    result = book.add_order(SELL, 100, 7)

    assert [(t.resting_order_id, t.quantity) for t in result.trades] == [
        (first.order_id, 5),
        (second.order_id, 2),
    ]


def test_many_orders_at_one_price_do_not_crash():
    # Regression: tied prices used to make the heap compare Order objects.
    book = OrderBook()
    for _ in range(50):
        book.add_order(BUY, 100, 1)
        book.add_order(SELL, 200, 1)
    assert len(book.get_book()[0]) == 50


# ---------------------------------------------------------------- market orders


def test_market_order_sweeps_multiple_price_levels():
    book = OrderBook()
    book.add_order(SELL, 100, 2)
    book.add_order(SELL, 105, 2)
    result = book.add_order(BUY, None, 4)

    assert [(t.price, t.quantity) for t in result.trades] == [(100, 2), (105, 2)]
    assert result.outcome == "filled"


def test_market_order_into_an_empty_book_is_cancelled_not_rested():
    # Regression: it used to rest at an infinite price and show as best bid.
    book = OrderBook()
    result = book.add_order(BUY, None, 5)

    assert result.trades == []
    assert result.outcome == "cancelled"
    assert result.order.status == CANCELLED
    assert book.best_bid() is None
    assert book.get_book() == ([], [])


def test_market_order_remainder_is_cancelled_after_partial_fill():
    book = OrderBook()
    book.add_order(SELL, 100, 3)
    result = book.add_order(BUY, None, 10)

    assert result.filled_quantity == 3
    assert result.outcome == "cancelled"
    assert book.best_bid() is None


# ----------------------------------------------------------------------- cancel


def test_cancel_removes_the_order_from_the_book():
    book = OrderBook()
    order = book.add_order(SELL, 101, 5).order

    assert book.cancel_order(order.order_id) is True
    assert order.status == CANCELLED
    assert book.best_ask() is None  # used to keep reporting the cancelled order
    assert book.get_book() == ([], [])


def test_cancelled_order_never_trades():
    # Regression: a cancelled order used to produce a zero-quantity trade.
    book = OrderBook()
    cancelled = book.add_order(SELL, 100, 5).order
    book.add_order(SELL, 101, 5)
    book.cancel_order(cancelled.order_id)
    result = book.add_order(BUY, 105, 3)

    assert [(t.price, t.quantity) for t in result.trades] == [(101, 3)]
    assert all(t.quantity > 0 for t in book.trades)


def test_cancel_unknown_order_returns_false():
    assert OrderBook().cancel_order(123) is False


def test_cancel_twice_returns_false_the_second_time():
    book = OrderBook()
    order = book.add_order(BUY, 100, 1).order
    assert book.cancel_order(order.order_id) is True
    assert book.cancel_order(order.order_id) is False


def test_cancel_after_full_fill_returns_false():
    # Regression: filled orders used to stay cancellable.
    book = OrderBook()
    resting = book.add_order(SELL, 100, 5).order
    book.add_order(BUY, 100, 5)

    assert book.cancel_order(resting.order_id) is False
    assert resting.status == FILLED


def test_cancel_one_of_two_orders_at_the_same_price():
    book = OrderBook()
    first = book.add_order(BUY, 100, 5).order
    second = book.add_order(BUY, 100, 5).order
    book.cancel_order(first.order_id)
    result = book.add_order(SELL, 100, 5)

    assert [t.resting_order_id for t in result.trades] == [second.order_id]


# ------------------------------------------------------------------ depth / view


def test_depth_aggregates_quantity_per_price_level_best_first():
    book = OrderBook()
    book.add_order(BUY, 99, 2)
    book.add_order(BUY, 99, 3)
    book.add_order(BUY, 98, 4)
    book.add_order(SELL, 101, 1)
    book.add_order(SELL, 102, 6)

    bids, asks = book.depth()
    assert bids == [(99, 5), (98, 4)]
    assert asks == [(101, 1), (102, 6)]


def test_get_book_lists_orders_best_price_then_oldest_first():
    book = OrderBook()
    a = book.add_order(BUY, 100, 1).order
    b = book.add_order(BUY, 101, 1).order
    c = book.add_order(BUY, 100, 1).order

    buys, _ = book.get_book()
    assert [o.order_id for o in buys] == [b.order_id, a.order_id, c.order_id]


# ------------------------------------------------------------------- validation


@pytest.mark.parametrize("quantity", [0, -1, 1.5, "3", None, True])
def test_invalid_quantity_is_rejected(quantity):
    with pytest.raises(ValueError):
        OrderBook().add_order(BUY, 100, quantity)


@pytest.mark.parametrize("price", [0, -5, math.nan, math.inf])
def test_invalid_price_is_rejected(price):
    with pytest.raises(ValueError):
        OrderBook().add_order(BUY, price, 1)


def test_invalid_side_is_rejected():
    with pytest.raises(ValueError):
        OrderBook().add_order("hold", 100, 1)


def test_rejected_order_does_not_consume_an_order_id():
    book = OrderBook()
    with pytest.raises(ValueError):
        book.add_order(BUY, 100, 0)
    assert book.add_order(BUY, 100, 1).order.order_id == 0


# -------------------------------------------------------------- random invariants


@pytest.mark.parametrize("seed", range(20))
def test_random_order_flow_keeps_the_book_consistent(seed):
    rng = random.Random(seed)
    book = OrderBook()
    submitted = {}
    open_ids = []

    for _ in range(300):
        action = rng.random()
        if action < 0.65:
            side = rng.choice([BUY, SELL])
            price = rng.randint(95, 105)
            result = book.add_order(side, price, rng.randint(1, 10))
            submitted[result.order.order_id] = result.order
            open_ids.append(result.order.order_id)
        elif action < 0.8:
            side = rng.choice([BUY, SELL])
            result = book.add_order(side, None, rng.randint(1, 10))
            submitted[result.order.order_id] = result.order
        elif open_ids:
            book.cancel_order(rng.choice(open_ids))

        bid, ask = book.best_bid(), book.best_ask()
        assert bid is None or ask is None or bid < ask, "book must never be crossed"

    # No empty trades, and every trade respects both orders' limit prices.
    for trade in book.trades:
        assert trade.quantity > 0
        resting = submitted[trade.resting_order_id]
        aggressor = submitted[trade.aggressor_order_id]
        assert trade.price == resting.price
        if not aggressor.is_market:
            if aggressor.side == BUY:
                assert trade.price <= aggressor.price
            else:
                assert trade.price >= aggressor.price

    # Quantity is conserved: what each order filled equals what its trades say.
    traded = {}
    for trade in book.trades:
        for order_id in (trade.aggressor_order_id, trade.resting_order_id):
            traded[order_id] = traded.get(order_id, 0) + trade.quantity
    for order_id, order in submitted.items():
        assert order.filled == traded.get(order_id, 0)
        assert 0 <= order.remaining <= order.quantity

    # Every trade fills exactly two orders, so total filled is twice the volume.
    assert sum(o.filled for o in submitted.values()) == 2 * sum(t.quantity for t in book.trades)

    # Everything left in the book is genuinely open, and nothing open is missing.
    buys, sells = book.get_book()
    assert all(o.status == OPEN and o.remaining > 0 for o in buys + sells)
    expected_open = {
        oid for oid, o in submitted.items() if o.status == OPEN and o.remaining > 0
    }
    assert {o.order_id for o in buys + sells} == expected_open
