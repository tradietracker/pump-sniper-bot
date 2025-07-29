import os
import csv
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "6558366634"
HELIUS_API_KEY = "b7586bedae034d9bb58c5df3f4168b03"

# === TRACKERS ===
alerted_tokens = {}
gauge_messages = {}

# === HELIUS TOKEN NAME LOOKUP ===
def get_token_name(token_address: str) -> str:
    try:
        url = f"https://mainnet.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
        body = {"mintAccounts": [token_address]}
        res = requests.post(url, json=body, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data[0].get("onChainMetadata", {}).get("metadata", {}).get("name") or token_address
    except Exception:
        return token_address  # fallback

# === TELEGRAM ALERT ===
def send_telegram_message(text: str, parse_mode: str = "Markdown") -> int:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode}
    res = requests.post(url, json=payload, timeout=10)
    res.raise_for_status()
    return res.json().get("result", {}).get("message_id", 0)

# === TELEGRAM EDIT ===
def edit_telegram_message(message_id: int, new_text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "Markdown",
    }
    requests.post(url, json=payload, timeout=10)

# === LIVE GAUGE DRAW ===
def draw_pump_gauge(score: int) -> str:
    return "🟩" * score + "⬜️" * (10 - score)

# === CSV FALLBACK ===
def log_to_csv(token_address: str, pump_score: int, timestamp: str):
    with open("fallback_log.csv", mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([datetime.utcnow().isoformat(), token_address, pump_score, timestamp])

# === MAIN WEBHOOK ===
@app.route("/helfire", methods=["POST"])
def helfire():
    try:
        data = request.get_json()
        token_address = data["token_address"]
        pump_score = int(data["pump_score"])
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())

        # Check for repeat alert in last 10 mins
        now = datetime.utcnow()
        last_alert_time = alerted_tokens.get(token_address)
        if last_alert_time and now - last_alert_time < timedelta(minutes=10):
            return jsonify({"status": "skipped: duplicate"})

        # Save alert timestamp
        alerted_tokens[token_address] = now

        # Lookup token name
        token_name = get_token_name(token_address)

        # Send initial alert
        gauge = draw_pump_gauge(pump_score)
        alert = f"🚀 *Pump Score {pump_score} detected!*\n\nToken: `{token_address}`\nName: *{token_name}*\nPump Strength:\n{gauge} ({pump_score}/10)\n_Live gauge updates will follow..._"
        message_id = send_telegram_message(alert)

        # Save gauge message ID
        gauge_messages[token_address] = message_id

        return jsonify({"status": "ok"})

    except Exception as e:
        log_to_csv(
            token_address=data.get("token_address", "unknown"),
            pump_score=data.get("pump_score", 0),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat())
        )
        return jsonify({"error": str(e)}), 500

# === GAUGE UPDATE ENDPOINT (OPTIONAL) ===
@app.route("/update-gauge", methods=["POST"])
def update_gauge():
    try:
        data = request.get_json()
        token_address = data["token_address"]
        pump_score = int(data["pump_score"])

        if token_address not in gauge_messages:
            return jsonify({"error": "Token not being tracked."}), 404

        token_name = get_token_name(token_address)
        gauge = draw_pump_gauge(pump_score)
        updated_text = f"🚀 *Pump Score {pump_score}*\n\nToken: `{token_address}`\nName: *{token_name}*\nPump Strength:\n{gauge} ({pump_score}/10)"

        edit_telegram_message(gauge_messages[token_address], updated_text)
        return jsonify({"status": "updated"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    return "Pump Sniper Bot is running.", 200
