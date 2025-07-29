import os
import csv
import json
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timezone

app = Flask(__name__)

# === CONFIG WITH YOUR INFO ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "6558366634"
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
AXIOM_TOKEN = os.getenv("AXIOM_TOKEN")
HELIUS_API_KEY = "b7586bedae034d9bb58c5df3f4168b03"

PUMP_SCORE_THRESHOLD = 7
FADE_SCORE_THRESHOLD = 3
ALERTED_FILE = "alerted_tokens.json"

# === STATE ===
def load_alerted_tokens():
    try:
        if os.path.exists(ALERTED_FILE):
            with open(ALERTED_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[❌ load_alerted_tokens error]: {e}")
    return {}

def save_alerted_tokens(data):
    try:
        with open(ALERTED_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[❌ save_alerted_tokens error]: {e}")

alerted_tokens = load_alerted_tokens()

# === UTILS ===
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

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"})
    return response.json()

def edit_telegram_message(message_id, new_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    response = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "Markdown"
    })
    return response.json()

def log_to_csv(token_address, pump_score, timestamp):
    with open("pump_score_log.csv", mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, token_address, pump_score])

def forward_to_axiom(data):
    headers = {"Authorization": f"Bearer {AXIOM_TOKEN}"}
    try:
        requests.post(AXIOM_INGEST_URL, json=data, headers=headers, timeout=5)
    except Exception:
        log_to_csv(data.get("token_address", "unknown"), data.get("pump_score", 0), data.get("timestamp", "n/a"))

def generate_gauge(score):
    filled = "🟩" * score
    empty = "⬜️" * (10 - score)
    return f"{filled}{empty} ({score}/10)"

# === MAIN WEBHOOK ===
@app.route("/helfire", methods=["POST"])
def helfire():
    global alerted_tokens
    data = request.json

    try:
        token = data.get("token_address")
        score = data.get("pump_score")
        timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

        if token is None or score is None:
            print("[❌ Missing token or score]")
            return jsonify({"error": "Missing token_address or pump_score"}), 400

        score = int(score)
        log_to_csv(token, score, timestamp)
        forward_to_axiom(data)

        alerted_tokens = load_alerted_tokens()
        token_name = get_token_metadata(token)

        # Case 1: New alert
        if token not in alerted_tokens and score >= PUMP_SCORE_THRESHOLD:
            text = (
                f"🚀 *Pump Score {score} detected!*\n\n"
                f"*Token:* {token_name}\n"
                f"*Pump Strength:*\n{generate_gauge(score)}\n"
                f"_Live gauge updates will follow..._"
            )
            sent = send_telegram_message(text)
            message_id = sent.get("result", {}).get("message_id")

            if message_id:
                alerted_tokens[token] = {"message_id": message_id, "last_score": score}
                save_alerted_tokens(alerted_tokens)

        # Case 2: Update gauge
        elif token in alerted_tokens:
            last_score = alerted_tokens[token]["last_score"]
            message_id = alerted_tokens[token]["message_id"]

            if score != last_score:
                new_text = (
                    f"🚀 *Pump Score {score}*\n\n"
                    f"*Token:* {token_name}\n"
                    f"*Pump Strength:*\n{generate_gauge(score)}"
                )
                edit_telegram_message(message_id, new_text)
                alerted_tokens[token]["last_score"] = score
                save_alerted_tokens(alerted_tokens)

            if score <= FADE_SCORE_THRESHOLD:
                alerted_tokens.pop(token, None)
                save_alerted_tokens(alerted_tokens)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[❌ CRITICAL ERROR in /helfire]: {e}")
        return jsonify({"error": str(e)}), 500
