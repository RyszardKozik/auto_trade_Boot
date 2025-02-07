import os  # For environment variable access
import logging  # For logging system events and activities
import json  # For saving and loading bot state in JSON format
from time import sleep  # To pause execution between trading cycles
from datetime import datetime, timedelta  # To handle date and time calculations
from dotenv import load_dotenv  # To load environment variables from a .env file
from alpaca_trade_api.rest import REST, TimeFrame  # Alpaca API for trading and fetching market data

# Load Environment Variables
load_dotenv(".env")  # Load the .env file to access API keys and configurations

# Configure Logger
logger = logging.getLogger("TradingBot")  # Create a logger named 'TradingBot'
logger.setLevel(logging.INFO)  # Set logging level to INFO

# # File Handler for Startup and Closing Logs
# file_handler = logging.FileHandler("paper_bot.log")  # Log to 'paper_bot.log' file
# file_formatter = logging.Formatter("%(asctime)s - %(message)s")  # Include timestamp in log messages
# file_handler.setFormatter(file_formatter)  # Apply formatter to file handler
# logger.addHandler(file_handler)  # Attach file handler to logger

# Console Handler for Terminal Logs (No "INFO")
console_handler = logging.StreamHandler()  # Create a console handler
console_formatter = logging.Formatter("%(message)s")  # Simplified format for terminal logs
console_handler.setFormatter(console_formatter)  # Apply formatter to console handler
logger.addHandler(console_handler)  # Attach console handler to logger

# Set API Credentials
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()  # Default to 'paper' mode if not specified

if TRADING_MODE == "live":  # Check if running in live trading mode
    API_KEY = os.getenv("PAPER_LIVE_API_KEY")  # Load live API key
    API_SECRET = os.getenv("PAPER_LIVE_SECRET_KEY")  # Load live API secret
    BASE_URL = os.getenv("PAPER_LIVE_BASE_URL", "https://api.alpaca.markets")  # Live API base URL
    logger.info("Running in LIVE mode.")  # Log mode
else:  # Default to paper trading mode
    API_KEY = os.getenv("PAPER_API_KEY")  # Load paper API key
    API_SECRET = os.getenv("PAPER_SECRET_KEY")  # Load paper API secret
    BASE_URL = os.getenv("PAPER_BASE_URL", "https://paper-api.alpaca.markets")  # Paper API base URL
    logger.info("Running in PAPER mode.")  # Log mode

# Add debug logging to confirm environment variables are loaded correctly
if API_KEY and API_SECRET:
    logger.debug(f"Using API Key: {API_KEY[:4]}*** (hidden for security)")
else:
    logger.error("API key or secret is missing. Check your .env file.")
    exit(1)

# Initialize API
api = REST(API_KEY, API_SECRET, BASE_URL)  # Create an Alpaca REST API client

# Bot Configuration
ASSETS = ["DOGE/USD", "BCH/USD", "USDT/USD"]  # List of assets to trade
TARGET_ALLOCATION = 20  # Target allocation per asset in USD
CHECK_INTERVAL = 300  # Time between checks in seconds (5 minutes)
STATE_FILE = "paper_state.json"  # State file for saving bot's state

def load_state():
    """Load bot state from file."""
    try:
        with open(STATE_FILE, "r") as f:  # Open state file in read mode
            state = json.load(f)  # Load JSON data
            logger.info("State loaded successfully.")  # Log success
            return state  # Return state
    except FileNotFoundError:  # Handle missing state file
        logger.warning("State file not found. Initializing a new state.")
        return {"positions": {}}  # Initialize empty state
    except json.JSONDecodeError:  # Handle corrupted state file
        logger.error("State file is corrupted. Initializing a new state.")
        return {"positions": {}}  # Initialize empty state


def save_state(state):
    """Save bot state to file."""
    try:
        with open(STATE_FILE, "w") as f:  # Open state file in write mode
            json.dump(state, f, indent=4)  # Save JSON data with indentation
            logger.info("State saved successfully.")  # Log success
    except Exception as e:  # Handle errors during saving
        logger.error(f"Failed to save state: {e}")  # Log error


def close_open_positions(state):
    """Close all open positions on bot restart."""
    logger.info("Checking for open positions to close.")  # Log activity
    for asset, position in state.get("positions", {}).items():  # Iterate through open positions
        qty = position["qty"]  # Get quantity of asset
        logger.info(f"Closing position for {asset}. Qty: {qty}")  # Log activity
        try:
            api.submit_order(  # Submit order to close position
                symbol=asset,
                qty=qty,
                side="sell",
                type="market",
                time_in_force="gtc"
            )
            logger.info(f"Successfully closed position for {asset}.")  # Log success
        except Exception as e:  # Handle errors during closing
            logger.error(f"Failed to close position for {asset}: {e}")  # Log error
    state["positions"] = {}  # Reset positions in state
    save_state(state)  # Save updated state
    logger.info("All positions closed.")  # Log completion


