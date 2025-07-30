import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime
import requests

# A simple Flask application that implements the Pump Sniper Bot webhook.
#
# This script exposes a `/helfire` route that accepts POST requests containing
# a token address and pump score. When the score meets or exceeds a certain
# threshold (7 by default), the bot will look up the human‑readable token name
# using the Helius API and send an alert to a configured Telegram chat.
# It also logs all triggered alerts to a CSV file for auditing.

app = Flask(__name__)

# === CONFIG ===
# NOTE: These values should be kept secret in production. For simplicity they
# are hard‑coded here, but you can pull them from environment variables as
# needed. TELEGRAM_CHAT_ID is set to the user's chat ID (6558366634) so that
# alerts are delivered directly.
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "6558366634"
HELIUS_API_KEY = "e61c01b8-8e60-4c29-8144-559953796a62"
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")

# === MEMORY ===
# Keep track of which tokens have been alerted and at what score to avoid
# spamming multiple messages for the same token if the score increases.
alerted_tokens = {}

# === HELPERS ===
def get_token_name(mint: str) -> str:
    """Lookup the on‑chain name for a given token mint address using Helius.

    If the lookup fails for any reason, return the mint address itself.
    """
    try:
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
        response = requests.post(url, json={"mintAccounts": [mint]}, timeout=5)
        response.raise_for_status()
        result = response.json()
        # Navigate through the nested structure to fetch the token name; use the
        # mint as a fallback if the name is missing.
        return result[0].get('onChainMetadata', {}).get('metadata', {}).get('name', mint)
    except Exception as e:
        print(f"[Token Lookup Error] {e}")
        return mint


def send_telegram_alert(token_address: str, token_name: str, pump_score: int) -> None:
    """Send a formatted pump alert message to the configured Telegram chat.

    The message includes a visual gauge of the pump score using colored blocks.
    """
    gauge_blocks = '🟩' * pump_score + '⬜️' * (10 - pump_score)
    message = f"""
🚀 *Pump Score {pump_score} detected!*

Token: `{token_address}`
Name: *{token_name}*
Pump Strength:
{gauge_blocks} ({pump_score}/10)
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


def log_to_csv(data: list) -> None:
    """Append a row of pump event data to a CSV file.

    This function ensures that each alert is recorded with the token, name,
    score, and timestamp for future analysis or auditing.
    """
    try:
        with open("pump_score_logs.csv", mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(data)
    except Exception as e:
        print(f"[CSV Logging Error] {e}")


# === ROUTES ===
@app.route("/helfire", methods=["POST"])
def helfire():
    """Webhook endpoint for receiving pump score events.

    Expects a JSON payload with `token_address` and `pump_score`. If the
    score is below the threshold (7) or if we've already alerted for this
    token at an equal or higher score, the request is ignored. Otherwise,
    fetch the token name, send a Telegram alert, and log the event.
    """
    try:
        data = request.get_json()
        token = data.get("token_address")
        score = data.get("pump_score")
        timestamp = data.get("timestamp") or datetime.utcnow().isoformat()

        # Validate input
        if not token or not isinstance(score, int):
            return jsonify({"status": "error", "message": "Invalid token or score"}), 400

        # Ignore scores below threshold
        if score < 7:
            return jsonify({"status": "ignored"})

        # Prevent sending repeated alerts for the same token at a lower or equal score
        if token in alerted_tokens and alerted_tokens[token] >= score:
            return jsonify({"status": "already alerted"})

        # Look up token name and send alert
        token_name = get_token_name(token)
        send_telegram_alert(token, token_name, score)

        # Update memory and log
        alerted_tokens[token] = score
        log_to_csv([token, token_name, score, timestamp])

        print(f"[Webhook] {token} ({token_name}) → Score {score} at {timestamp}")
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/")
def index():
    """Simple health check endpoint to confirm the bot is running."""
    return "Pump Sniper Bot is live."


# === START ===
if __name__ == "__main__":
    # Run the Flask development server. In production, use a WSGI server
    # like Gunicorn or uWSGI behind a process manager.
    app.run(debug=True)
