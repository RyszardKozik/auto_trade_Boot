import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve variables from .env
API_BASE_URL = os.getenv("LIVE_BASE_URL")
API_KEY = os.getenv("LIVE_API_KEY")
SECRET_KEY = os.getenv("LIVE_SECRET_KEY")
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "USDTUSD")  # Default asset to USDTUSD

def fetch_position(symbol):
    """
    Fetch the current position for the given symbol.
    """
    try:
        endpoint = f"{API_BASE_URL}/v2/positions/{symbol}"
        headers = {
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": SECRET_KEY,
        }
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            position_data = response.json()
            print(f"Position Details: {position_data}")
            return position_data
        elif response.status_code == 404:
            print(f"No open position for {symbol}.")
            return None
        else:
            print(f"Error fetching position: {response.status_code}")
            print("Response:", response.text)
            return None
    except Exception as e:
        print(f"Error during position fetch: {e}")
        return None

def liquidate_position(symbol, qty):
    """
    Submit a market sell order to liquidate the position.
    """
    try:
        endpoint = f"{API_BASE_URL}/v2/orders"
        headers = {
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": SECRET_KEY,
        }
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": "sell",
            "type": "market",
            "time_in_force": "gtc"
        }
        response = requests.post(endpoint, json=payload, headers=headers)
        if response.status_code == 200 or response.status_code == 201:
            print("Position successfully liquidated.")
            print("Response:", response.json())
        elif response.status_code == 403:
            print("403 Forbidden: Ensure permissions and platform rules are correct.")
        else:
            print(f"Failed to liquidate position. Status Code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"Error during liquidation: {e}")

if __name__ == "__main__":
    print("### Live Platform Position Liquidation Program ###")
    if not API_BASE_URL or not API_KEY or not SECRET_KEY:
        print("ERROR: Missing required environment variables. Please check your .env file.")
        exit(1)

    # Get the symbol to close
    symbol = input(f"Enter the symbol to close (default: {DEFAULT_SYMBOL}): ").strip() or DEFAULT_SYMBOL

    # Step 1: Fetch position details
    position = fetch_position(symbol)
    if not position:
        print(f"No open position found for {symbol}. Exiting.")
        exit(0)

    # Step 2: Validate position and proceed
    qty = position.get("qty")
    if qty:
        print("\n### WARNING: You are about to liquidate a LIVE position ###")
        confirmation = input(f"Type 'CONFIRM' to sell {qty} of {symbol}: ")
        if confirmation.strip().upper() == "CONFIRM":
            # Step 3: Liquidate position
            liquidate_position(symbol, qty)
        else:
            print("Position liquidation aborted by user.")
    else:
        print(f"No quantity available to liquidate for {symbol}.")
