import os
import logging
import requests
from dotenv import load_dotenv
from datetime import datetime
from time import sleep
from pytz import timezone

# Configure logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()  # Output logs to console
    ]
)

# Load environment variables
load_dotenv()

# Questrade API credentials
ACCESS_TOKEN = os.getenv("QUESTRADE_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("QUESTRADE_REFRESH_TOKEN")
API_BASE_URL = os.getenv("QUESTRADE_API_BASE_URL", "https://api01.iq.questrade.com")  # Removed trailing '/v1'
TIMEZONE = timezone("US/Eastern")

# Validate environment variables
if not ACCESS_TOKEN or not REFRESH_TOKEN:
    logging.error("Missing Questrade API credentials. Please check your .env file.")
    raise ValueError("Missing required environment variables: ACCESS_TOKEN or REFRESH_TOKEN.")

# Portfolio configuration
TRADE_LIMITS = {
    "AAPL": {"low": 150, "high": 200},
    "AMZN": {"low": 3000, "high": 3500},
    "TSLA": {"low": 600, "high": 800},
    "GOOGL": {"low": 2500, "high": 3000},
    "MSFT": {"low": 200, "high": 300},
}
TRADE_AMOUNT = 10
PROFIT_TARGET = 1000  # Example profit target in USD

# Trading hours and days
MARKET_OPEN = 9
MARKET_CLOSE = 16

# Track open positions
open_positions = {}

# Helper Functions
def refresh_access_token():
    """Refresh Questrade access token."""
    global ACCESS_TOKEN, API_BASE_URL
    try:
        response = requests.post(
            "https://login.questrade.com/oauth2/token",
            params={"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
        )
        response_data = response.json()
        ACCESS_TOKEN = response_data["access_token"]
        API_BASE_URL = response_data["api_server"]
        logging.info("Access token refreshed successfully.")
    except Exception as e:
        logging.error(f"Error refreshing access token: {e}")
        raise

def send_request(endpoint, method="GET", params=None, data=None):
    """Send API requests."""
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    url = f"{API_BASE_URL}{endpoint}"  # Properly append endpoint to base URL
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
        logging.error(f"Error in API request to {url}: {e}")
        raise

def is_trading_time():
    """Check if the current time is within trading hours on a weekday."""
    now = datetime.now(TIMEZONE)
    return now.weekday() < 5 and MARKET_OPEN <= now.hour < MARKET_CLOSE

def get_positions(account_id):
    """Fetch current positions."""
    endpoint = f"/v1/accounts/{account_id}/positions"  # Use proper endpoint
    positions = send_request(endpoint)
    return {pos["symbol"]: pos for pos in positions.get("positions", [])}

def get_symbol_price(symbol):
    """Fetch the latest price for a symbol."""
    endpoint = f"/v1/markets/quotes/{symbol}"
    response = send_request(endpoint)
    return response.get("quotes", [{}])[0].get("lastTradePrice", 0)

def place_order(account_id, symbol, side, amount):
    """Place a market order."""
    price = get_symbol_price(symbol)
    if price <= 0:
        logging.error(f"Invalid price for {symbol}. Skipping order.")
        return

    quantity = round(amount / price, 4)
    order_data = {
        "accountId": account_id,
        "symbol": symbol,
        "quantity": quantity,
        "action": side.upper(),
        "orderType": "Market",
        "timeInForce": "GTC"
    }
    endpoint = f"/v1/accounts/{account_id}/orders"
    send_request(endpoint, method="POST", data=order_data)
    logging.info(f"Order placed: {side} {quantity} units of {symbol} at ${price:.2f}.")

def close_position(account_id, symbol, quantity):
    """Close an open position."""
    order_data = {
        "accountId": account_id,
        "symbol": symbol,
        "quantity": quantity,
        "action": "SELL",
        "orderType": "Market",
        "timeInForce": "GTC"
    }
    endpoint = f"/v1/accounts/{account_id}/orders"
    send_request(endpoint, method="POST", data=order_data)
    logging.info(f"Position closed for {symbol}: {quantity} units sold.")

def manage_positions(account_id):
    """Check and manage open positions for profit or stop-loss."""
    positions = get_positions(account_id)
    for symbol, position in positions.items():
        current_price = get_symbol_price(symbol)
        if symbol in TRADE_LIMITS:
            limits = TRADE_LIMITS[symbol]
            if current_price <= limits["low"]:
                logging.info(f"{symbol} hit stop-loss. Closing position.")
                close_position(account_id, symbol, position["quantity"])
            elif current_price >= limits["high"]:
                logging.info(f"{symbol} reached take-profit. Closing position.")
                close_position(account_id, symbol, position["quantity"])

def rebalance_portfolio(account_id):
    """Rebalance the portfolio based on target allocations."""
    positions = get_positions(account_id)
    for symbol in TRADE_LIMITS.keys():
        if symbol in positions:
            logging.info(f"{symbol} already has an open position. Skipping trade.")
            continue
        current_price = get_symbol_price(symbol)
        if TRADE_LIMITS[symbol]["low"] <= current_price <= TRADE_LIMITS[symbol]["high"]:
            logging.info(f"Placing order for {symbol}.")
            place_order(account_id, symbol, "BUY", TRADE_AMOUNT)
        else:
            logging.info(f"{symbol} price is out of trade limits. Skipping.")

# Main Trading Loop
def run_bot():
    logging.info("Starting trading bot...")
    account_data = send_request("/v1/accounts")  # Proper endpoint
    account_id = account_data["accounts"][0]["number"]

    total_profit = 0

    while True:
        try:
            if is_trading_time():
                total_profit += calculate_portfolio_profit(account_id)
                if total_profit >= PROFIT_TARGET:
                    logging.info(f"Profit target reached: ${total_profit:.2f}. Stopping trading.")
                    break
                manage_positions(account_id)
                rebalance_portfolio(account_id)
            else:
                logging.info("Market is closed. Waiting for next session.")
            sleep(3600)  # Wait 1 hour
        except KeyboardInterrupt:
            logging.info("Bot stopped manually.")
            break
        except Exception as e:
            logging.error(f"Unexpected error in bot loop: {e}")

if __name__ == "__main__":
    run_bot()
