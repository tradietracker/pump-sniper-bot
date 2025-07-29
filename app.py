import os
import csv
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timezone

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "6558366634"
AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")
AXIOM_DATASET = "justamemecoin_trades"
AXIOM_INGEST_URL = f"https://api.axiom.co/v1/datasets/{AXIOM_DATASET}/ingest"

# === GLOBAL STATE ===
alerted_tokens = {}  # {token_address: {"message_id": int, "last_score": int}}

# === HELPERS ===
def get_token_metadata(mint):
    url = f"https://mainnet.helius-rpc.com/?api-key=b7586bedae034d9bb58c5df3f4168b03"
    payload = {
        "jsonrpc": "2.0",
        "id": "pump-sniper",
        "method": "getTokenMetadata",
        "params": {"mint": mint}
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        return data.get("result", {}).get("name", "Unknown Token")
    except:
        return "Unknown Token"

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

def post_to_axiom(event):
    headers = {"Authorization": f"Bearer {AXIOM_API_KEY}"}
    try:
        response = requests.post(AXIOM_INGEST_URL, json={"events": [event]}, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

def log_to_csv(event):
    with open("webhook_log.csv", "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=event.keys())
        writer.writerow(event)

def get_gauge(score):
    return "🟩" * score + "⬜️" * (10 - score)

# === WEBHOOK ENDPOINT ===
@app.route("/helfire", methods=["POST"])
def helfire():
    try:
        data = request.get_json()
        token = data.get("token_address")
        score = int(data.get("pump_score", 0))
        timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

        print(f"[🔥 Webhook Received] {token} → Score {score}")

        event = {
            "token_address": token,
            "pump_score": score,
            "_time": timestamp
        }

        # Send to Axiom or fallback to CSV
        if not post_to_axiom(event):
            print("[📝 Logged to CSV fallback]")
            log_to_csv(event)

        # Handle gauge alerting
        if score >= 7:
            if token not in alerted_tokens:
                name = get_token_metadata(token)
                gauge = get_gauge(score)
                text = (
                    f"🚀 *Pump Score {score} detected!*\n\n"
                    f"*Token:* `{token}`\n"
                    f"*Name:* `{name}`\n"
                    f"*Pump Strength:*\n{gauge} ({score}/10)\n"
                    f"_Live gauge updates will follow..._"
                )
                res = send_telegram_message(text)
                if res.ok:
                    message_id = res.json()["result"]["message_id"]
                    alerted_tokens[token] = {"message_id": message_id, "last_score": score}
            else:
                # Update gauge if score has changed
                last_score = alerted_tokens[token]["last_score"]
                if score != last_score:
                    gauge = get_gauge(score)
                    new_text = (
                        f"🚀 *Pump Score {score}*\n\n"
                        f"*Token:* `{token}`\n"
                        f"*Pump Strength:*\n{gauge} ({score}/10)"
                    )
                    edit_telegram_message(alerted_tokens[token]["message_id"], new_text)
                    alerted_tokens[token]["last_score"] = score

        # Fade-out cleanup
        if score < 3 and token in alerted_tokens:
            print(f"🧼 Removing faded token from tracking: {token}")
            del alerted_tokens[token]

        return jsonify({"status": "ok"})

    except Exception as e:
        print(f"[❌ Error]: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "Pump Sniper Bot Active!", 200
