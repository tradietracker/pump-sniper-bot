import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime, timezone
import requests

app = Flask(__name__)

# === ENV CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")
AXIOM_DATASET = "justamemecoin_trades"

# === TELEGRAM SEND ===
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Telegram alert sent")
        else:
            print("❌ Telegram error:", response.text)
    except Exception as e:
        print("❌ Telegram exception:", str(e))

# === CSV FALLBACK ===
def log_to_csv(event):
    try:
        filename = "fallback_events.csv"
        with open(filename, "a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=event.keys())
            if file.tell() == 0:
                writer.writeheader()
            writer.writerow(event)
        print("[📝 Logged to CSV fallback]")
    except Exception as e:
        print("CSV logging error:", e)

# === AXIOM FORWARD ===
def forward_to_axiom(events):
    url = f"https://api.axiom.co/v1/datasets/{AXIOM_DATASET}/ingest"
    headers = {
        "Authorization": f"Bearer {AXIOM_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=events, headers=headers)
        print(f"[✅ Forwarded to Axiom] {response.status_code}")
    except Exception as e:
        print("[❌ Axiom Error]", str(e))

# === ROUTES ===
@app.route("/helfire", methods=["POST"])
def webhook_handler():
    try:
        data = request.get_json()
        print("[🔥 Webhook Received]")

        # Handle list or single dict
        events = data if isinstance(data, list) else [data]

        # Forward to Axiom
        forward_to_axiom(events)

        # Fallback log
        for event in events:
            log_to_csv(event)

        # Telegram alert if score logic applies
        for event in events:
            if "pump_score" in event and event["pump_score"] >= 7:
                msg = f"🚨 Pump Score Alert\n\nToken: {event.get('token_name', 'Unknown')}\nScore: {event['pump_score']}"
                send_telegram_alert(msg)

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("❌ Exception in webhook:", str(e))
        return jsonify({"error": "Internal error"}), 500

@app.route("/whoami", methods=["POST"])
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

# === START ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
