from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

AXIOM_API_KEY = os.getenv("AXIOM_API_KEY")
AXIOM_INGEST_URL = os.getenv("AXIOM_INGEST_URL")

@app.route('/helfire', methods=['POST'])
def handle_helfire():
    data = request.get_json()
    print("[🔥 Webhook Received]")
    print(data)

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
    app.run(port=5000)