def fetch_prices(asset):
    """Fetch historical prices for an asset."""
    try:
        now = datetime.utcnow()  # Current UTC time
        start = now - timedelta(days=7)  # Start time 7 days ago

        start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")  # Format start time
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")  # Format current time

        bars = api.get_crypto_bars(asset, TimeFrame.Minute, start=start_str, end=now_str).df  # Fetch data
        return bars['close'].tolist()  # Return closing prices as a list
    except Exception as e:  # Handle errors during fetching
        logger.error(f"Error fetching prices for {asset}: {e}")  # Log error
        return []  # Return empty list on failure


def calculate_sma(prices, window):
    """Calculate Simple Moving Average."""
    if len(prices) < window:  # Check if enough data is available
        return None  # Return None if not enough data
    return sum(prices[-window:]) / window  # Calculate SMA


def evaluate_and_trade():
    """Evaluate assets and perform trading."""
    state = load_state()  # Load bot state
    cash = float(api.get_account().cash)  # Fetch available cash

    for asset in ASSETS:  # Iterate through assets
        logger.info(f"Evaluating asset: {asset}")  # Log activity
        prices = fetch_prices(asset)  # Fetch prices for asset

        if not prices:  # Skip if no prices are available
            logger.warning(f"No price data for {asset}. Skipping.")
            continue

        short_sma = calculate_sma(prices, 10)  # Calculate short SMA
        long_sma = calculate_sma(prices, 50)  # Calculate long SMA

        if not short_sma or not long_sma:  # Skip if SMA calculations are not possible
            logger.warning(f"Not enough data for SMA calculation for {asset}. Skipping.")
            continue

        logger.info(f"Short SMA: {short_sma}, Long SMA: {long_sma}")  # Log SMA values

        # Ensure available cash is sufficient
        if cash < TARGET_ALLOCATION:
            logger.warning(f"Insufficient cash to trade {asset}. Available: ${cash}, Required: ${TARGET_ALLOCATION}. Skipping.")
            continue

        if short_sma > long_sma and asset not in state.get("positions", {}):  # Buy condition
            logger.info(f"Buying {asset}.")  # Log activity
            qty = round(cash / prices[-1], 4) if cash < TARGET_ALLOCATION else round(TARGET_ALLOCATION / prices[-1], 4)

            try:
                api.submit_order(  # Submit buy order
                    symbol=asset,
                    qty=qty,
                    side="buy",
                    type="market",
                    time_in_force="gtc"
                )
                state["positions"][asset] = {"qty": qty, "entry_price": prices[-1]}  # Update state
                save_state(state)  # Save state
                logger.info(f"Successfully bought {asset}. Qty: {qty}, Remaining Cash: ${cash - qty * prices[-1]}")  # Log success
                cash -= qty * prices[-1]  # Deduct allocated cash
            except Exception as e:  # Handle errors during buying
                logger.error(f"Failed to buy {asset}: {e}")  # Log error

        elif short_sma < long_sma and asset in state.get("positions", {}):  # Sell condition
            logger.info(f"Selling {asset}.")  # Log activity
            position = state["positions"].pop(asset)  # Remove position from state
            qty = position["qty"]  # Get quantity

            try:
                api.submit_order(  # Submit sell order
                    symbol=asset,
                    qty=qty,
                    side="sell",
                    type="market",
                    time_in_force="gtc"
                )
                save_state(state)  # Save state
                logger.info(f"Successfully sold {asset}. Qty: {qty}")  # Log success
            except Exception as e:  # Handle errors during selling
                logger.error(f"Failed to sell {asset}: {e}")  # Log error

        else:  # No trade condition
            logger.info(f"No trade signal for {asset}.")  # Log activity

    save_state(state)  # Save state after evaluation


def main():
    logger.info("Trading bot started.")  # Log startup
    state = load_state()  # Load bot state

    # Close positions if any
    if state.get("positions"):  # Check for open positions
        close_open_positions(state)  # Close open positions

    while True:  # Continuous trading loop
        try:
            evaluate_and_trade()  # Evaluate and trade assets
            logger.info(f"Sleeping for {CHECK_INTERVAL} seconds.")  # Log sleep time
            sleep(CHECK_INTERVAL)  # Sleep before next evaluation
        except KeyboardInterrupt:  # Handle manual stop
            logger.info("Bot stopped manually.")  # Log manual stop
            close_open_positions(state)  # Close open positions
            break
        except Exception as e:  # Handle unexpected errors
            logger.error(f"Unexpected error: {e}")  # Log error
            sleep(CHECK_INTERVAL)  # Sleep before retry


if __name__ == "__main__":  # Run the main function if the script is executed
    main()
