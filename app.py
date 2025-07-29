import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime, timezone
import requests

app = Flask(__name__)

# === ENV CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6558366634")
AXIOM_DATASET = os.getenv("AXIOM_DATASET", "justamemecoin_trades")
AXIOM_TOKEN = os.getenv("AXIOM_TOKEN", "axiom_ingest_key_here")
AXIOM_URL = f"https://api.axiom.co/v1/datasets/{AXIOM_DATASET}/ingest"

# === TELEGRAM ALERT ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        res = requests.post(url, json=payload)
        print(f"Telegram response: {res.status_code} - {res.text}")
    except Exception as e:
        print("Telegram error:", e)

# === AXIOM FORWARDING ===
def forward_to_axiom(events):
    try:
        headers = {
            "Authorization": f"Bearer {AXIOM_TOKEN}",
            "Content-Type": "application/json"
        }
        response = requests.post(AXIOM_URL, headers=headers, json=events)
        print("[✅ Forwarded to Axiom]", response.status_code)
        return response.status_code == 200
    except Exception as e:
        print("Axiom error:", e)
        return False

# === CSV FALLBACK ===
def save_to_csv(events):
    filename = "fallback_events.csv"
    try:
        with open(filename, mode="a", newline="") as file:
            writer = csv.writer(file)
            for event in events:
                writer.writerow([datetime.now(timezone.utc).isoformat(), str(event)])
        print("[📝 Logged to CSV fallback]")
    except Exception as e:
        print("CSV logging error:", e)

# === MAIN HELFIRE ENDPOINT ===
@app.route('/helfire', methods=['POST'])
def helfire():
    try:
        data = request.get_json()
        print("[🔥 Webhook Received]")

        # Handle both dict and list style payloads
        events = data if isinstance(data, list) else [data]

        # Forward to Axiom
        if not forward_to_axiom(events):
            save_to_csv(events)

        # Example scoring logic
        for event in events:
            pump_score = 7  # You’ll replace with real logic soon
            if pump_score >= 7:
                send_telegram_message(f"🚀 Pump Score {pump_score} detected for token!")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"error": str(e)}), 500

# === /whoami TEST ROUTE ===
@app.route('/whoami', methods=['POST'])
def whoami():
    data = request.get_json()
    print("[/whoami POST]", data)
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        username = data["message"]["from"].get("username", "no_username")
        return jsonify({
            "chat_id": chat_id,
            "username": username
        })
    return jsonify({"error": "Invalid data"})

# === FLASK START ===
if __name__ == '__main__':
    app.run(debug=True)
