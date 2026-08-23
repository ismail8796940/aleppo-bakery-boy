import os
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

processed_updates = set()


def send_message(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = {
            "keyboard": keyboard,
            "resize_keyboard": True
        }

    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json=payload,
        timeout=15
    )


@app.route("/", methods=["GET"])
def home():
    return "Bakery Management Bot is running", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True)

    if not update:
        return "OK", 200

    update_id = update.get("update_id")

    if update_id in processed_updates:
        return "OK", 200

    processed_updates.add(update_id)

    if len(processed_updates) > 1000:
        processed_updates.clear()

    message = update.get("message")

    if not message:
        return "OK", 200

    chat_id = message["chat"]["id"]
    text = str(message.get("text", "")).strip()

    if text == "/start":
        send_message(
            chat_id,
            "أهلاً بك في نظام إدارة الأفران\n\nيرجى تسجيل الدخول للمتابعة.",
            [["تسجيل الدخول"]]
        )

    elif text == "تسجيل الدخول":
        send_message(
            chat_id,
            "أدخل اسم المستخدم:"
        )

    else:
        send_message(
            chat_id,
            "هذا الخيار غير متاح حالياً."
        )

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )
