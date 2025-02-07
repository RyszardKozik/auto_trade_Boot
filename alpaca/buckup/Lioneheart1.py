import os  # For accessing environment variables
import logging  # For logging system events and activities
import json  # For saving and loading bot state in JSON format
from time import sleep  # For pausing execution between trading cycles
from dotenv import load_dotenv  # For loading environment variables from a .env file
from alpaca_trade_api.rest import REST  # For interacting with Alpaca API

# Logger Setup
logger = logging.getLogger("Lioneheart2")  # Create a logger named 'Lioneheart2'
logger.setLevel(logging.INFO)  # Set logging level to INFO
console_handler = logging.StreamHandler()  # Console handler for logging
console_handler.setFormatter(logging.Formatter("%(message)s"))  # Simple log format
logger.addHandler(console_handler)  # Attach console handler to the logger

# Load Environment Variables
load_dotenv(".env")  # Load environment variables from the .env file

# Set up API credentials
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()
if TRADING_MODE == "live":
    API_KEY = os.getenv("LIONHEART1_LIVE_API_KEY")
    API_SECRET = os.getenv("LIONHEART1_LIVE_SECRET_KEY")
    BASE_URL = os.getenv("LIONHEART1_LIVE_BASE_URL", "https://api.alpaca.markets")
    logger.info("Running in LIVE mode.")
else:
    API_KEY = os.getenv("LIONHEART1_API_KEY")
    API_SECRET = os.getenv("LIONHEART1_SECRET_KEY")
    BASE_URL = os.getenv("LIONHEART1_BASE_URL", "https://paper-api.alpaca.markets")
    logger.info("Running in PAPER mode.")

# Initialize Alpaca API Client
try:
    api = REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")
    logger.info("Connected to Alpaca API successfully.")
except Exception as e:
    logger.error(f"Error initializing Alpaca API client: {e}")
    exit()

# Constants
ASSETS = ["USDU", "USDTUSD", "LTCUSD"]  # List of tradable assets
TARGET_ALLOCATION_PER_ASSET = 20  # Allocate $20 per asset
CHECK_INTERVAL = 300  # Pause for 5 minutes between trading cycles
STATE_FILE = "Lioneheart2_state.json"  # File to save the bot's state

# Save and Load State
def save_state(state):
    """Save the bot's state to a file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def load_state():
    """Load the bot's state from a file."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"invested_assets": {}}

# Verify Tradable Assets
def verify_tradable_assets():
    """Check if the assets in the ASSETS list are tradable."""
    try:
        tradable_assets = {asset.symbol: asset for asset in api.list_assets(status="active") if asset.tradable}
        logger.info("Verifying tradable assets...")
        ASSETS.extend(["LTCUSD", "BB"]) # Dynamically add new assets here
        filtered_assets = [asset for asset in ASSETS if asset.replace("/", "") in tradable_assets]
        logger.info(f"Filtered tradable assets: {filtered_assets}")
        return filtered_assets
    except Exception as e:
        logger.error(f"Error verifying tradable assets: {e}")
        return []

# Log Current Portfolio
def log_portfolio():
    """Log the current portfolio holdings."""
    try:
        positions = api.list_positions()
        if not positions:
            logger.info("Portfolio is empty.")
        else:
            logger.info("Current Portfolio:")
            for position in positions:
                logger.info(f"{position.symbol}: {position.qty} units at ${position.avg_entry_price}")
    except Exception as e:
        logger.error(f"Error fetching portfolio: {e}")

# Allocate Funds
def allocate_funds(tradable_assets):
    """Allocate funds across assets."""
    try:
        account = api.get_account()
        cash = float(account.cash)
        state = load_state()
        invested_assets = state["invested_assets"]

        for asset in tradable_assets:
            if asset in invested_assets:
                logger.info(f"Already invested in {asset}. Skipping allocation.")
                continue

            try:
                latest_trade = api.get_latest_trade(asset.replace("/", ""))
                latest_price = latest_trade.price
                qty = round(TARGET_ALLOCATION_PER_ASSET / latest_price, 4)

                if cash >= TARGET_ALLOCATION_PER_ASSET:
                    api.submit_order(
                        symbol=asset.replace("/", ""),
                        qty=qty,
                        side="buy",
                        type="market",
                        time_in_force="day"
                    )
                    logger.info(f"Allocated ${TARGET_ALLOCATION_PER_ASSET} to {asset} (Qty: {qty}).")
                    cash -= TARGET_ALLOCATION_PER_ASSET
                    invested_assets[asset] = {"qty": qty, "price": latest_price}
                    save_state(state)
                else:
                    logger.warning(f"Insufficient cash to allocate ${TARGET_ALLOCATION_PER_ASSET} to {asset}.")
            except Exception as e:
                logger.error(f"Error allocating funds for {asset}: {e}")
    except Exception as e:
        logger.error(f"Error in fund allocation process: {e}")

# Main Bot Loop
def run_bot():
    """Main trading bot loop."""
    logger.info("Starting Lionheart2 trading bot.")
    tradable_assets = verify_tradable_assets()  # Verify tradable assets at startup

    while True:
        try:
            log_portfolio()
            allocate_funds(tradable_assets)
            logger.info(f"Sleeping for {CHECK_INTERVAL} seconds.")
            sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Bot stopped manually.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sleep(CHECK_INTERVAL)

# Entry Point
if __name__ == "__main__":
    run_bot()
