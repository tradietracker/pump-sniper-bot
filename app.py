from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# ✅ Root homepage to avoid 404 errors
@app.route("/", methods=["GET"])
def home():
    return "✅ Pump Sniper Bot Webhook is live and ready!"

# ✅ Webhook handler
@app.route('/helfire', methods=['POST'])
def handle_helfire():
    data = request.get_json()
    print("[🔥 Webhook Received]")
    print(data)

    AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")
    AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

