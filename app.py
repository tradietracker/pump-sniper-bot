import os
import csv
from flask import Flask, request, jsonify
import requests
from datetime import datetime, timezone

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
CSV_FALLBACK_FILE = "webhook_fallback.csv"

def send_telegram_alert(message):
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(telegram_url, json=payload)
    print("[Telegram Response]", response.status_code, response.text)
    return response.status_code == 200

@app.route("/")
def home():
    return "Pump Sniper Bot is live!"

@app.route("/test-alert")
def test_alert():
    sent = send_telegram_alert("🚀 Test alert from Pump Sniper Bot is working!")
    return jsonify({"sent": sent})

@app.route(f"/{os.getenv('WEBHOOK_PATH', 'helfire')}", methods=["POST"])
def handle_webhook():
    try:
        data = request.get_json()
        print("[🔥 Webhook Received]")
        if isinstance(data, list):
            for item in data:
                process_event(item)
        else:
            process_event(data)
        return jsonify({"status": "ok"})
    except Exception as e:
        print("[Webhook Error]", str(e))
        return jsonify({"error": str(e)}), 500

def process_event(event):
    try:
        # Log to Axiom
        if AXIOM_INGEST_URL:
            axiom_resp = requests.post(AXIOM_INGEST_URL, json=event)
            print("[✅ Forwarded to Axiom]", axiom_resp.status_code)

        # Log to CSV fallback
        with open(CSV_FALLBACK_FILE, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                datetime.now(timezone.utc).isoformat(),
                event.get("description", ""),
                event.get("amount", ""),
                event.get("source", ""),
                event.get("destination", ""),
                event.get("signature", "")
            ])
    except Exception as e:
        print("[⚠️ CSV Log Error]", str(e))

# === Telegram Bot Handler ===
@app.route("/start-bot", methods=["POST"])
def handle_start():
    data = request.get_json()
    message = data.get("message", {}).get("text", "")
    chat_id = data.get("message", {}).get("chat", {}).get("id")

    if message == "/start":
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "👋 Hey! Pump Sniper Bot is now active in this chat."
        }
        resp = requests.post(telegram_url, json=payload)
        return jsonify({"status": "replied", "telegram_response": resp.text})
    return jsonify({"status": "ignored"})

if __name__ == "__main__":
    app.run(debug=True)

