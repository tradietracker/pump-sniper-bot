import os
import csv
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "6558366634"
HELIUS_API_KEY = "9bc5aee3-1f9f-4434-98f3-b5dcd183b6f5"
ALERT_THRESHOLD = 7
FADE_THRESHOLD = 3
STATE_FILE = "alerted_tokens.json"
CSV_LOG = "webhook_fallback_log.csv"

# === STATE ===
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        alerted_tokens = json.load(f)
else:
    alerted_tokens = {}

# === UTILS ===
def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(alerted_tokens, f)

def log_to_csv(token_address, pump_score, timestamp):
    try:
        with open(CSV_LOG, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([token_address, pump_score, timestamp])
    except Exception as e:
        print(f"[CSV Logging Error] {e}")

def get_token_metadata(mint_address):
    try:
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}&mint={mint_address}"
        response = requests.get(url, timeout=5)
        metadata = response.json()
        name = metadata.get("name", None)
        symbol = metadata.get("symbol", None)

        if name and symbol:
            return f"{name} (${symbol})"
        elif name:
            return name
        elif symbol:
            return f"${symbol}"
        else:
            return "Unknown Token"
    except Exception as e:
        print(f"[❌ Token metadata lookup failed]: {e}")
        return "Unknown Token"

def send_telegram_alert(token_address, pump_score):
    token_name = get_token_metadata(token_address)
    gauge = "🟩" * pump_score + "⬜️" * (10 - pump_score)
    message = f"🚀 *Pump Score {pump_score} detected!*\n\nToken: {token_name}\nPump Strength:\n{gauge} ({pump_score}/10)\n\n_Live gauge updates will follow..._"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        r = requests.post(url, json=payload)
        print(f"[Telegram response]: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"[Telegram Error] {e}")

# === TEMP HALT ROUTE ===
@app.route("/helfire", methods=["POST"])
def helfire():
    return jsonify({"status": "temp hold"}), 200  # TEMP BLOCK — REMOVE AFTER DEBUG

if __name__ == "__main__":
    app.run(debug=True)
