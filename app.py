import os
import csv
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

# === ENV CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")

# === HELPERS ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload)
        print(f"[Telegram Response] Status: {res.status_code}, Body: {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"[Telegram Error] {e}")
        return False

def log_to_csv(event):
    try:
        timestamp = datetime.utcnow().isoformat()
        with open("webhook_log.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, event])
    except Exception as e:
        print(f"[⚠️ CSV Log Error] {e}")

# === ROUTES ===
@app.route("/helfire", methods=["POST"])
def helfire():
    event = request.json
    print("[🔥 Webhook Received]")

    # Log to Axiom if available
    if AXIOM_API_KEY and AXIOM_INGEST_URL:
        try:
            res = requests.post(
                AXIOM_INGEST_URL,
                json=event,
                headers={"Authorization": f"Bearer {AXIOM_API_KEY}"}
            )
            print(f"[✅ Forwarded to Axiom] {res.status_code}")
        except Exception as e:
            print(f"[⚠️ Axiom Error] {e}")

    # Fallback log to CSV
    try:
        log_to_csv(event)
    except Exception as e:
        print(f"[⚠️ CSV Logging Failed] {e}")

    return jsonify({"received": True})

@app.route("/test-alert", methods=["GET"])
def test_alert():
    success = send_telegram_message("✅ Manual test alert from Pump Sniper Bot (via /test-alert)")
    return jsonify({"sent": success})

if __name__ == "__main__":
    app.run(debug=True)

