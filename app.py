import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime, timezone
import requests

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "6558366634"
AXIOM_API_KEY = "axiom-api-key-placeholder"
AXIOM_INGEST_URL = "https://api.axiom.co/v1/datasets/justamemecoin_trades/ingest"

# === TRACKING STATE ===
active_gauges = {}  # {token_address: message_id}
last_alerted_score = {}  # Prevent repeated alert spam

def get_token_name(mint_address):
    try:
        url = f"https://mainnet.helius-rpc.com/?api-key=b7586bedae034d9bb58c5df3f4168b03"
        payload = {
            "jsonrpc": "2.0",
            "id": "name-check",
            "method": "getAsset",
            "params": { "id": mint_address }
        }
        response = requests.post(url, json=payload)
        metadata = response.json().get("result", {})
        return metadata.get("content", {}).get("metadata", {}).get("name", mint_address)
    except:
        return mint_address

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    return requests.post(url, json=payload)

def edit_telegram_message(message_id, new_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "Markdown"
    }
    return requests.post(url, json=payload)

def log_to_csv(data):
    with open("webhook_fallback_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([data.get("token_address"), data.get("pump_score"), data.get("timestamp")])

@app.route("/helfire", methods=["POST"])
def helfire():
    data = request.get_json()

    token = data.get("token_address")
    score = int(data.get("pump_score"))
    ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())

    # === LOG TO CSV IF AXIOM FAILS ===
    try:
        ax = requests.post(
            AXIOM_INGEST_URL,
            headers={"Authorization": f"Bearer {AXIOM_API_KEY}"},
            json=[data]
        )
        if ax.status_code != 200:
            log_to_csv(data)
    except Exception:
        log_to_csv(data)

    # === Lookup Token Name ===
    name = get_token_name(token)

    # === ALERT ONLY ONCE ABOVE THRESHOLD ===
    if score >= 7 and last_alerted_score.get(token) != score:
        last_alerted_score[token] = score
        strength_bar = "🟩" * score + "⬜️" * (10 - score)
        text = f"""🚀 *Pump Score {score} detected!*

Token: `{token}`
Name: *{name}*
Pump Strength:
{strength_bar} ({score}/10)
_Live gauge updates will follow..._"""
        res = send_telegram_message(text)
        if res.status_code == 200:
            message_id = res.json()["result"]["message_id"]
            active_gauges[token] = message_id
        return jsonify({"status": "alerted"})

    # === LIVE GAUGE UPDATE ===
    if token in active_gauges:
        if score <= 3:
            edit_telegram_message(active_gauges[token], f"🔻 *Pump Score faded to {score}*\nToken: `{token}`\nNo longer tracking.")
            del active_gauges[token]
        else:
            strength_bar = "🟩" * score + "⬜️" * (10 - score)
            edit_telegram_message(active_gauges[token], f"""🚀 *Pump Score {score}!*

Token: `{token}`
Name: *{name}*
Pump Strength:
{strength_bar} ({score}/10)""")
        return jsonify({"status": "updated"})

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)
