
import os
import csv
from flask import Flask, request, jsonify
from datetime import datetime, timezone
import requests

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = "6558366634"
AXIOM_DATASET = "justamemecoin_trades"
PUMP_SCORE_THRESHOLD = 16
REMOVE_SCORE_THRESHOLD = 8

app = Flask(__name__)

# === HELPERS ===

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})

def fetch_helius_data(token_address):
    # Simulate fetching token info (you'll replace with real call)
    return {
        "top_holders_percent": 22,
        "dev_wallet_percent": 1.5,
        "sniper_percent": 4.8,
        "recovery_hours": 6,
        "buy_volume_5min": 5.2,
        "unique_buyers_5min": 6,
        "lp_percent_supply": 7.2,
        "mc_to_liquidity_ratio": 10.5,
        "holder_growth_30min": 12,
        "cpw_score": 2
    }

def calculate_pump_score(metrics):
    score = 0

    # Top 10 holders %
    score += 2 if 15 <= metrics['top_holders_percent'] <= 30 else 1 if 5 <= metrics['top_holders_percent'] < 15 else 0
    # Dev wallet %
    score += 2 if metrics['dev_wallet_percent'] <= 2 else 1 if metrics['dev_wallet_percent'] <= 5 else 0
    # Sniper wallet %
    score += 2 if metrics['sniper_percent'] <= 5 else 1 if metrics['sniper_percent'] <= 10 else 0
    # Recovery duration
    score += 2 if 2 <= metrics['recovery_hours'] <= 12 else 1 if 1 <= metrics['recovery_hours'] < 2 or 12 < metrics['recovery_hours'] <= 24 else 0
    # Buy spike
    buy_vol = metrics['buy_volume_5min']
    buyers = metrics['unique_buyers_5min']
    score += 4 if buy_vol >= 5 and buyers >= 5 else 2 if buy_vol >= 2 and buyers >= 3 else 0
    # LP % supply
    score += 2 if 5 <= metrics['lp_percent_supply'] <= 10 else 1 if 3 <= metrics['lp_percent_supply'] < 5 or 10 < metrics['lp_percent_supply'] <= 12 else 0
    # MC:LP ratio
    score += 2 if 8 <= metrics['mc_to_liquidity_ratio'] <= 14 else 1 if 5 <= metrics['mc_to_liquidity_ratio'] < 8 or 14 < metrics['mc_to_liquidity_ratio'] <= 20 else 0
    # Holder growth
    growth = metrics['holder_growth_30min']
    score += 4 if growth >= 10 else 2 if growth >= 5 else 0
    # CPW (Call Power Weight)
    score += 4 if metrics['cpw_score'] >= 2 else 2 if metrics['cpw_score'] == 1 else 0

    return min(score, 24)

# === ROUTES ===

@app.route('/helfire', methods=['POST'])
def webhook():
    data = request.json
    token_address = data.get("token_address")
    if not token_address:
        return jsonify({"error": "No token_address provided"}), 400

    metrics = fetch_helius_data(token_address)
    pump_score = calculate_pump_score(metrics)

    if pump_score >= PUMP_SCORE_THRESHOLD:
        message = f"🚀 *Pump Score {pump_score}/24 detected!*
Token: `{token_address}`"
        send_telegram_alert(message)
    elif pump_score <= REMOVE_SCORE_THRESHOLD:
        print(f"Token {token_address} dropped below removal threshold.")

    return jsonify({"status": "scored", "pump_score": pump_score})

@app.route('/')
def index():
    return "Pump Sniper Bot is live!", 200

# === MAIN ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
