import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime
import json

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "-6558366634"
HELIUS_API_KEY = "e61c01b8-8e60-4c29-8144-559953796a62"  # Your updated key here
ALERTED_TOKENS = {}

# === UTILS ===
def get_token_name(mint_address):
    try:
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "mintAccounts": [mint_address]
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        result = response.json()
        name = result[0]["onChainMetadata"]["metadata"]["name"]
        return name
    except Exception:
        return mint_address  # fallback

def build_pump_gauge(score):
    filled = "🟩" * score
    empty = "⬜️" * (10 - score)
    return f"{filled}{empty} ({score}/10)"

def send_telegram_alert(token_address, pump_score, token_name):
    text = f"🚀 *Pump Score {pump_score} detected!*\n\n"
    text += f"*Token:* `{token_address}`\n"
    text += f"*Name:* {token_name}\n"
    text += f"*Pump Strength:*\n{build_pump_gauge(pump_score)}\n"
    text += "_Live gauge updates will follow..._"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def send_gauge_update(token_address, pump_score):
    token_name = get_token_name(token_address)
    message = f"📈 *Pump Score Update*\n\n"
    message += f"*Name:* {token_name}\n"
    message += f"*Strength:* {build_pump_gauge(pump_score)}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

# === ROUTES ===
@app.route("/")
def index():
    return "Pump Sniper Bot Live ✅"

@app.route("/helfire", methods=["POST"])
def handle_webhook():
    data = request.get_json()
    token = data.get("token_address")
    score = data.get("pump_score")
    timestamp = data.get("timestamp")

    if not token or not score:
        return jsonify({"error": "Missing fields"}), 400

    token_name = get_token_name(token)

    # Avoid duplicate alerts
    if token not in ALERTED_TOKENS or ALERTED_TOKENS[token] != score:
        ALERTED_TOKENS[token] = score
        if score >= 7:
            send_telegram_alert(token, score, token_name)
        else:
            send_gauge_update(token, score)

    print(f"[Webhook] {token} ({token_name}) → Score {score} at {timestamp}")
    return jsonify({"status": "ok"}), 200
