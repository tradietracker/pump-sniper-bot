import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime, timezone
import requests

app = Flask(__name__)

# === ENV CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")

# === TELEGRAM ALERT ===
def send_telegram_alert(message: str):
    try:
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(telegram_url, json=payload)
        print(f"Telegram response: {response.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

# === CSV FALLBACK ===
def log_to_csv(data):
    try:
        with open("webhook_fallback.csv", mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(data)
    except Exception as e:
        print(f"CSV log error: {e}")

# === WEBHOOK ENDPOINT ===
@app.route("/helfire", methods=["POST"])
def handle_webhook():
    try:
        json_data = request.get_json()

        # Extract trade data
        price = json_data.get("price", 0)
        amount = json_data.get("amount", 0)
        symbol = json_data.get("symbol", "UNKNOWN")
        side = json_data.get("side", "unknown")
        timestamp = datetime.now(timezone.utc).isoformat()

        # === Send to Axiom
        if AXIOM_INGEST_URL and AXIOM_API_KEY:
            headers = {
                "Authorization": f"Bearer {AXIOM_API_KEY}",
                "Content-Type": "application/json"
            }
            axiom_payload = {
                "_time": timestamp,
                "price": price,
                "amount": amount,
                "symbol": symbol,
                "side": side
            }
            axiom_response = requests.post(
                AXIOM_INGEST_URL, headers=headers, json=axiom_payload
            )

            if axiom_response.status_code != 200:
                print("Axiom ingest failed, logging to CSV.")
                log_to_csv([timestamp, symbol, price, amount, side])
        else:
            print("Axiom credentials not set, logging to CSV.")
            log_to_csv([timestamp, symbol, price, amount, side])

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# === SEND TELEGRAM ON STARTUP (RENDER-SAFE) ===
@app.before_first_request
def startup_alert():
    send_telegram_alert("✅ Telegram alert test successful from Pump Sniper Bot!")

