"""Streamlit front end for the limit order book simulator.

Run with:  streamlit run order_book.py

All matching logic lives in ``matching_engine.py``; this file only handles
input, display and export.
"""

from dataclasses import asdict

import pandas as pd
import streamlit as st

from matching_engine import BUY, SELL, OrderBook, OrderResult

SAMPLE_ORDERS = [
    (BUY, 99, 10),
    (BUY, 99, 5),
    (BUY, 98, 15),
    (BUY, 97, 20),
    (SELL, 101, 8),
    (SELL, 101, 4),
    (SELL, 102, 12),
    (SELL, 103, 20),
]

st.set_page_config(page_title="Limit Order Book Simulator", layout="wide")
st.title("Limit Order Book Simulator")
st.caption(
    "Orders match by price priority, then time priority. "
    "Trades execute at the resting order's price."
)

if "order_book" not in st.session_state:
    st.session_state.order_book = OrderBook()
book: OrderBook = st.session_state.order_book


def show_result(result: OrderResult) -> None:
    """Tell the user what happened to the order they just submitted."""
    order = result.order
    kind = "market" if order.is_market else f"limit @ {order.price:,.2f}"
    head = f"Order {order.order_id} ({order.side} {order.quantity} {kind})"
    outcome = result.outcome
    if outcome == "filled":
        st.success(f"{head}: fully filled in {len(result.trades)} trade(s).")
    elif outcome == "partially_filled":
        st.info(f"{head}: {result.filled_quantity} filled, {order.remaining} resting in the book.")
    elif outcome == "resting":
        st.info(f"{head}: no match, now resting in the book.")
    elif result.trades:  # market order that ran out of liquidity
        st.warning(
            f"{head}: {result.filled_quantity} filled, "
            f"{order.remaining} cancelled (no more liquidity)."
        )
    else:
        st.warning(f"{head}: nothing to match against, so it was cancelled.")


def order_rows(orders: list) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ID": o.order_id,
                "Price": o.price,
                "Remaining": o.remaining,
                "Original": o.quantity,
            }
            for o in orders
        ],
        columns=["ID", "Price", "Remaining", "Original"],
    )


# ------------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("Book controls")
    if st.button("Load sample orders", help="Adds a few resting buy and sell orders."):
        for side, price, quantity in SAMPLE_ORDERS:
            book.add_order(side, price, quantity)
    if st.button("Reset book", help="Clears all orders and trades."):
        st.session_state.order_book = book = OrderBook()

# ------------------------------------------------------------- order entry

st.subheader("Place or cancel an order")
action = st.selectbox("Action", ["Place Limit Order", "Place Market Order", "Cancel Order"])

if action == "Place Limit Order":
    with st.form("limit_order"):
        side = st.selectbox("Side", [BUY, SELL])
        price = st.number_input("Price", min_value=0.01, value=100.0, step=1.0, format="%.2f")
        quantity = st.number_input("Quantity", min_value=1, value=10, step=1)
        if st.form_submit_button("Submit limit order"):
            show_result(book.add_order(side, price, quantity))

elif action == "Place Market Order":
    with st.form("market_order"):
        side = st.selectbox("Side", [BUY, SELL])
        quantity = st.number_input("Quantity", min_value=1, value=10, step=1)
        if st.form_submit_button("Submit market order"):
            show_result(book.add_order(side, None, quantity))

else:
    with st.form("cancel_order"):
        order_id = st.number_input("Order ID to cancel", min_value=0, value=0, step=1)
        if st.form_submit_button("Cancel order"):
            if book.cancel_order(order_id):
                st.success(f"Order {order_id} cancelled.")
            else:
                st.warning(f"Order {order_id} is not open (unknown, filled or already cancelled).")

# ----------------------------------------------------------------- analytics

st.subheader("Order book analytics")
best_bid, best_ask, spread = book.best_bid(), book.best_ask(), book.spread()


def fmt(value):
    return "N/A" if value is None else f"{value:,.2f}"


col1, col2, col3 = st.columns(3)
col1.metric("Best bid", fmt(best_bid))
col2.metric("Best ask", fmt(best_ask))
col3.metric("Spread", fmt(spread))

# --------------------------------------------------------------------- depth

st.subheader("Market depth")
bids, asks = book.depth()
if bids or asks:
    depth = (
        pd.DataFrame({"Bids": dict(bids), "Asks": dict(asks)})
        .sort_index()
        .fillna(0)
        .rename_axis("Price")
    )
    st.bar_chart(depth, color=["#2e8b57", "#c0392b"])
    st.caption("Total open quantity at each price level.")
else:
    st.caption("The book is empty. Place an order or load the sample orders from the sidebar.")

# -------------------------------------------------------------------- tables

st.subheader("Current order book")
buys, sells = book.get_book()
left, right = st.columns(2)
left.markdown("**Buy orders** (best first)")
left.dataframe(order_rows(buys), hide_index=True)
right.markdown("**Sell orders** (best first)")
right.dataframe(order_rows(sells), hide_index=True)

# ------------------------------------------------------------------- history

st.subheader("Trade history")
if book.trades:
    trades = pd.DataFrame([asdict(t) for t in book.trades])
    st.dataframe(trades.iloc[::-1], hide_index=True)  # newest first on screen
    st.download_button(
        "Download trades (CSV)",
        trades.to_csv(index=False),
        file_name="trades.csv",
        mime="text/csv",
    )
else:
    st.caption("No trades yet.")
