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
CSV_LOG_FILE = "fallback_log.csv"

# === UTILS ===
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        print("Telegram status code:", response.status_code)
        print("Telegram response:", response.text)
        return response.status_code == 200
    except Exception as e:
        print("Telegram send error:", str(e))
        return False

def log_to_csv(data):
    try:
        fieldnames = list(data.keys())
        file_exists = os.path.isfile(CSV_LOG_FILE)
        with open(CSV_LOG_FILE, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(data)
    except Exception as e:
        print("CSV logging error:", str(e))

# === ROUTES ===

@app.route('/')
def home():
    return jsonify({"status": "Pump Sniper Bot Webhook is Live"})

@app.route('/helfire', methods=['POST'])
def helfire():
    try:
        data = request.get_json()
        print("[🔥 Webhook Received]")
        print(data)

        # Forward to Axiom
        axiom_success = False
        if AXIOM_INGEST_URL:
            try:
                axiom_response = requests.post(AXIOM_INGEST_URL, json=data)
                axiom_success = axiom_response.status_code == 200
                print("[✅ Forwarded to Axiom]", axiom_response.status_code)
            except Exception as axiom_err:
                print("[❌ Axiom Error]", str(axiom_err))

        # Log to CSV fallback if Axiom failed
        if not axiom_success:
            log_to_csv(data)
            print("[📝 Logged to CSV fallback]")

        return jsonify({"received": True})
    except Exception as e:
        print("[❌ Webhook Error]", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/test-telegram')
def test_telegram():
    text = "🚨 <b>Pump Sniper Test</b>\nThis is a test message from your bot."
    success = send_telegram_message(text)
    return jsonify({"sent": success})

@app.route('/whoami', methods=['POST'])
def whoami():
    data = request.get_json()
    print("[/whoami POST]", data)
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        username = data["message"]["from"].get("username", "no_username")
        return jsonify({
            "chat_id": chat_id,
            "username": username
        })
    return jsonify({"error": "Invalid data"})

# === MAIN ===
if __name__ == '__main__':
    app.run(debug=True)

