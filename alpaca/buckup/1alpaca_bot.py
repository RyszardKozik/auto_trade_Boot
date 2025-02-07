import os
import logging
from time import sleep
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestTradeRequest

# Load environment variables
load_dotenv(".env")

# Configure logging
logger = logging.getLogger("AlpacaTradingBot")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
logger.addHandler(console_handler)

# Set trading mode and API credentials
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()
API_KEY = os.getenv(f"{TRADING_MODE.upper()}_API_KEY")
API_SECRET = os.getenv(f"{TRADING_MODE.upper()}_SECRET_KEY")
BASE_URL = os.getenv(f"{TRADING_MODE.upper()}_BASE_URL")

logger.info(f"Running in {TRADING_MODE.upper()} mode.")

# Initialize Alpaca Clients
trading_client = TradingClient(api_key=API_KEY, secret_key=API_SECRET, paper=(TRADING_MODE == "paper"))
crypto_data_client = CryptoHistoricalDataClient(api_key=API_KEY, secret_key=API_SECRET)

logger.info("Connected to Alpaca API successfully.")

# Bot configuration
ASSETS = ["DOGE/USD", "BCH/USD", "USDT/USD"]
ALLOCATION = 10  # Amount in USD per trade
CHECK_INTERVAL = 300  # Time between evaluations in seconds
TAKE_PROFIT_PERCENT = 10  # Profit percentage to trigger sell
STOP_LOSS_PERCENT = 5  # Loss percentage to trigger sell

# Track active positions
positions = {}

def get_crypto_price(symbol):
    """Fetch the latest price of a crypto asset."""
    try:
        request_params = CryptoLatestTradeRequest(symbol_or_symbols=[symbol])
        response = crypto_data_client.get_crypto_latest_trade(request_params)
        latest_trade = response[symbol]
        return latest_trade.price
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return None

def place_order(symbol, allocation, side):
    """Place a market order for the specified symbol."""
    try:
        price = get_crypto_price(symbol)
        if not price:
            logger.warning(f"Price unavailable for {symbol}. Skipping.")
            return

        qty = round(allocation / price, 4)
        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.IOC,
        )
        trading_client.submit_order(order_request)
        logger.info(f"Order {'bought' if side == OrderSide.BUY else 'sold'}: {symbol}, Qty: {qty}, Allocation: ${allocation}")
    except Exception as e:
        logger.error(f"Error placing order for {symbol}: {e}")

def check_take_profit_and_stop_loss():
    """Check each position for take-profit or stop-loss conditions."""
    global positions
    for symbol, data in list(positions.items()):
        current_price = get_crypto_price(symbol)
        if not current_price:
            continue

        entry_price = data["entry_price"]
        qty = data["qty"]

        # Calculate profit/loss percentage
        profit_loss_percent = ((current_price - entry_price) / entry_price) * 100

        if profit_loss_percent >= TAKE_PROFIT_PERCENT:
            logger.info(f"Take-profit triggered for {symbol} at {current_price} (+{profit_loss_percent:.2f}%).")
            place_order(symbol, qty * current_price, OrderSide.SELL)
            del positions[symbol]  # Remove from active positions
        elif profit_loss_percent <= -STOP_LOSS_PERCENT:
            logger.info(f"Stop-loss triggered for {symbol} at {current_price} ({profit_loss_percent:.2f}%).")
            place_order(symbol, qty * current_price, OrderSide.SELL)
            del positions[symbol]  # Remove from active positions

def main():
    global positions
    logger.info("Starting trading bot.")

    while True:
        try:
            # Check active positions for take-profit and stop-loss conditions
            check_take_profit_and_stop_loss()

            # Evaluate new trades
            for asset in ASSETS:
                if asset in positions:
                    logger.info(f"Skipping {asset} (already in position).")
                    continue

                logger.info(f"Evaluating asset: {asset}")
                price = get_crypto_price(asset)
                if price:
                    qty = round(ALLOCATION / price, 4)
                    positions[asset] = {"entry_price": price, "qty": qty}
                    place_order(asset, ALLOCATION, OrderSide.BUY)

            logger.info(f"Sleeping for {CHECK_INTERVAL} seconds.")
            sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Bot stopped manually.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
