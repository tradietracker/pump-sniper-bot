from flask import Flask, request, jsonify
import requests
import os
import csv
from datetime import datetime

app = Flask(__name__)

AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")
CSV_LOG_FILE = "webhook_fallback_log.csv"

@app.route("/", methods=["GET"])
def homepage():
    return "✅ Pump Sniper Bot Webhook is live", 200

@app.route('/helfire', methods=['POST'])
def handle_helfire():
    data = request.get_json()
    print("[🔥 Webhook Received]")
    print(data)

    # Always log to CSV as backup
    log_to_csv(data)

    # Try forwarding to Axiom
    if AXIOM_API_KEY and AXIOM_INGEST_URL:
        try:
            headers = {
                "Authorization": f"Bearer {AXIOM_API_KEY}",
                "Content-Type": "application/json"
            }
            resp = requests.post(AXIOM_INGEST_URL, headers=headers, json=data)
            print("[✅ Forwarded to Axiom]", resp.status_code)
        except Exception as e:
            print("[❌ Axiom Forward Error]", str(e))

    return jsonify({"status": "received"}), 200

def log_to_csv(data):
    try:
        file_exists = os.path.isfile(CSV_LOG_FILE)
        with open(CSV_LOG_FILE, mode='a', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=['timestamp', 'token', 'price', 'volume', 'source'])
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                'timestamp': datetime.utcnow().isoformat(),
                'token': data.get('token'),
                'price': data.get('price'),
                'volume': data.get('volume'),
                'source': data.get('source', 'unknown')
            })
            print("[📝 Logged to CSV]")
    except Exception as e:
        print("[⚠️ CSV Log Error]", str(e))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

