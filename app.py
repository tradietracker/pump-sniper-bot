import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime, timezone
import requests

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")

CSV_LOG_FILE = "webhook_fallback.csv"
app_started_flag = {"has_run": False}


def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[⚠️ Telegram] Missing TELEGRAM config.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print("[✅ Telegram Sent]")
        else:
            print(f"[❌ Telegram Error] {response.text}")
    except Exception as e:
        print(f"[❌ Telegram Exception] {e}")


def log_to_csv(payload):
    try:
        with open(CSV_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for tx in payload if isinstance(payload, list) else [payload]:
                writer.writerow([
                    tx.get("description", ""),
                    tx.get("events", {}).get("amount", ""),
                    tx.get("type", ""),
                    tx.get("source", ""),
                    tx.get("fee", ""),
                    tx.get("slot", ""),
                    tx.get("timestamp", "")
                ])
        print("[💾 CSV Logged]")
    except Exception as e:
        print(f"[⚠️ CSV Log Error] {e}")


def forward_to_axiom(payload):
    if not AXIOM_INGEST_URL or not AXIOM_API_KEY:
        print("[⚠️ Axiom] Missing ingest URL or API key.")
        return
    try:
        headers = {
            "Authorization": f"Bearer {AXIOM_API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.post(AXIOM_INGEST_URL, headers=headers, json=payload)
        print(f"[✅ Forwarded to Axiom] {response.status_code}")
    except Exception as e:
        print(f"[❌ Axiom Error] {e}")


@app.route("/")
def home():
    return "Pump Sniper Bot is Live!"


@app.route("/helfire", methods=["POST"])
def helfire():
    print("[🔥 Webhook Received]")
    payload = request.get_json(force=True)
    forward_to_axiom(payload)
    log_to_csv(payload)
    return jsonify({"status": "ok"})


@app.route("/test-alert")
def test_alert():
    send_telegram_message("✅ Manual test alert from Pump Sniper Bot (via /test-alert)")
    return jsonify({"sent": True})


@app.before_request
def startup_once():
    if not app_started_flag["has_run"]:
        app_started_flag["has_run"] = True
        print("🚀 Pump Sniper Bot just went live on Render")
        send_telegram_message("🚀 Pump Sniper Bot just went *live* on Render")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

