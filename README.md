# Limit Order Book Simulator

An interactive limit order book built in Python. Place limit and market orders, watch them match by **price-time priority**, and inspect the book, the spread and the trade history. The matching engine is a standalone, tested module; the Streamlit app is a thin front end on top of it.

![Screenshot of the simulator showing the order entry form, best bid/ask, depth chart, order tables and trade history](docs/screenshot.png)

## Features

- **Limit and market orders** on both sides of the book
- **Price-time priority matching:** best price first, and first-in-first-out among orders at the same price
- **Partial fills:** unfilled quantity keeps resting in the book
- **Order cancellation** by order ID
- **Live analytics:** best bid, best ask and spread
- **Market depth chart** showing total quantity at each price level
- **Trade history** with CSV export
- **Input validation** (positive prices and whole-number quantities only)
- **Automated tests**, including randomised order-flow checks

## How matching works

| Rule | Behaviour |
|---|---|
| Price priority | A buy matches the lowest-priced sell first. A sell matches the highest-priced buy first. |
| Time priority | At the same price, the order that arrived first is filled first. |
| Trade price | Trades execute at the **resting** order's price, so an aggressive order can get a better price than its limit. |
| Market orders | Match against whatever liquidity exists. Any unfilled remainder is **cancelled**, never rested. |
| Cancels | Only open orders can be cancelled. Filled, cancelled or unknown IDs are reported as not open. |

**Example** (the "Load sample orders" button, then a buy of 15 @ 101):

- The book has two sells at 101: order 4 for 8 units, then order 5 for 4 units.
- The buy fills 8 against order 4, then 4 against order 5, both at 101. That is 12 units across two trades.
- The remaining 3 units rest as a new best bid at 101. The best ask is now 102, so the spread is 1.00.

## Getting started

Requires Python 3.10 or newer (developed and tested on Python 3.13).

```bash
git clone https://github.com/abukar916/order-book-simulator.git
cd order-book-simulator

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
streamlit run order_book.py
```

The app opens at http://localhost:8501. Use **Load sample orders** in the sidebar to populate the book, and **Reset book** to start again.

## Running the tests

```bash
pip install pytest
pytest
```

The suite covers:

- resting, crossing and partial-fill behaviour for both sides
- price priority across levels and time priority at a single level
- market orders, including sweeping several levels and running out of liquidity
- cancellation, including cancelling a filled, unknown or already-cancelled order
- input validation
- 20 seeded random order flows of 300 actions each. After every action the book must not be crossed (best bid below best ask). At the end, every trade must respect both orders' limit prices, and the quantity filled on each order must equal what its trades add up to

## Project structure

```
order-book-simulator/
├── matching_engine.py        # OrderBook, Order, Trade: no UI dependencies
├── order_book.py             # Streamlit app
├── test_matching_engine.py   # pytest suite
├── requirements.txt
└── docs/screenshot.png
```

## Design notes

- Each side of the book is a binary heap of `(price_key, sequence, order)`. Buys use the negated price so the highest bid is on top. The unique, increasing `sequence` number breaks price ties by arrival time, which is what gives FIFO priority (and means orders are never compared with each other).
- Cancellation is **lazy**: a cancelled order is marked and left in the heap, then discarded when it reaches the top. This keeps cancel at O(1), at the cost of a little extra work later.
- Resting an order and each fill cost O(log n). Reading the best bid or ask is O(1) amortised.
- The engine never touches Streamlit, so it can be tested directly and reused by something other than this UI.

## Limitations

- Single user, in memory: the book lives in the Streamlit session and is lost when the session ends.
- Prices are floats with no tick size. A production engine would use integer ticks or `Decimal`.
- No self-trade prevention, order amendment, or other order types such as immediate-or-cancel or fill-or-kill.
- No fees, latency or multiple instruments.

## Ideas for next steps

- A random order-flow generator to study how the spread and mid-price evolve
- Integer tick prices
- Order amendment and immediate-or-cancel orders
