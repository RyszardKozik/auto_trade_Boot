import os
import logging
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from time import sleep
from pytz import timezone

# Configure logging
logging.basicConfig(
    filename="trading_bot.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables
load_dotenv()

# Questrade API credentials
ACCESS_TOKEN = os.getenv("QUESTRADE_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("QUESTRADE_REFRESH_TOKEN")
API_BASE_URL = os.getenv("QUESTRADE_API_BASE_URL", "https://api01.iq.questrade.com/v1/")
TIMEZONE = timezone("US/Eastern")  # Ensure Eastern Time for trading hours

# Validate credentials
if not REFRESH_TOKEN:
    raise ValueError("Missing Questrade API credentials. Check your .env file.")

# Portfolio configuration
TARGET_ALLOCATIONS = {
    "AAPL": 10,
    "AMZN": 10,
    "TSLA": 10,
    "GOOGL": 10,
    "MSFT": 10
}
TRADE_AMOUNT = 10  # Set $10 allocation for each trade

# Trading hours and days
MARKET_OPEN = 9
MARKET_CLOSE = 16

# API Helper Functions
def refresh_access_token():
    """Refreshes the Questrade access token using the refresh token."""
    global ACCESS_TOKEN, API_BASE_URL
    try:
        response = requests.post(
            f"https://login.questrade.com/oauth2/token",
            params={"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
        )
        response_data = response.json()
        if "access_token" in response_data:
            ACCESS_TOKEN = response_data["access_token"]
            API_BASE_URL = response_data["api_server"]
            logging.info("Access token refreshed successfully.")
        else:
            raise ValueError("Failed to refresh access token.")
    except Exception as e:
        logging.error(f"Error refreshing access token: {e}")
        raise

def send_request(endpoint, method="GET", params=None, data=None):
    """Helper function to send API requests."""
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError("Unsupported HTTP method.")
        if response.status_code == 401:  # Handle expired token
            logging.info("Access token expired. Refreshing...")
            refresh_access_token()
            return send_request(endpoint, method, params, data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error in API request to {endpoint}: {e}")
        raise

# Trading Functions
def is_trading_time():
    """Check if the current time is within trading hours on a weekday."""
    now = datetime.now(TIMEZONE)
    if now.weekday() < 5:  # Monday to Friday
        return MARKET_OPEN <= now.hour < MARKET_CLOSE
    return False

def get_account_info():
    """Fetches account information."""
    try:
        account_data = send_request("v1/accounts")
        for account in account_data.get("accounts", []):
            logging.info(f"Account ID: {account['number']}, Status: {account['status']}")
        return account_data
    except Exception as e:
        logging.error(f"Failed to fetch account information: {e}")
        return None

def get_positions(account_id):
    """Fetches current positions."""
    try:
        endpoint = f"v1/accounts/{account_id}/positions"
        positions = send_request(endpoint)
        logging.info("Current Positions:")
        for position in positions.get("positions", []):
            logging.info(f"{position['symbol']} - Quantity: {position['quantity']}, Market Value: ${position['currentMarketValue']}")
        return positions.get("positions", [])
    except Exception as e:
        logging.error(f"Failed to fetch positions: {e}")
        return []

def get_symbol_price(symbol):
    """Fetches the latest price for a given symbol."""
    try:
        response = send_request(f"v1/markets/quotes/{symbol}")
        price = response.get("quotes", [{}])[0].get("lastTradePrice", 0)
        logging.info(f"Latest price for {symbol}: ${price:.2f}")
        return price
    except Exception as e:
        logging.error(f"Failed to fetch price for {symbol}: {e}")
        return 0

def place_order(account_id, symbol, side, amount):
    """Places a market order."""
    try:
        price = get_symbol_price(symbol)
        if price <= 0:
            raise ValueError("Invalid price fetched for the symbol.")

        quantity = round(amount / price, 4)  # Calculate quantity based on $10 allocation
        order_data = {
            "accountId": account_id,
            "symbol": symbol,
            "quantity": quantity,
            "action": side.upper(),
            "orderType": "Market",
            "timeInForce": "GTC"
        }
        send_request(f"v1/accounts/{account_id}/orders", method="POST", data=order_data)
        logging.info(f"Order placed: {side} {quantity} units of {symbol}.")
    except Exception as e:
        logging.error(f"Failed to place order for {symbol}: {e}")

def rebalance_portfolio(account_id):
    """Rebalances the portfolio based on target allocations."""
    logging.info("Starting portfolio rebalancing...")
    try:
        for symbol, target in TARGET_ALLOCATIONS.items():
            logging.info(f"Rebalancing for {symbol}: Allocating ${TRADE_AMOUNT}")
            place_order(account_id, symbol, "BUY", TRADE_AMOUNT)
    except Exception as e:
        logging.error(f"Error rebalancing portfolio: {e}")

# Main Trading Bot Loop
def run_bot():
    """Runs the trading bot."""
    logging.info("Starting trading bot...")
    account_data = get_account_info()
    if not account_data:
        logging.error("No account data available. Exiting bot.")
        return

    # Use the first account for trading
    account_id = account_data["accounts"][0]["number"]

    while True:
        try:
            if is_trading_time():
                logging.info("Market is open. Running trades.")
                rebalance_portfolio(account_id)
            else:
                logging.info("Market is closed. Waiting for the next trading session.")
            sleep(3600)  # Wait for 1 hour
        except KeyboardInterrupt:
            logging.info("Trading bot stopped manually.")
            break
        except Exception as e:
            logging.error(f"Unexpected error in the bot loop: {e}")

if __name__ == "__main__":
    run_bot()
