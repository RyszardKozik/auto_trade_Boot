import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Retrieve API credentials
API_BASE_URL = os.getenv("LIVE_BASE_URL")
API_KEY = os.getenv("LIVE_API_KEY")
SECRET_KEY = os.getenv("LIVE_SECRET_KEY")

def close_position(symbol):
    """
    Close an open position for a specific symbol using Alpaca's close position endpoint.
    """
    try:
        endpoint = f"{API_BASE_URL}/v2/positions/{symbol}"
        headers = {
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": SECRET_KEY,
        }
        print(f"Attempting to close position for {symbol}...")
        response = requests.delete(endpoint, headers=headers)
        if response.status_code == 200:
            print(f"Position for {symbol} successfully closed.")
            print("Response:", response.json())
        elif response.status_code == 403:
            print("403 Forbidden: Check for account restrictions or permissions.")
            print("Response:", response.json())
            if "EU tax resident" in response.text:
                print("USDT is restricted for EU accounts. Consider converting USDT to another asset or transferring funds to another platform.")
        elif response.status_code == 404:
            print(f"Position for {symbol} not found or already closed.")
        else:
            print(f"Failed to close position. Status Code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"Error during position closure: {e}")

if __name__ == "__main__":
    symbol = "USDTUSD"  # Specify the asset to close
    confirmation = input(f"Are you sure you want to CLOSE the position for {symbol}? Type 'CONFIRM' to proceed: ")
    if confirmation.strip().upper() == "CONFIRM":
        close_position(symbol)
    else:
        print("Operation canceled by user.")
