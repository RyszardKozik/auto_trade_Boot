from dotenv import load_dotenv
import os

# Explicitly load .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Print the token to verify
access_token = os.getenv("QUESTRADE_ACCESS_TOKEN")
print(f"QUESTRADE_ACCESS_TOKEN: {access_token}")

if not access_token:
    print("Failed to load QUESTRADE_ACCESS_TOKEN. Check your .env file and path.")
else:
    print("QUESTRADE_ACCESS_TOKEN loaded successfully.")
