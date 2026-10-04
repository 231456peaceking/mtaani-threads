"""Mtaani Threads web server (Flask). Run:  python3 app.py"""
import os, threading
from flask import Flask, jsonify, request, send_from_directory
import daraja

app = Flask(__name__, static_folder="public", static_url_path="")

# Prices live on the SERVER so customers can't change them in the browser.
PRODUCTS = [
    {"id": "s1", "type": "shirt",   "name": "Kitenge Shirt",           "price": 1200, "color": "#f2a900", "bg": "#fff4d6", "desc": "Bold African print, short sleeves.",       "fabric": "Cotton",          "fit": "Regular",  "sizes": ["S", "M", "L", "XL"]},
    {"id": "s2", "type": "shirt",   "name": "Oxford Shirt",            "price": 1500, "color": "#1f7a8c", "bg": "#dff1f4", "desc": "Smart long-sleeve shirt for the office.", "fabric": "Cotton",          "fit": "Slim",     "sizes": ["S", "M", "L", "XL"]},
    {"id": "s3", "type": "shirt",   "name": "Silk Evening Shirt",      "price": 2800, "color": "#8a2b4a", "bg": "#f6dfe7", "desc": "Smooth and light with a soft shine.",      "fabric": "Silk",            "fit": "Relaxed",  "sizes": ["M", "L", "XL"]},
    {"id": "t1", "type": "trouser", "name": "Khaki Chinos",            "price": 1800, "color": "#b08d57", "bg": "#f3ead9", "desc": "Everyday chinos, easy to dress up.",       "fabric": "Cotton twill",    "fit": "Straight", "sizes": ["30", "32", "34", "36"]},
    {"id": "t2", "type": "trouser", "name": "Black Official Trousers", "price": 2200, "color": "#14213d", "bg": "#dfe3ec", "desc": "Creased front, ready for meetings.",       "fabric": "Polyester blend", "fit": "Slim",     "sizes": ["30", "32", "34", "36"]},
    {"id": "t3", "type": "trouser", "name": "Linen Trousers",          "price": 2500, "color": "#6b8f71", "bg": "#e2eee4", "desc": "Cool and breathable for hot days.",        "fabric": "Linen",           "fit": "Relaxed",  "sizes": ["30", "32", "34"]},
]


IMG_DIR = os.path.join(app.static_folder, "images")


def find_image(pid):
    """public/images/<id>.jpg|jpeg|png|webp|svg -> URL (real photos win over the drawn svg)."""
    for ext in ("jpg", "jpeg", "png", "webp", "svg"):
        if os.path.exists(os.path.join(IMG_DIR, f"{pid}.{ext}")):
            return f"/images/{pid}.{ext}"
    return None

ORDERS = {}  # checkout_id -> order (in memory; use a database later)
SIMULATE = os.getenv("SIMULATE_CALLBACK", "false").lower() == "true"


@app.get("/")
def home():
    return send_from_directory("public", "index.html")


@app.get("/api/products")
def products():
    return jsonify([{**p, "image": find_image(p["id"])} for p in PRODUCTS])


@app.post("/api/pay")
def pay():
    data = request.get_json(silent=True) or {}
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items or len(raw_items) > 20:
        return jsonify(error="Your cart is empty."), 400

    items, total = [], 0
    for it in raw_items:
        product = next((p for p in PRODUCTS if p["id"] == (it or {}).get("productId")), None)
        size, qty = (it or {}).get("size"), (it or {}).get("qty")
        if not product or size not in product["sizes"] or not isinstance(qty, int) or not 1 <= qty <= 10:
            return jsonify(error="Invalid item in cart."), 400
        items.append({"productId": product["id"], "name": product["name"], "size": size, "qty": qty, "price": product["price"]})
        total += product["price"] * qty  # price comes from the server, never the browser

    phone = daraja.normalize_phone(data.get("phone"))
    if not phone:
        return jsonify(error="Enter a valid phone number, e.g. 0712345678."), 400
    missing = daraja.missing_settings()
    if missing:
        print("Missing in .env:", ", ".join(missing))
        return jsonify(error="Server is not set up yet (missing: " + ", ".join(missing) + ")."), 500

    print("Prompting number:", phone, "| items:", len(items), "| total KES", total)
    try:
        reply = daraja.stk_push(phone, total)
    except daraja.DarajaError as e:
        print("STK push error:", e)
        return jsonify(error="Could not start M-PESA payment: " + str(e)), 502

    cid = reply["CheckoutRequestID"]
    ORDERS[cid] = {"items": items, "phone": phone, "amount": total, "status": "pending"}
    if SIMULATE:  # sandbox demo helper only
        def fake_paid():
            o = ORDERS.get(cid)
            if o and o["status"] == "pending":
                o.update(status="paid", receipt="SIMULATED", message="Paid (sandbox simulation)")
        threading.Timer(8, fake_paid).start()
    return jsonify(checkoutRequestId=cid, total=total)


@app.get("/api/pay/status/<cid>")
def status(cid):
    o = ORDERS.get(cid)
    if not o:
        return jsonify(status="unknown"), 404
    return jsonify(status=o["status"], receipt=o.get("receipt"), message=o.get("message"))


@app.post("/api/pay-callback/<token>")
def callback(token):
    """Safaricom posts the final result here (via your ngrok link)."""
    if token != daraja.CALLBACK_SECRET:
        return "", 403
    r = daraja.parse_callback(request.get_json(silent=True))
    o = r and ORDERS.get(r["checkout_id"])
    if o:
        o["status"] = "paid" if r["success"] else "failed"
        o["receipt"] = r["receipt"]
        o["message"] = "Paid" if r["success"] else (r["message"] or "Payment was not completed.")
        print("Callback:", r["checkout_id"], o["status"], r["receipt"] or "")
    return jsonify(ResultCode=0, ResultDesc="Accepted")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    print(f"Mtaani Threads running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
