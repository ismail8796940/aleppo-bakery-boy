import os
import hashlib
import requests

from flask import Flask, request


app = Flask(__name__)


BOT_TOKEN = os.environ.get("BOT_TOKEN")
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")
API_SECRET = os.environ.get("API_SECRET")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


login_state = {}
pending_username = {}
logged_users = {}


def send_message(chat_id, text, keyboard=None, remove_keyboard=False):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if remove_keyboard:
        payload["reply_markup"] = {
            "remove_keyboard": True
        }

    elif keyboard:
        payload["reply_markup"] = {
            "keyboard": keyboard,
            "resize_keyboard": True,
            "one_time_keyboard": False
        }

    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json=payload,
        timeout=20
    )


def get_user_by_username(username):
    try:
        response = requests.get(
            APPS_SCRIPT_URL,
            params={
                "secret": API_SECRET,
                "action": "getUserByUsername",
                "username": username
            },
            timeout=60
        )

        data = response.json()

        if not data.get("ok"):
            return None

        if not data.get("found"):
            return None

        return data.get("user")

    except Exception as error:
        print("Apps Script error:", repr(error))
        return None


def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def role_arabic(role):
    roles = {
        "CREATOR": "المنشئ",
        "SUPERVISOR": "المشرف",
        "TRADE_MANAGER": "مدير التجارة",
        "INSPECTOR": "المفتش",
        "DIWAN": "الديوان",
        "BAKERY": "صاحب الفرن",
        "ASSOCIATION": "الجمعية"
    }

    key = str(role or "").strip().upper()

    return roles.get(key, role)


def show_welcome(chat_id):
    send_message(
        chat_id,
        "أهلاً بك في نظام إدارة الأفران\n\n"
        "يرجى تسجيل الدخول للمتابعة.",
        [
            ["تسجيل الدخول"]
        ]
    )


def show_main_menu(chat_id, user):
    full_name = user.get("fullName", "")
    role = str(user.get("role", "")).strip().upper()
    role_name = role_arabic(role)
    bakery_id = user.get("bakeryId", "")

    text = (
        "تم تسجيل الدخول بنجاح\n\n"
        f"الاسم: {full_name}\n"
        f"الصلاحية: {role_name}"
    )

    if bakery_id:
        text += f"\nرقم الفرن: {bakery_id}"

    if role == "CREATOR":
        keyboard = [
            ["إدارة المستخدمين"],
            ["إدارة الأفران"],
            ["الحسميات", "الأعطال"],
            ["التقارير"],
            ["إعدادات النظام"],
            ["مسح البيانات"],
            ["تسجيل الخروج"]
        ]

    else:
        keyboard = [
            ["القائمة الرئيسية"],
            ["تسجيل الخروج"]
        ]

    send_message(
        chat_id,
        text,
        keyboard
    )


def show_users_menu(chat_id):
    send_message(
        chat_id,
        "إدارة المستخدمين",
        [
            ["إضافة مستخدم"],
            ["عرض المستخدمين"],
            ["تفعيل/تعطيل مستخدم"],
            ["القائمة الرئيسية"]
        ]
    )


@app.route("/", methods=["GET"])
def home():
    return "Bakery Management Bot is running", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True)

    if not update:
        return "OK", 200

    message = update.get("message")

    if not message:
        return "OK", 200

    chat_id = str(message["chat"]["id"])
    text = str(message.get("text", "")).strip()

    # البداية
    if text == "/start":
        login_state.pop(chat_id, None)
        pending_username.pop(chat_id, None)
        logged_users.pop(chat_id, None)

        show_welcome(chat_id)

        return "OK", 200

    # تسجيل الدخول
    if text == "تسجيل الدخول":
        login_state[chat_id] = "WAITING_USERNAME"
        pending_username.pop(chat_id, None)

        send_message(
            chat_id,
            "أدخل اسم المستخدم:",
            remove_keyboard=True
        )

        return "OK", 200
