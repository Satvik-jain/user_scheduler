import os
import time
import requests
import json
from dotenv import load_dotenv
TOKEN_FILE = "zoho_tokens.json"
load_dotenv()
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")
TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"

def read_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as file:
            return json.load(file)
    return {}

def write_tokens(data):
    with open(TOKEN_FILE, "w") as file:
        json.dump(data, file)

def get_access_token():
    tokens = read_tokens()
    
    if tokens.get("access_token") and time.time() < tokens.get("expires_at", 0):
        return tokens["access_token"]

    response = requests.post(
        TOKEN_URL,
        data={
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
    )

    if response.status_code == 200:
        new_tokens = response.json()
        # print(new_tokens)
        new_tokens["expires_at"] = time.time() + new_tokens["expires_in"] - 60  
        
        write_tokens(new_tokens)
        return new_tokens["access_token"]
    
    raise Exception(f"Failed to refresh access token: {response.text}")
