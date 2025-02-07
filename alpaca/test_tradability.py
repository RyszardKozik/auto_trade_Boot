from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(".env")

# Initialize client
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()
API_KEY = os.getenv(f"{TRADING_MODE.upper()}_API_KEY")
API_SECRET = os.getenv(f"{TRADING_MODE.upper()}_SECRET_KEY")

try:
    trading_client = TradingClient(api_key=API_KEY, secret_key=API_SECRET, paper=(TRADING_MODE == "paper"))
    print("Successfully connected to Alpaca API.")
except Exception as e:
    print(f"Error connecting to Alpaca API: {e}")
