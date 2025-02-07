import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Alpaca API Credentials
API_BASE_URL = os.getenv("LIVE_BASE_URL")
API_KEY = os.getenv("LIVE_API_KEY")
SECRET_KEY = os.getenv("LIVE_SECRET_KEY")

def check_conversion_support():
    """
    Check if Alpaca supports crypto-to-crypto conversions.
    """
    try:
        endpoint = f"{API_BASE_URL}/v2/crypto/conversion"
        headers = {
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": SECRET_KEY,
        }
        response = requests.options(endpoint, headers=headers)  # OPTIONS request checks endpoint availability
        if response.status_code == 200:
            print("Crypto conversion is supported.")
        else:
            print(f"Crypto conversion not supported. Status Code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"Error checking conversion support: {e}")

def withdraw_crypto(symbol, qty, wallet_address):
    """
    Withdraw cryptocurrency to an external wallet.
    """
    try:
        endpoint = f"{API_BASE_URL}/v2/crypto/withdrawals"
        headers = {
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": SECRET_KEY,
        }
        payload = {
            "currency": symbol,
            "qty": str(qty),
            "crypto_address": wallet_address,
        }
        response = requests.post(endpoint, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"Successfully withdrew {qty} {symbol} to {wallet_address}.")
            print("Response:", response.json())
        else:
            print(f"Failed to withdraw {symbol}. Status Code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"Error during withdrawal: {e}")

if __name__ == "__main__":
    symbol = "USDT"
    qty = 9.785282934  # Replace with your actual USDT quantity

    # Step 1: Check conversion support
    print("Checking if crypto-to-crypto conversion is supported...")
    check_conversion_support()

    # Step 2: If not supported, withdraw to an external platform (Kraken)
    wallet_address = input("Enter your Kraken USDT deposit address: ")
    print(f"Withdrawing {qty} {symbol} to {wallet_address}...")
    withdraw_crypto(symbol, qty, wallet_address)
