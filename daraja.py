"""Daraja (M-PESA) integration. Same flow as tools/daraja_test.py, made reusable for the website."""
import os, base64, time, requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("DARAJA_ENV", "sandbox")
BASE = "https://api.safaricom.co.ke" if ENV == "production" else "https://sandbox.safaricom.co.ke"
CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET")
SHORTCODE = os.getenv("DARAJA_SHORTCODE", "174379")
PASSKEY = os.getenv("DARAJA_PASSKEY")
CALLBACK_URL = os.getenv("DARAJA_CALLBACK_URL", "")
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET", "")

_token = {"value": None, "expires": 0}


class DarajaError(Exception):
    pass


def missing_settings():
    need = {"DARAJA_CONSUMER_KEY": CONSUMER_KEY, "DARAJA_CONSUMER_SECRET": CONSUMER_SECRET,
            "DARAJA_PASSKEY": PASSKEY, "DARAJA_CALLBACK_URL": CALLBACK_URL}
    return [k for k, v in need.items() if not v]


def normalize_phone(raw):
    """0712345678 / 0112345678 / +254712345678 -> 254712345678, or None."""
    n = "".join(c for c in str(raw or "") if c not in " +-")
    if len(n) == 10 and n[0] == "0" and n[1] in "17" and n.isdigit():
        return "254" + n[1:]
    if len(n) == 12 and n.startswith("254") and n[3] in "17" and n.isdigit():
        return n
    return None


def get_access_token():
    if _token["value"] and time.time() < _token["expires"]:
        return _token["value"]
    try:
        r = requests.get(f"{BASE}/oauth/v1/generate?grant_type=client_credentials",
                         auth=(CONSUMER_KEY, CONSUMER_SECRET), timeout=60)
        r.raise_for_status()
        d = r.json()
    except requests.exceptions.RequestException as e:
        raise DarajaError(f"Could not reach Safaricom to get a token: {e}")
    _token["value"] = d["access_token"]
    _token["expires"] = time.time() + int(d.get("expires_in", 3599)) - 60
    return _token["value"]


def stk_push(phone, amount, reference="MTAANI", description="Clothing"):
    """Send the M-PESA prompt to `phone` (254XXXXXXXXX). Returns Safaricom's JSON."""
    token = get_access_token()
    timestamp = datetime.now(timezone(timedelta(hours=3))).strftime("%Y%m%d%H%M%S")  # Nairobi time
    password = base64.b64encode(f"{SHORTCODE}{PASSKEY}{timestamp}".encode()).decode()
    callback = f"{CALLBACK_URL}?token={CALLBACK_SECRET}"
    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": os.getenv("DARAJA_TXN_TYPE", "CustomerPayBillOnline"),
        "Amount": int(round(amount)),
        "PartyA": phone,
        "PartyB": os.getenv("DARAJA_PARTY_B", SHORTCODE),
        "PhoneNumber": phone,
        "CallBackURL": callback,
        "AccountReference": reference[:12],
        "TransactionDesc": description[:13],
    }
    try:
        r = requests.post(f"{BASE}/mpesa/stkpush/v1/processrequest", json=payload,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                          timeout=60)
        data = r.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        raise DarajaError(f"STK push request failed: {e}")
    print("Safaricom replied:", data)
    if data.get("ResponseCode") != "0":
        raise DarajaError(data.get("errorMessage") or data.get("ResponseDescription") or "STK push rejected")
    return data


def parse_callback(body):
    cb = (body or {}).get("Body", {}).get("stkCallback")
    if not cb:
        return None
    items = (cb.get("CallbackMetadata") or {}).get("Item", [])
    receipt = next((i.get("Value") for i in items if i.get("Name") == "MpesaReceiptNumber"), None)
    return {"checkout_id": cb.get("CheckoutRequestID"), "success": cb.get("ResultCode") == 0,
            "message": cb.get("ResultDesc"), "receipt": receipt}
