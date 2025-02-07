from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(".env")

# Get trading mode and API credentials
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()
API_KEY = os.getenv(f"{TRADING_MODE.upper()}_API_KEY")
API_SECRET = os.getenv(f"{TRADING_MODE.upper()}_SECRET_KEY")

print(f"Using API Key: {API_KEY[:4]}***, Trading Mode: {TRADING_MODE}")

try:
    # Initialize the client
    client = TradingClient(api_key=API_KEY, secret_key=API_SECRET, paper=(TRADING_MODE == "paper"))
    account = client.get_account()
    print(f"Connected successfully: Account ID: {account.id}, Cash Balance: {account.cash}")
except Exception as e:
    print(f"Error: {e}")
