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

