import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

# === ENV CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === Telegram Alert Function ===
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not set.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            print("❌ Failed to send Telegram message:", response.text)
    except Exception as e:
        print("❌ Telegram send error:", str(e))

# === Test Route ===
@app.route("/test-alert", methods=["GET"])
def test_alert():
    send_telegram_message("✅ Manual test alert from Pump Sniper Bot (via /test-alert)")
    return jsonify({"status": "sent"})

# === Startup Alert ===
@app.before_serving
async def startup():
    send_telegram_message("🚀 Pump Sniper Bot just went *live* on Render!")

# === Root Route ===
@app.route("/", methods=["GET"])
def index():
    return "Pump Sniper Bot is Live"

# === Run Locally ===
if __name__ == "__main__":
    app.run(debug=True)

