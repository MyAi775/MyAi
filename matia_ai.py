from flask import Flask, request

app = Flask(__name__)

import os

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "matia_ai_2026")


@app.route("/", methods=["GET"])
def home():
    return "MATIA AI IS ONLINE 🤖🔥", 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def receive_webhook():
    data = request.get_json(silent=True)

    print("=== WHATSAPP WEBHOOK ===")
    print(data)
    print("========================")

    return "EVENT_RECEIVED", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
