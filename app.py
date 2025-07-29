import os
import csv
import json
from flask import Flask, request, jsonify
import requests
from datetime import datetime, timezone

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or "6558366634"
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY") or "b7586bedae034d9bb58c5df3f4168b03"

CSV_LOG_PATH = "webhook_fallback_log.csv"
active_gauges = {}

# === UTILITIES ===
def get_token_name(token_address: str) -> str:
    try:
        url = f"https://mainnet.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
        body = {"mintAccounts": [token_address]}
        res = requests.post(url, json=body, timeout=10)
        res.raise_for_status()
        data = res.json()
        if not data or not isinstance(data, list) or not data[0]:
            return token_address
        metadata = data[0].get("onChainMetadata", {}).get("metadata", {})
        name = metadata.get("name")
        return name if name else token_address
    except Exception as e:
        print(f"[Token Name Lookup Failed] {e}")
        return token_address

def send_telegram_message(text, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    response = requests.post(url, json=payload)
    print("Telegram response:", response.status_code, "-", response.text)
    return response.json()

def edit_telegram_message(message_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    response = requests.post(url, json=payload)
    print("Edit Telegram:", response.status_code, "-", response.text)

def log_to_csv(data):
    fieldnames = ["timestamp", "token_address", "pump_score"]
    file_exists = os.path.exists(CSV_LOG_PATH)
    with open(CSV_LOG_PATH, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

def format_gauge(score):
    filled = "🟩" * score
    empty = "⬜️" * (10 - score)
    return f"{filled}{empty} ({score}/10)"

# === ROUTES ===
@app.route("/")
def index():
    return "Pump Sniper Bot is live"

@app.route("/helfire", methods=["POST"])
def helfire():
    try:
        data = request.get_json()
        print("[🔥 Webhook Received]")
        print(json.dumps(data, indent=2))

        token_address = data.get("token_address")
        score = data.get("pump_score")
        timestamp = data.get("timestamp")

        if not token_address or score is None:
            return jsonify({"error": "Missing token_address or pump_score"}), 400

        # Lookup token name
        token_name = get_token_name(token_address)

        # Prevent duplicate gauges
        if token_address in active_gauges and score <= 3:
            print(f"[❌ Gauge Ended for {token_address}]")
            del active_gauges[token_address]
            return jsonify({"status": "removed"}), 200

        if token_address not in active_gauges and score >= 7:
            # New alert
            alert = f"🚀 *Pump Score {score} detected!*\n\n" \
                    f"Token: `{token_address}`\n" \
                    f"Name: *{token_name}*\n" \
                    f"Pump Strength:\n{format_gauge(score)}\n" \
                    f"_Live gauge updates will follow..._"
            msg = send_telegram_message(alert)
            active_gauges[token_address] = {
                "message_id": msg["result"]["message_id"]
            }

        elif token_address in active_gauges:
            # Gauge update
            msg_id = active_gauges[token_address]["message_id"]
            update = f"🚀 *Pump Score {score}!*\n\n" \
                     f"Token: `{token_address}`\n" \
                     f"Name: *{token_name}*\n" \
                     f"Pump Strength:\n{format_gauge(score)}"
            edit_telegram_message(msg_id, update)

        # Forward to Axiom (if needed)
        try:
            axiom_url = os.getenv("AXIOM_INGEST_URL")
            if axiom_url:
                res = requests.post(axiom_url, json=data, timeout=5)
                if res.status_code != 200:
                    raise Exception("Axiom error")
                print("[✅ Forwarded to Axiom]", res.status_code)
        except Exception as e:
            print("[📝 Logged to CSV fallback]")
            log_to_csv({
                "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
                "token_address": token_address,
                "pump_score": score
            })

        return jsonify({"status": "ok"})

    except Exception as e:
        print("[❌ ERROR]", str(e))
        return jsonify({"error": str(e)}), 500


# === MAIN ===
if __name__ == "__main__":
    app.run(debug=True)
