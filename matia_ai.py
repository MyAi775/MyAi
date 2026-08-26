from flask import Flask, request
import os
import requests

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "matia_ai_2026")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")


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
    data = request.get_json(silent=True) or {}

    print("=== WHATSAPP WEBHOOK ===")
    print(data)
    print("========================")

    try:
        entry = data.get("entry", [])

        for item in entry:
            changes = item.get("changes", [])

            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])

                for message in messages:
                    from_number = message.get("from")
                    message_type = message.get("type")

                    if message_type == "text":
                        text_body = (
                            message.get("text", {})
                            .get("body", "")
                            .strip()
                        )

                        print(f"Message from {from_number}: {text_body}")

                        reply = (
                            f"🤖 Matia AI received your message:\n\n"
                            f"“{text_body}”\n\n"
                            f"Matia AI is online! 🔥"
                        )

                        send_whatsapp_message(from_number, reply)

    except Exception as e:
        print("Webhook processing error:", e)

    return "EVENT_RECEIVED", 200


def send_whatsapp_message(to_number, message_text):
    if not ACCESS_TOKEN:
        print("WHATSAPP_ACCESS_TOKEN is missing.")
        return

    if not PHONE_NUMBER_ID:
        print("PHONE_NUMBER_ID is missing.")
        return

    url = f"https://graph.facebook.com/vXX.X/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": message_text
        }
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=20
        )

        print("WhatsApp API status:", response.status_code)
        print("WhatsApp API response:", response.text)

    except requests.RequestException as e:
        print("WhatsApp API error:", e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
