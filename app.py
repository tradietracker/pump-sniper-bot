import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime, timezone
import requests

app = Flask(__name__)

# === ENV CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")

# === STATE ===
alerted_tokens = set()
live_gauges = {}

# === CSV FALLBACK ===
CSV_FILE = "fallback_log.csv"
def log_to_csv(data):
    try:
        if isinstance(data, list):
            for item in data:
                with open(CSV_FILE, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=item.keys())
                    if f.tell() == 0:
                        writer.writeheader()
                    writer.writerow(item)
        elif isinstance(data, dict):
            with open(CSV_FILE, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=data.keys())
                if f.tell() == 0:
                    writer.writeheader()
                writer.writerow(data)
    except Exception as e:
        print("CSV logging error:", str(e))

# === TELEGRAM ===
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def edit_telegram(message_id, new_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

# === SCORING ===
def calculate_pump_score(event):
    try:
        buy_volume = float(event.get("buy_volume", 0))
        sell_volume = float(event.get("sell_volume", 0))
        lp = float(event.get("liquidity", 0))
        buys = int(event.get("buys", 0))
        sells = int(event.get("sells", 0))

        ratio = buy_volume / max(sell_volume, 1)
        velocity = buys - sells

        score = 0
        if ratio > 1.5: score += 2
        if buy_volume > 1000: score += 2
        if lp > 3000: score += 1
        if velocity > 3: score += 2
        if buys > 10: score += 1

        return round(score, 2)
    except Exception as e:
        print("Score error:", e)
        return 0

def format_alert(event, score):
    return f"""🚀 *Pump Alert Detected!*
*Token:* {event.get("token_name", "Unknown")}
*Score:* {score}
*Buys:* {event.get("buys")} | *Sells:* {event.get("sells")}
*Buy Volume:* ${event.get("buy_volume")}
*LP:* ${event.get("liquidity")}
*Mint:* `{event.get("mint")}`
"""

def format_gauge(event, score):
    return f"""📊 *Live Pump Score Tracker*
*Token:* {event.get("token_name", "Unknown")}
*Score:* {score}
*Buys:* {event.get("buys")} | *Sells:* {event.get("sells")}
*Buy Volume:* ${event.get("buy_volume")}
*LP:* ${event.get("liquidity")}
"""

# === ROUTES ===
@app.route('/helfire', methods=['POST'])
def helfire():
    data = request.get_json()
    print("[🔥 Webhook Received]")

    if not data:
        return jsonify({"error": "No data"}), 400

    try:
        if isinstance(data, list):
            events = data
        else:
            events = [data]

        for event in events:
            mint = event.get("mint")
            score = calculate_pump_score(event)

            # Alert once per token
            if mint not in alerted_tokens and score >= 7:
                message = format_alert(event, score)
                res = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
                )
                alerted_tokens.add(mint)

                # Start gauge
                msg_id = res.json().get("result", {}).get("message_id")
                if msg_id:
                    live_gauges[mint] = msg_id

            # Gauge live updates
            if mint in live_gauges:
                if score < 3:
                    # Stop tracking
                    del live_gauges[mint]
                else:
                    edit_telegram(live_gauges[mint], format_gauge(event, score))

        # Forward to Axiom
        try:
            axiom_res = requests.post(
                AXIOM_INGEST_URL,
                headers={"Authorization": f"Bearer {AXIOM_API_KEY}", "Content-Type": "application/json"},
                json=events
            )
            print("[✅ Forwarded to Axiom]", axiom_res.status_code)
        except Exception as e:
            log_to_csv(events)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("Processing error:", e)
        log_to_csv(data)
        return jsonify({"error": "processing error"}), 500

@app.route('/whoami', methods=['POST'])
def whoami():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        username = data["message"]["from"].get("username", "no_username")
        return jsonify({"chat_id": chat_id, "username": username})
    return jsonify({"error": "Invalid data"})
