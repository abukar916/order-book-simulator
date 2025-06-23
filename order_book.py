import heapq
import streamlit as st
import pandas as pd

class Order:
    def __init__(self, order_id, side, price, quantity):
        self.order_id = order_id
        self.side = side
        self.price = price
        self.quantity = quantity

class OrderBook:
    def __init__(self):
        self.buys = []
        self.sells = []
        self.order_id_counter = 0
        self.order_map = {}
        self.trades = []  # For trade log

    def add_order(self, side, price, quantity):
        order = Order(self.order_id_counter, side, price, quantity)
        self.order_id_counter += 1
        self.order_map[order.order_id] = order
        self.match(order)

    def match(self, order):
        if order.price is None:
            order.price = float('inf') if order.side == 'buy' else 0.0

        if order.side == 'buy':
            while self.sells and order.quantity > 0:
                best_sell_price, sell_order = self.sells[0]
                if sell_order.price <= order.price:
                    trade_qty = min(order.quantity, sell_order.quantity)
                    st.write(f"Trade executed: BUY {trade_qty} @ {sell_order.price}")
                    self.trades.append({'side': 'BUY', 'price': sell_order.price, 'quantity': trade_qty})
                    order.quantity -= trade_qty
                    sell_order.quantity -= trade_qty
                    if sell_order.quantity == 0:
                        heapq.heappop(self.sells)
                        self.order_map.pop(sell_order.order_id, None)
                else:
                    break
            if order.quantity > 0:
                heapq.heappush(self.buys, (-order.price, order))
        else:
            while self.buys and order.quantity > 0:
                best_buy_price, buy_order = self.buys[0]
                best_buy_price = -best_buy_price
                if buy_order.price >= order.price:
                    trade_qty = min(order.quantity, buy_order.quantity)
                    st.write(f"Trade executed: SELL {trade_qty} @ {buy_order.price}")
                    self.trades.append({'side': 'SELL', 'price': buy_order.price, 'quantity': trade_qty})
                    order.quantity -= trade_qty
                    buy_order.quantity -= trade_qty
                    if buy_order.quantity == 0:
                        heapq.heappop(self.buys)
                        self.order_map.pop(buy_order.order_id, None)
                else:
                    break
            if order.quantity > 0:
                heapq.heappush(self.sells, (order.price, order))

    def cancel_order(self, order_id):
        order = self.order_map.pop(order_id, None)
        if order:
            order.quantity = 0
            st.write(f"Order {order_id} cancelled.")
        else:
            st.write(f"Order {order_id} not found.")

    def get_book(self):
        buys_sorted = sorted([(-price, order) for price, order in self.buys if order.quantity > 0], reverse=True)
        sells_sorted = sorted([(price, order) for price, order in self.sells if order.quantity > 0])
        return buys_sorted, sells_sorted

    def get_best_bid_ask(self):
        best_bid = -self.buys[0][0] if self.buys else None
        best_ask = self.sells[0][0] if self.sells else None
        return best_bid, best_ask

# Streamlit UI
st.title("Limit Order Book Simulator")

if 'order_book' not in st.session_state:
    st.session_state.order_book = OrderBook()

option = st.selectbox("Choose action", ["Place Limit Order", "Place Market Order", "Cancel Order"])

if option == "Place Limit Order":
    side = st.selectbox("Side", ["buy", "sell"])
    price = st.number_input("Price", min_value=0.0, step=1.0)
    qty = st.number_input("Quantity", min_value=1, step=1)
    if st.button("Submit Limit Order"):
        st.session_state.order_book.add_order(side, price, qty)

elif option == "Place Market Order":
    side = st.selectbox("Side", ["marketbuy", "marketsell"])
    qty = st.number_input("Quantity", min_value=1, step=1)
    if st.button("Submit Market Order"):
        side_actual = 'buy' if side == 'marketbuy' else 'sell'
        st.session_state.order_book.add_order(side_actual, None, qty)

elif option == "Cancel Order":
    order_id = st.number_input("Order ID to cancel", min_value=0, step=1)
    if st.button("Cancel Order"):
        st.session_state.order_book.cancel_order(order_id)

# Show analytics
st.subheader("Order Book Analytics")
best_bid, best_ask = st.session_state.order_book.get_best_bid_ask()
spread = round(best_ask - best_bid, 2) if best_bid and best_ask else None

col1, col2, col3 = st.columns(3)
col1.metric("Best Bid", best_bid if best_bid else "N/A")
col2.metric("Best Ask", best_ask if best_ask else "N/A")
col3.metric("Spread", spread if spread else "N/A")

# Show order book
st.subheader("Current Order Book")
buys, sells = st.session_state.order_book.get_book()

buy_data = [{"ID": o.order_id, "Price": p, "Quantity": o.quantity} for p, o in buys]
sell_data = [{"ID": o.order_id, "Price": p, "Quantity": o.quantity} for p, o in sells]

col1, col2 = st.columns(2)
col1.write("### Buy Orders")
col1.dataframe(pd.DataFrame(buy_data))

col2.write("### Sell Orders")
col2.dataframe(pd.DataFrame(sell_data))

# Show trade log
st.subheader("Trade History")
if st.session_state.order_book.trades:
    trade_df = pd.DataFrame(st.session_state.order_book.trades)
    st.dataframe(trade_df)
    st.download_button("Download Trades CSV", trade_df.to_csv(index=False), "trades.csv", "text/csv")
else:
    st.write("No trades yet.")
