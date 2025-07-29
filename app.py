import os
import csv
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timezone

app = Flask(__name__)

# === ENV VARS ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
AXIOM_TOKEN = os.getenv("AXIOM_TOKEN")

# === CONFIG ===
PUMP_SCORE_THRESHOLD = 7
FADE_SCORE_THRESHOLD = 3

# === STATE TRACKING ===
alerted_tokens = {}  # format: {token_address: {"message_id": 123, "last_score": 8}}

# === UTILITIES ===
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    return response.json()

def edit_telegram_message(message_id, new_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    response = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": new_text
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
        # Fallback to CSV if Axiom fails
        log_to_csv(data.get("token_address", "unknown"), data.get("pump_score", 0), data.get("timestamp", "n/a"))

def generate_gauge(score):
    filled = "🟩" * score
    empty = "⬜️" * (10 - score)
    return f"{filled}{empty} ({score}/10)"

# === MAIN WEBHOOK ===
@app.route("/helfire", methods=["POST"])
def helfire():
    data = request.json
    token = data.get("token_address")
    score = data.get("pump_score")
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

    if token is None or score is None:
        return jsonify({"error": "Missing token_address or pump_score"}), 400

    score = int(score)
    log_to_csv(token, score, timestamp)
    forward_to_axiom(data)

    # Case 1: New pump alert
    if token not in alerted_tokens and score >= PUMP_SCORE_THRESHOLD:
        text = (
            f"🚀 *Pump Score {score} detected!*\n\n"
            f"Token: `{token}`\n"
            f"Pump Strength:\n{generate_gauge(score)}\n"
            f"_Live gauge updates will follow..._"
        )
        sent = send_telegram_message(text)
        message_id = sent.get("result", {}).get("message_id")

        if message_id:
            alerted_tokens[token] = {"message_id": message_id, "last_score": score}

    # Case 2: Update existing gauge
    elif token in alerted_tokens:
        last_score = alerted_tokens[token]["last_score"]
        message_id = alerted_tokens[token]["message_id"]

        # Update gauge only if score changed
        if score != last_score:
            new_text = (
                f"🚀 *Pump Score {score}*\n\n"
                f"Token: `{token}`\n"
                f"Pump Strength:\n{generate_gauge(score)}"
            )
            edit_telegram_message(message_id, new_text)
            alerted_tokens[token]["last_score"] = score

        # If it fades below fade score, remove it from tracking
        if score <= FADE_SCORE_THRESHOLD:
            alerted_tokens.pop(token, None)

    return jsonify({"status": "ok"}), 200
