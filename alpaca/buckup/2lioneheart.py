# Import required libraries
import os  # To access environment variables
import logging  # For logging events and debugging
import json  # To save and load the bot's state in JSON format
from time import sleep  # To pause execution between trade cycles
from datetime import datetime, timedelta  # For handling date and time operations
from dotenv import load_dotenv  # To load environment variables from a .env file
from alpaca_trade_api.rest import REST, TimeFrame  # Alpaca API for trading and market data

# Load environment variables from the .env file
load_dotenv(".env")

# Configure logging (no timestamps in console output)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",  # Simplified log format without timestamps
    handlers=[
        logging.StreamHandler(),  # Console logging
    #    logging.FileHandler("lioneheart.log")  # Save logs to a file
    ]
)
logger = logging.getLogger("TradingBot")  # Create a logger named 'TradingBot'

# Set trading mode and load API credentials
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()  # Default to "paper" mode

# Load credentials based on the trading mode
if TRADING_MODE == "live":
    API_KEY = os.getenv("LIONHEART_LIVE_API_KEY")
    API_SECRET = os.getenv("LIONHEART_LIVE_SECRET_KEY")
    BASE_URL = os.getenv("LIONHEART_LIVE_BASE_URL", "https://api.alpaca.markets")
    logger.info("Running in LIVE mode.")
else:
    API_KEY = os.getenv("LIONHEART_API_KEY")
    API_SECRET = os.getenv("LIONHEART_SECRET_KEY")
    BASE_URL = os.getenv("LIONHEART_BASE_URL", "https://paper-api.alpaca.markets")
    logger.info("Running in PAPER mode.")

# Verify API credentials
if not API_KEY or not API_SECRET:
    logger.error("API key or secret is missing. Check your .env file.")
    exit(1)

# Initialize the Alpaca API client
api = REST(API_KEY, API_SECRET, BASE_URL)

# Trading configuration
ASSETS = ["AAPL", "AMZN", "GOOGL"]  # List of stock assets to monitor and trade
TARGET_ALLOCATION = 300  # Max amount (in USD) to allocate per asset
CHECK_INTERVAL = 300  # Time interval (in seconds) between trade evaluations
STATE_FILE = "lioneheart_state.json"  # State file for saving the bot's current positions
MARKET_OPEN = "09:30"  # Market opening time (HH:MM)
MARKET_CLOSE = "16:00"  # Market closing time (HH:MM)
manual_stop = False  # Global flag for manual stop


def is_market_hours():
    """Check if the market is currently open."""
    now = datetime.now()
    open_time = datetime.strptime(MARKET_OPEN, "%H:%M").time()
    close_time = datetime.strptime(MARKET_CLOSE, "%H:%M").time()
    return open_time <= now.time() <= close_time


def load_state():
    """Load the bot's state from a JSON file."""
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            logger.info("State loaded successfully.")
            return state
    except FileNotFoundError:
        logger.warning("State file not found. Initializing a new state.")
        return {"positions": {}}  # Return an empty state
    except json.JSONDecodeError:
        logger.error("State file is corrupted. Initializing a new state.")
        return {"positions": {}}


def save_state(state):
    """Save the bot's state to a JSON file."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
            logger.info("State saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def fetch_prices(asset):
    """Fetch historical prices for a stock, explicitly using IEX feed."""
    try:
        now = datetime.utcnow()
        start = now - timedelta(days=7)
        start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Fetch price data from the IEX feed
        bars = api.get_bars(asset, TimeFrame.Minute, start=start_str, end=now_str, feed="iex").df
        return bars["close"].tolist()
    except Exception as e:
        logger.error(f"Error fetching prices for {asset} using IEX feed: {e}")
        return []  # Return empty list on error


def close_all_positions():
    """Manually close all open positions."""
    logger.info("Closing all open positions...")
    try:
        positions = api.list_positions()  # Fetch all open positions
        for position in positions:
            symbol = position.symbol
            qty = position.qty
            try:
                api.submit_order(symbol=symbol, qty=qty, side="sell", type="market", time_in_force="gtc")
                logger.info(f"Closed position for {symbol}. Qty: {qty}")
            except Exception as e:
                logger.error(f"Failed to close position for {symbol}: {e}")
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")


def evaluate_and_trade():
    """Evaluate market conditions and execute trades."""
    global manual_stop
    if manual_stop:
        logger.info("Manual stop triggered. Exiting trade evaluations.")
        return

    state = load_state()
    try:
        account = api.get_account()
        logger.info(f"Available cash: {account.cash}")
    except Exception as e:
        logger.error(f"Error fetching account details: {e}")
        return

    for asset in ASSETS:
        logger.info(f"Evaluating {asset}...")
        prices = fetch_prices(asset)

        if not prices:
            logger.warning(f"No price data for {asset}. Skipping.")
            continue

        # Calculate Simple Moving Averages (SMAs)
        short_sma = sum(prices[-10:]) / 10 if len(prices) >= 10 else None
        long_sma = sum(prices[-50:]) / 50 if len(prices) >= 50 else None

        if not short_sma or not long_sma:
            logger.warning(f"Not enough data for SMA calculation for {asset}. Skipping.")
            continue

        logger.info(f"Short SMA: {short_sma}, Long SMA: {long_sma}")

        # Buy condition
        if short_sma > long_sma and asset not in state.get("positions", {}):
            logger.info(f"Buying {asset}...")
            qty = float(account.cash) / prices[-1]
            try:
                api.submit_order(symbol=asset, qty=qty, side="buy", type="market", time_in_force="day")
                state["positions"][asset] = {"qty": qty, "entry_price": prices[-1]}
                save_state(state)
                logger.info(f"Bought {asset}, Qty: {qty}")
            except Exception as e:
                logger.error(f"Failed to buy {asset}: {e}")

        # Sell condition
        elif short_sma < long_sma and asset in state.get("positions", {}):
            logger.info(f"Selling {asset}...")
            position = state["positions"].pop(asset)
            try:
                api.submit_order(symbol=asset, qty=position["qty"], side="sell", type="market", time_in_force="gtc")
                save_state(state)
                logger.info(f"Sold {asset}, Qty: {position['qty']}")
            except Exception as e:
                logger.error(f"Failed to sell {asset}: {e}")


def main():
    """Main function to run the trading bot."""
    logger.info("Starting trading bot...")
    global manual_stop

    while True:
        try:
            if not is_market_hours():
                logger.info("Market is closed. Waiting...")
                sleep(60)
                continue

            evaluate_and_trade()
            logger.info(f"Sleeping for {CHECK_INTERVAL} seconds.")
            sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Bot stopped manually.")
            manual_stop = True
            close_all_positions()
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
