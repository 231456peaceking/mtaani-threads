import requests
import base64
from datetime import datetime
import json
import os
from dotenv import load_dotenv
load_dotenv()  # added: reads ../.env

# Environment variables (set these)
CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET")
SHORTCODE = os.getenv("DARAJA_SHORTCODE", "174379")  # Sandbox test shortcode
PASSKEY = os.getenv("DARAJA_PASSKEY")
CALLBACK_URL = os.getenv("DARAJA_CALLBACK_URL", "https://yourdomain.com/callback")

SANDBOX_AUTH_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
SANDBOX_API_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

def get_access_token():
    """Get OAuth access token (valid 1 hour)"""
    auth = (CONSUMER_KEY, CONSUMER_SECRET)
    try:
        response = requests.get(SANDBOX_AUTH_URL, auth=auth, timeout=60)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.RequestException as e:
        print(f"Auth error: {e}")
        return None

def prompt_user_payment(phone_number, amount=1):
    """
    Prompt user with STK Push (no money taken in sandbox).
    
    Args:
        phone_number: User's phone in format 254XXXXXXXXX (no + or spaces)
        amount: Amount in KES (default 1 for testing)
    
    Returns:
        Response dict with CheckoutRequestID or error
    """
    token = get_access_token()
    if not token:
        return {"error": "Failed to get access token"}
    
    # Generate timestamp and password
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password_string = f"{SHORTCODE}{PASSKEY}{timestamp}"
    password = base64.b64encode(password_string.encode()).decode()
    
    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,  # **254XXXXXXXXX format required**
        "PartyB": SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "School Program",
        "TransactionDesc": "Test Payment Prompt"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            SANDBOX_API_URL,
            json=payload,
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API error: {e}")
        return {"error": str(e)}

# Example usage
if __name__ == "__main__":
    result = prompt_user_payment("254708926083", amount=1)
    print(json.dumps(result, indent=2))