# Order Book Simulator

## 📈 Description
An interactive **Streamlit web app** that simulates a simple limit order book. It supports:

- Placing limit and market buy/sell orders
- Automatic trade matching based on price-time priority
- Live order book display
- Best bid/ask price and spread analytics
- Trade history with CSV export

Perfect for students and developers learning how financial market order books operate.

## 🚀 How to Run

1. **Clone the repository:**
   ```bash
   git clone https://github.com/abukar916/order-book-simulator.git
   cd limit-order-book-streamlit
   ```

2. **(Optional) Create a virtual environment:**
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Streamlit app:**
   ```bash
   streamlit run order_book.py
   ```

5. **Open in your browser and interact with the order book!**

## 📄 Requirements

- Python 3.8+
- `streamlit`
- `pandas`

## ✅ Features

- ✅ Place limit and market orders
- ✅ Cancel orders by ID
- ✅ View live order book with buy/sell tables
- ✅ See best bid, best ask, and spread
- ✅ Download trade log as CSV

## 📂 Files

- `order_book.py` — Streamlit app source code
- `requirements.txt` — Python dependencies

