import os
import requests
import csv
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "-1002121513660"
HELIUS_API_KEY = "b7586bedae034d9bb58c5df3f4168b03"  # from project pumpscorebot

alerted_tokens = {}
live_gauges = {}

def get_token_name(mint_address):
    try:
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
        headers = {"Content-Type": "application/json"}
        data = {"mintAccounts": [mint_address]}
        res = requests.post(url, headers=headers, json=data)
        res.raise_for_status()
        result = res.json()
        if isinstance(result, list) and result and "name" in result[0]:
            return result[0]["name"]
        return mint_address
    except Exception:
        return mint_address

def send_telegram_message(text, disable_notification=False, message_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{'editMessageText' if message_id else 'sendMessage'}"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_notification": disable_notification
    }
    if message_id:
        payload["message_id"] = message_id
    response = requests.post(url, json=payload)
    return response.json()

def score_to_gauge(score):
    full = "🟩" * score
    empty = "⬜️" * (10 - score)
    return f"{full}{empty} ({score}/10)"

@app.route("/")
def index():
    return "Pump Sniper Bot Active"

@app.route("/helfire", methods=["POST"])
def helfire():
    data = request.get_json()
    token_address = data.get("token_address")
    score = int(data.get("pump_score", 0))
    timestamp = data.get("timestamp", datetime.utcnow().isoformat())

    if not token_address or score < 1:
        return jsonify({"status": "ignored"})

    name = get_token_name(token_address)

    now = datetime.utcnow()
    last_alert = alerted_tokens.get(token_address)
    if last_alert and (now - last_alert).seconds < 300:
        return jsonify({"status": "duplicate"})

    alerted_tokens[token_address] = now

    alert_message = (
        f"🚀 *Pump Score {score} detected!*\n\n"
        f"*Token:* `{token_address}`\n"
        f"*Name:* `{name}`\n"
        f"*Pump Strength:*\n{score_to_gauge(score)}\n"
        f"_Live gauge updates will follow..._"
    )
    response = send_telegram_message(alert_message)
    msg_id = response.get("result", {}).get("message_id")
    if msg_id:
        live_gauges[token_address] = msg_id

    # Log to CSV
    with open("pump_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, token_address, name, score])

    return jsonify({"status": "ok"})

@app.route("/update_gauge", methods=["POST"])
def update_gauge():
    data = request.get_json()
    token_address = data.get("token_address")
    score = int(data.get("pump_score", 0))

    if token_address not in live_gauges or score < 1:
        return jsonify({"status": "ignored"})

    gauge = score_to_gauge(score)
    msg_id = live_gauges[token_address]
    name = get_token_name(token_address)

    updated_text = (
        f"🚀 *Pump Score {score}*\n\n"
        f"*Token:* `{token_address}`\n"
        f"*Name:* `{name}`\n"
        f"*Pump Strength:*\n{gauge}"
    )
    send_telegram_message(updated_text, message_id=msg_id)

    # Remove if score drops below 3
    if score < 3:
        live_gauges.pop(token_address, None)
        alerted_tokens.pop(token_address, None)

    return jsonify({"status": "updated"})

if __name__ == "__main__":
    app.run(debug=True)
