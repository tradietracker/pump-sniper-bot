import os
import csv
import threading
from flask import Flask, request, jsonify
from datetime import datetime, timezone
import requests

app = Flask(__name__)

# === ENV CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === TRACKING STATE ===
tracked_tokens = {}  # { mint: {"score": float, "message_id": int} }

# === TELEGRAM FUNCTIONS ===
def send_telegram_alert(mint, symbol, score):
    text = (
        f"🚨 <b>PUMP DETECTED</b>: <code>{symbol}</code>\n"
        f"📈 <b>Score:</b> {score:.2f}/10\n"
        f"🧠 Recovery Mode: <code>Active</code>\n"
        f"🔁 <i>Live tracking initiated...</i>\n\n"
        f"<code>{mint}</code>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })
    message_id = resp.json().get("result", {}).get("message_id")
    return message_id

def update_telegram_gauge(mint, symbol, score, message_id):
    text = (
        f"📊 <b>LIVE PUMP SCORE</b>: <code>{symbol}</code>\n"
        f"💥 <b>Score:</b> {score:.2f}/10\n\n"
        f"<code>{mint}</code>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    })

def remove_token_gauge(mint):
    if mint in tracked_tokens:
        del tracked_tokens[mint]

# === PUMP SCORE LOGIC ===
def calculate_pump_score(data):
    score = 0
    try:
        side = data.get("side", "").lower()
        amount = data.get("amount", 0)
        source = data.get("source", "")
        wallet = data.get("wallet", "")

        if side == "buy":
            score += 3
        if amount >= 5_000_000:
            score += 2
        elif amount >= 1_000_000:
            score += 1
        if "raydium" in source.lower():
            score += 1
        # future: score += dev_wallet_check(wallet)
        # future: score += velocity_check(mint)

    except Exception as e:
        print("[Score Calc Error]", e)
    return score

# === CSV FALLBACK (PATCHED TO HANDLE LISTS) ===
def log_to_csv(data):
    now = datetime.now(timezone.utc).isoformat()

    # Wrap single dict into list
    events = data if isinstance(data, list) else [data]

    for event in events:
        try:
            row = {
                "timestamp": now,
                "mint": event.get("token", {}).get("mint"),
                "symbol": event.get("token", {}).get("symbol"),
                "side": event.get("side"),
                "amount": event.get("amount"),
                "score": calculate_pump_score(event)
            }

            with open("fallback_log.csv", "a", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if f.tell() == 0:
                    writer.writeheader()
                writer.writerow(row)
        except Exception as e:
            print("CSV logging error:", e)

# === LIVE GAUGE UPDATE ===
def handle_trade(data):
    events = data if isinstance(data, list) else [data]

    for event in events:
        mint = event.get("token", {}).get("mint")
        symbol = event.get("token", {}).get("symbol", "UNKNOWN")
        if not mint:
            continue

        score = calculate_pump_score(event)

        if score >= 7 and mint not in tracked_tokens:
            message_id = send_telegram_alert(mint, symbol, score)
            tracked_tokens[mint] = {"score": score, "message_id": message_id}
            print(f"[🔥 ALERT SENT] {symbol} Score: {score}")

        if mint in tracked_tokens:
            tracked_tokens[mint]["score"] = score
            msg_id = tracked_tokens[mint]["message_id"]
            update_telegram_gauge(mint, symbol, score, msg_id)
            print(f"[🔄 Gauge Updated] {symbol} Score: {score}")

            if score <= 3:
                print(f"[❌ Faded Out] {symbol}")
                remove_token_gauge(mint)

# === FLASK ROUTES ===
@app.route("/helfire", methods=["POST"])
def helfire():
    data = request.get_json()
    try:
        threading.Thread(target=handle_trade, args=(data,)).start()
        log_to_csv(data)
        return jsonify({"status": "ok"})
    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/ping", methods=["GET"])
def ping():
    return "Bot is running"

@app.route("/whoami", methods=["POST"])
def whoami():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        username = data["message"]["from"].get("username", "no_username")
        return jsonify({
            "chat_id": chat_id,
            "username": username
        })
    return jsonify({"error": "Invalid data"})

# === RUN LOCALLY ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
