import os
import logging
import requests
from dotenv import load_dotenv
from time import sleep
from datetime import datetime
from pytz import timezone
from flask import Flask, request

# Flask App for OAuth Callback
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    filename="questrade_bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables
load_dotenv('.env')

# Configuration
TRADE_LIMIT = float('inf')  # Unlimited trades
TRADE_THRESHOLD = int(os.getenv("TRADE_THRESHOLD", 5))  # Default: 5%
TRADE_PERCENTAGE = float(os.getenv("TRADE_PERCENTAGE", 0.1))  # Default: 10%

CLIENT_ID = os.getenv("QUESTRADE_CLIENT_ID")
REDIRECT_URI = os.getenv("QUESTRADE_REDIRECT_URI")
REFRESH_TOKEN = os.getenv("QUESTRADE_REFRESH_TOKEN")
TARGET_ALLOCATIONS = eval(os.getenv("TARGET_ALLOCATIONS", "{}"))  # Parse JSON-like syntax

# Global variables
ACCESS_TOKEN = None
API_SERVER = None


@app.route("/callback")
def callback():
    """Handle OAuth callback to exchange code for tokens."""
    global REFRESH_TOKEN
    code = request.args.get("code")
    if code:
        try:
            exchange_code_for_token(code)
            return "Authorization successful! You can close this window."
        except Exception as e:
            log_error(f"Callback error: {e}")
            return f"Authorization failed: {e}"
    return "Authorization code not provided."


def start_oauth_flow():
    """Initiate the OAuth flow."""
    auth_url = (
        f"https://login.questrade.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
    )
    print(f"Authorize the application by visiting this URL:\n{auth_url}")


def exchange_code_for_token(code):
    """Exchange authorization code for access and refresh tokens."""
    global ACCESS_TOKEN, REFRESH_TOKEN, API_SERVER
    try:
        url = "https://login.questrade.com/oauth2/token"
        payload = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        ACCESS_TOKEN = data["access_token"]
        REFRESH_TOKEN = data["refresh_token"]
        API_SERVER = data["api_server"]
        logging.info("Token obtained successfully.")
    except Exception as e:
        log_error(f"Failed to exchange code for token: {e}")
        raise


def refresh_token():
    """Refresh Questrade API tokens."""
    global ACCESS_TOKEN, API_SERVER
    try:
        url = f"https://login.questrade.com/oauth2/token?grant_type=refresh_token&refresh_token={REFRESH_TOKEN}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        ACCESS_TOKEN = data["access_token"]
        API_SERVER = data["api_server"]
        logging.info("Token refreshed successfully.")
    except Exception as e:
        log_error(f"Failed to refresh token: {e}")
        raise


def log_error(message):
    """Log errors."""
    logging.error(message)


def is_market_open():
    """Check if the current time is within US market hours (9:30 AM - 4:00 PM ET)."""
    eastern = timezone("US/Eastern")
    now = datetime.now(eastern)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def make_questrade_request(endpoint, method="GET", payload=None):
    """Make authenticated requests to Questrade API."""
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    url = f"{API_SERVER}{endpoint}"
    try:
        response = requests.request(method, url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error(f"API request error at {endpoint}: {e}")
        raise


def rebalance_portfolio():
    """Rebalance portfolio based on target allocations."""
    if not is_market_open():
        print("Market is closed. Skipping rebalance.")
        return

    try:
        account_info = make_questrade_request("/v1/accounts")
        balance = account_info["accounts"][0]["totalEquity"]
        for symbol, target in TARGET_ALLOCATIONS.items():
            current_allocation = 0  # Placeholder for actual allocation
            if abs(current_allocation - target) > TRADE_THRESHOLD:
                side = "buy" if current_allocation < target else "sell"
                amount = balance * TRADE_PERCENTAGE
                print(f"Placing trade for {symbol}: {side.upper()} ${amount:.2f}")
    except Exception as e:
        log_error(f"Error during portfolio rebalance: {e}")


def run_bot():
    """Main bot loop."""
    refresh_token()  # Initial token refresh
    while True:
        rebalance_portfolio()
        sleep(3600)  # Rebalance every hour


if __name__ == "__main__":
    start_oauth_flow()
    app.run(port=5000)
