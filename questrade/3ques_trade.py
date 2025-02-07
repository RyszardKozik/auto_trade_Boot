import os
import json
import logging
from dotenv import load_dotenv
from time import sleep
from datetime import datetime, timedelta
from pytz import timezone
from alpaca_trade_api.rest import REST

# Configure logging to show in both terminal and log file
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create file handler for logging to file
file_handler = logging.FileHandler("trading_bot.log")
file_handler.setLevel(logging.INFO)

# Create console handler for logging to terminal
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a log format
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Load environment variables
load_dotenv()

# Parse TARGET_ALLOCATIONS from .env
try:
    raw_allocations = os.getenv("TARGET_ALLOCATIONS", "{}")
    TARGET_ALLOCATIONS = json.loads(raw_allocations)
    if not isinstance(TARGET_ALLOCATIONS, dict):
        raise ValueError("TARGET_ALLOCATIONS must be a valid JSON object")
except Exception as e:
    logger.error(f"Failed to parse TARGET_ALLOCATIONS: {e}")
    TARGET_ALLOCATIONS = {}

# Determine trading mode (paper or live)
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()
if TRADING_MODE == "live":
    API_KEY = os.getenv("LIVE_API_KEY")
    API_SECRET = os.getenv("LIVE_SECRET_KEY")
    BASE_URL = os.getenv("LIVE_BASE_URL", "https://api.alpaca.markets")
else:
    API_KEY = os.getenv("PAPER_API_KEY")
    API_SECRET = os.getenv("PAPER_SECRET_KEY")
    BASE_URL = os.getenv("PAPER_BASE_URL", "https://paper-api.alpaca.markets")

# Validate API credentials
if not API_KEY or not API_SECRET:
    raise ValueError("Missing Alpaca API credentials. Check your .env file.")

# Initialize Alpaca REST API client
api = REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Configuration
TRADE_AMOUNT = 10  # Fixed $10 allocation for each trade
TRADE_INTERVAL_CRYPTO = 3600  # Rebalance every 1 hour for crypto
TRADE_INTERVAL_STOCKS = 1800  # Rebalance every 30 minutes for stocks
eastern = timezone("US/Eastern")

def is_weekday():
    """Check if today is a weekday (Monday-Friday)."""
    now = datetime.now(eastern)
    return now.weekday() < 5

def is_market_open():
    """Checks if the stock market is open and ensures it's not within 30 minutes of open/close."""
    now = datetime.now(eastern)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    early_cutoff = market_close - timedelta(minutes=30)
    late_start = market_open + timedelta(minutes=30)
    return late_start <= now <= early_cutoff and is_weekday()

def is_crypto_trading_time():
    """Crypto trading is always open (24/7)."""
    return True

def get_account_info():
    """Fetch account information (Equity, Buying Power)."""
    try:
        account = api.get_account()
        equity = account.equity
        buying_power = account.buying_power
        # Display in the terminal
        print(f"Buying power: ${buying_power}")
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")

def get_open_positions():
    """Fetch all open positions."""
    try:
        positions = api.list_positions()
        if positions:
            print("Current Open Positions:")
            for position in positions:
                print(f"{position.symbol}: {position.qty} shares, Value: ${float(position.market_value):.2f}")
        else:
            print("No open positions.")
    except Exception as e:
        logger.error(f"Failed to get open positions: {e}")

def get_asset_price(symbol):
    """Gets the current price of an asset from Alpaca."""
    try:
        # For stocks, we can use `get_last_trade`. For crypto, we need to use `get_quote`.
        if symbol.endswith("/USD"):
            # For crypto, we use `get_quote`
            quote = api.get_quote(symbol)
            return quote.askprice
        else:
            # For stocks, we can use `get_last_trade`
            trade = api.get_last_trade(symbol)
            return trade.price
    except Exception as e:
        logger.error(f"Failed to get price for {symbol}: {e}")
        return 0  # If there's an issue getting the price, return 0

def place_order(symbol, side, amount):
    """Places a trade order for a given symbol."""
    try:
        # Get the current price of the asset
        price = get_asset_price(symbol)
        if price == 0:
            raise ValueError("Invalid asset price.")

        # Calculate the quantity to trade
        qty = round(amount / price, 4)  # Calculate based on asset's current price
        logger.info(f"Placing {side.upper()} order for ${amount:.2f} of {symbol} ({qty} units).")
        
        # Adjust time_in_force for crypto and stocks
        time_in_force = 'gtc'  # Use Good-Til-Canceled for both crypto and stock
        
        api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type='market',
            time_in_force=time_in_force
        )
        logger.info(f"Trade executed: {side.upper()} ${amount:.2f} of {symbol}.")
    except Exception as e:
        logger.error(f"Failed to place order for {symbol}: {e}")

def rebalance_crypto_portfolio():
    """Rebalances the crypto portfolio based on target allocations."""
    logger.info("Starting crypto rebalancing...")
    try:
        for symbol, target in TARGET_ALLOCATIONS.items():
            if not symbol.endswith("/USD"):  # Skip non-crypto assets
                continue
            logger.info(f"Rebalancing for {symbol}: Allocating ${TRADE_AMOUNT}")
            place_order(symbol, "buy", TRADE_AMOUNT)
    except Exception as e:
        logger.error(f"Error rebalancing crypto portfolio: {e}")

def rebalance_stock_portfolio():
    """Rebalances the stock portfolio based on target allocations."""
    logger.info("Starting stock rebalancing...")
    if not is_weekday():
        logger.info("Stock market is closed today. Skipping stock rebalancing.")
        return

    try:
        for symbol, target in TARGET_ALLOCATIONS.items():
            if symbol.endswith("/USD"):  # Skip crypto assets
                continue
            logger.info(f"Rebalancing for {symbol}: Allocating ${TRADE_AMOUNT}")
            place_order(symbol, "buy", TRADE_AMOUNT)
    except Exception as e:
        logger.error(f"Error rebalancing stock portfolio: {e}")

def close_all_positions():
    """Closes all open positions."""
    try:
        positions = api.list_positions()
        for position in positions:
            api.submit_order(
                symbol=position.symbol,
                qty=position.qty,
                side='sell',
                type='market',
                time_in_force='day'
            )
            logger.info(f"Closed position for {position.symbol}, Quantity: {position.qty}")
        logger.info("All positions closed.")
    except Exception as e:
        logger.error(f"Failed to close positions: {e}")

def run_bot():
    """Main trading bot loop."""
    while True:
        # Print account info and open positions before making trades
        get_account_info()
        get_open_positions()

        if is_market_open():
            logger.info("Stock market is open. Rebalancing stock portfolio...")
            rebalance_stock_portfolio()
            sleep(TRADE_INTERVAL_STOCKS)
        elif is_crypto_trading_time():
            logger.info("Crypto trading is active. Rebalancing crypto portfolio...")
            rebalance_crypto_portfolio()
            sleep(TRADE_INTERVAL_CRYPTO)
        else:
            logger.info("Markets are closed. Waiting for the next cycle...")
            sleep(TRADE_INTERVAL_STOCKS)

if __name__ == "__main__":
    run_bot()
