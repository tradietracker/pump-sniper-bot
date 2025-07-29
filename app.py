import os
import csv
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timezone
from threading import Thread
import time

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "-1002103841338"
HELIUS_API_KEY = "b7586bedae034d9bb58c5df3f4168b03"
ALERT_THRESHOLD = 7
FADE_THRESHOLD = 3
GAUGE_UPDATE_INTERVAL = 6  # seconds

# === STATE ===
active_gauges = {}  # token -> score
last_alerted_scores = {}  # token -> last score sent


def fetch_token_name(mint):
    try:
        url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        payload = {
            "jsonrpc": "2.0",
            "id": "token-name-lookup",
            "method": "getTokenMetadata",
            "params": {
                "mint": mint
            }
        }
        response = requests.post(url, json=payload)
        result = response.json().get("result", {})
        name = result.get("name")
        if name and isinstance(name, str):
            return name
    except Exception as e:
        print(f"[ERROR] Token name fetch failed for {mint}: {e}")
    return mint  # fallback


def build_pump_gauge(score):
    return "🟩" * score + "⬜️" * (10 - score)


def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[ERROR] Telegram message failed: {e}")


def edit_telegram_message(message_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[ERROR] Telegram edit failed: {e}")


def track_live_gauge(token, name, score, initial_message_id):
    while True:
        time.sleep(GAUGE_UPDATE_INTERVAL)
        current_score = active_gauges.get(token, 0)
        if current_score < FADE_THRESHOLD:
            print(f"[INFO] Token {token} faded below threshold.")
            active_gauges.pop(token, None)
            break
        gauge = build_pump_gauge(current_score)
        text = (
            f"📊 *Live Pump Score: {current_score}*\n\n"
            f"Token: `{token}`\n"
            f"Name: *{name}*\n"
            f"{gauge} ({current_score}/10)"
        )
        edit_telegram_message(initial_message_id, text)


@app.route("/helfire", methods=["POST"])
def helfire():
    data = request.get_json()
    token = data.get("token_address")
    score = int(data.get("pump_score", 0))
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

    if not token or score is None:
        return jsonify({"error": "Missing token or score"}), 400

    token_name = fetch_token_name(token)
    print(f"[Webhook] {token_name} ({token}) → Score {score} at {timestamp}")

    # Avoid repeat alerts
    last_score = last_alerted_scores.get(token, 0)
    if score >= ALERT_THRESHOLD and score > last_score:
        last_alerted_scores[token] = score
        gauge = build_pump_gauge(score)
        text = (
            f"🚀 *Pump Score {score} detected!*\n\n"
            f"Token: `{token}`\n"
            f"Name: *{token_name}*\n"
            f"Pump Strength:\n{gauge} ({score}/10)\n"
            f"_Live gauge updates will follow..._"
        )
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        )
        message_id = response.json().get("result", {}).get("message_id")
        if message_id:
            active_gauges[token] = score
            Thread(target=track_live_gauge, args=(token, token_name, score, message_id)).start()

    # Update score if already tracking
    if token in active_gauges:
        active_gauges[token] = score

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(debug=True)
