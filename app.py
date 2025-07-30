import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime
import requests

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "6558366634"
HELIUS_API_KEY = "e61c01b8-8e60-4c29-8144-559953796a62"
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")

# === MEMORY ===
alerted_tokens = {}

# === HELPERS ===
def get_token_name(mint):
    """Look up a token’s name from Helius. Falls back to the mint address on error."""
    try:
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
        response = requests.post(url, json={"mintAccounts": [mint]}, timeout=5)
        response.raise_for_status()
        result = response.json()
        return result[0].get("onChainMetadata", {}).get("metadata", {}).get("name", mint)
    except Exception as e:
        print(f"[Token Lookup Error] {e}")
        return mint

def build_pump_gauge(score):
    """Return a visual gauge string for a pump score out of 10."""
    filled = "🟩" * score
    empty = "⬜️" * (10 - score)
    return f"{filled}{empty} ({score}/10)"

def send_telegram_alert(token_address, token_name, pump_score):
    """Send a formatted pump alert message to Telegram."""
    gauge_blocks = build_pump_gauge(pump_score)
    message = f"""
🚀 *Pump Score {pump_score} detected!*

Token: `{token_address}`
Name: *{token_name}*
Pump Strength:
{gauge_blocks}
_Live gauge updates will follow..._
    """
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        print(f"[Telegram Error] {e}")

def log_to_csv(row):
    """Append a row of pump event data to a CSV log file."""
    try:
        with open("pump_score_logs.csv", mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(row)
    except Exception as e:
        print(f"[CSV Logging Error] {e}")

# === ROUTES ===
@app.route("/helfire", methods=["POST"])
def helfire():
    """Handle incoming pump-score webhook events, supporting single or batched events."""
    try:
        payload = request.get_json()

        # Normalise incoming data to a list of events
        if isinstance(payload, list):
            events = payload
        else:
            events = [payload]

        for data in events:
            # Skip if data is not a dictionary
            if not isinstance(data, dict):
                continue

            token = data.get("token_address")
            score = data.get("pump_score")
            timestamp = data.get("timestamp") or datetime.utcnow().isoformat()

            # Validate token and score
            if not token or not isinstance(score, int):
                continue

            # Ignore scores below threshold
            if score < 7:
                continue

            # Skip if already alerted at an equal or higher score
            if token in alerted_tokens and alerted_tokens[token] >= score:
                continue

            # Look up token name and send alert
            token_name = get_token_name(token)
            send_telegram_alert(token, token_name, score)

            # Track and log
            alerted_tokens[token] = score
            log_to_csv([token, token_name, score, timestamp])
            print(f"[Webhook] {token} ({token_name}) → Score {score} at {timestamp}")

        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def index():
    return "Pump Sniper Bot is live."

# === START ===
if __name__ == "__main__":
    app.run(debug=True)
