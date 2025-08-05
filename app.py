import os
from flask import Flask, request, jsonify
import requests

# === CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8002496896:AAHVVGnUTP_d7Gpz_7nS7L9kNNr9SgcJ__0"
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or "6558366634"
PUMP_SCORE_THRESHOLD = 16
REMOVE_SCORE_THRESHOLD = 8

app = Flask(__name__)

# In-memory store: token_address -> telegram message_id
alerted_tokens = {}

# === TELEGRAM ALERT ===
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True})
    if resp.status_code == 200:
        return resp.json()['result']['message_id']
    else:
        print(f"Telegram sendMessage error: {resp.text}")
        return None

def edit_telegram_message(message_id, new_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        print(f"Telegram editMessageText error: {resp.text}")

# === HELPER: Format large numbers ===
def human_format(num):
    try:
        num = float(num)
    except (ValueError, TypeError):
        return "N/A"
    magnitude = 0
    while abs(num) >= 1000 and magnitude < 4:
        magnitude += 1
        num /= 1000.0
    suffixes = ['', 'K', 'M', 'B', 'T']
    return f"${num:.2f}{suffixes[magnitude]}"

# === HELPER: Gradient color gauge bar ===
def create_gauge_bar(score, max_score=24, length=10):
    gradient_blocks = ["🟥", "🟥", "🟧", "🟧", "🟨", "🟨", "🟩", "🟩", "🟩", "🟩"]
    filled_blocks = int(round(score / max_score * length))
    bar = []

    for i in range(length):
        if i < filled_blocks:
            bar.append(gradient_blocks[i])
        else:
            bar.append("⬜️")
    return "".join(bar)

# === PUMP SCORE ENGINE ===
def calculate_pump_score(data):
    score = 0

    # 1. Top Holder %
    score += 2 if 15 <= data['top_holder_pct'] <= 30 else 1 if 10 <= data['top_holder_pct'] < 15 or 30 < data['top_holder_pct'] <= 35 else 0

    # 2. Dev Wallet %
    score += 2 if data['dev_wallet_pct'] <= 2 else 1 if data['dev_wallet_pct'] <= 5 else 0

    # 3. Sniper / Insider %
    score += 2 if data['sniper_pct'] <= 5 else 1 if data['sniper_pct'] <= 10 else 0

    # 4. Recovery Duration
    score += 2 if 2 <= data['recovery_duration_hrs'] <= 12 else 1 if 1 <= data['recovery_duration_hrs'] < 2 or 12 < data['recovery_duration_hrs'] <= 24 else 0

    # 5. Buy Spike (5min)
    net_volume = data['buy_volume'] - data['sell_volume']
    if net_volume >= 5 and data['unique_buyers'] >= 5:
        score += 4
    elif net_volume >= 2 and data['unique_buyers'] >= 3:
        score += 2

    # 6. LP %
    score += 2 if 5 <= data['lp_pct'] <= 10 else 1 if 3 <= data['lp_pct'] < 5 or 10 < data['lp_pct'] <= 12 else 0

    # 7. MC:LP Ratio
    score += 2 if 8 <= data['mc_to_liquidity_ratio'] <= 14 else 1 if 5 <= data['mc_to_liquidity_ratio'] < 8 or 14 < data['mc_to_liquidity_ratio'] <= 20 else 0

    # 8. Holder Growth
    score += 4 if data['holder_growth'] >= 10 else 2 if data['holder_growth'] >= 5 else 0

    # 9. CPW
    score += 4 if data['cpw_score'] >= 2 else 2 if data['cpw_score'] == 1 else 0

    return min(score, 24)

# === FORMAT ALERT with live gauge ===
def format_alert(data, score):
    market_cap_str = human_format(data['market_cap'])
    axiom_link = f"https://axiom.trade/meme/{data['token_address']}"
    gauge = create_gauge_bar(score)

    if score >= PUMP_SCORE_THRESHOLD:
        color = "🟢 *STRONG SIGNAL*"
    elif score >= 10:
        color = "🟡 *WARMING UP*"
    else:
        color = "🔴 *WEAK / FADING*"

    return f"""{color}
*Pump Score: {score}/24*

Token: `{data['token_name']}`
Market Cap: {market_cap_str}
[View Chart on Axiom](<{axiom_link}>)

Pump Strength:
{gauge} ({score}/24)

📈 Buy Volume: {data['buy_volume']} | Buyers: {data['unique_buyers']}
📉 Sell Volume: {data['sell_volume']} | Sellers: {data['unique_sellers']}

👑 Top Holder %: {data['top_holder_pct']}%
🧬 Dev Wallet %: {data['dev_wallet_pct']}%
🎯 Sniper %: {data['sniper_pct']}%
🧪 LP %: {data['lp_pct']}%
⚖️ MC/LP Ratio: {data['mc_to_liquidity_ratio']}
👥 Holder Growth: {data['holder_growth']}
📢 CPW Score: {data['cpw_score']}
⏳ Recovery Duration: {data['recovery_duration_hrs']}h
"""

# === WEBHOOK ===
@app.route('/helfire', methods=['POST'])
def helfire():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON received"}), 400

    required = [
        "token_address", "token_name", "market_cap",
        "buy_volume", "sell_volume", "unique_buyers", "unique_sellers",
        "top_holder_pct", "dev_wallet_pct", "sniper_pct",
        "lp_pct", "mc_to_liquidity_ratio", "holder_growth",
        "cpw_score", "recovery_duration_hrs"
    ]

    missing = [field for field in required if field not in data]
    if missing:
        return jsonify({
            "error": "Missing fields",
            "missing": missing,
            "received_keys": list(data.keys())
        }), 400

    score = calculate_pump_score(data)
    token_address = data['token_address']
    message_id = alerted_tokens.get(token_address)

    if score >= PUMP_SCORE_THRESHOLD:
        alert_text = format_alert(data, score)
        if message_id:
            edit_telegram_message(message_id, alert_text)
        else:
            message_id = send_telegram_alert(alert_text)
            if message_id:
                alerted_tokens[token_address] = message_id
    else:
        # If score below remove threshold, fade alert
        if message_id:
            faded_text = f"⚠️ *Alert faded* for `{data['token_name']}` (Pump Score dropped to {score}/24)"
            edit_telegram_message(message_id, faded_text)
            alerted_tokens.pop(token_address, None)

    return jsonify({"status": "scored", "pump_score": score}), 200

# === PING ===
@app.route('/')
def index():
    return "Pump Sniper Bot is live!", 200

# === MAIN ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
