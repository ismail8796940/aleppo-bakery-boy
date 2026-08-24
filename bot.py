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

    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json=payload,
            timeout=20
        )
        print("Telegram send status:", response.status_code)
    except Exception as error:
        print("Telegram send error:", repr(error))


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

        print("Apps Script status:", response.status_code)

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
        "أهلاً بك في نظام إدارة الأفران\n\nيرجى تسجيل الدخول للمتابعة.",
        [["تسجيل الدخول"]]
    )


def show_main_menu(chat_id, user):
    full_name = str(user.get("fullName", ""))
    role = str(user.get("role", "")).strip().upper()
    role_name = role_arabic(role)
    bakery_id = str(user.get("bakeryId", "")).strip()

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

    send_message(chat_id, text, keyboard)


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
    try:
        update = request.get_json(silent=True)

        if not update:
            return "OK", 200

        message = update.get("message")

        if not message:
            return "OK", 200

        chat_id = str(message.get("chat", {}).get("id", "")).strip()
        text = str(message.get("text", "")).strip()

        if not chat_id or not text:
            return "OK", 200

        if text == "/start":
            login_state.pop(chat_id, None)
            pending_username.pop(chat_id, None)
            logged_users.pop(chat_id, None)

            show_welcome(chat_id)
            return "OK", 200

        if text == "تسجيل الدخول":
            login_state[chat_id] = "WAITING_USERNAME"
            pending_username.pop(chat_id, None)

            send_message(
                chat_id,
                "أدخل اسم المستخدم:",
                remove_keyboard=True
            )
            return "OK", 200

        if text == "تسجيل الخروج":
            login_state.pop(chat_id, None)
            pending_username.pop(chat_id, None)
            logged_users.pop(chat_id, None)

            show_welcome(chat_id)
            return "OK", 200

        state = login_state.get(chat_id)

        if state == "WAITING_USERNAME":
            user = get_user_by_username(text)

            if not user:
                send_message(
                    chat_id,
                    "اسم المستخدم غير موجود.\nأدخل اسم المستخدم من جديد:"
                )
                return "OK", 200

            status = str(user.get("status", "")).strip().upper()

            if status != "ACTIVE":
                login_state.pop(chat_id, None)
                pending_username.pop(chat_id, None)

                send_message(
                    chat_id,
                    "هذا الحساب غير فعال. يرجى مراجعة إدارة النظام."
                )
                return "OK", 200

            pending_username[chat_id] = user.get("username")
            login_state[chat_id] = "WAITING_PASSWORD"

            send_message(
                chat_id,
                "أدخل كلمة المرور:"
            )
            return "OK", 200

        if state == "WAITING_PASSWORD":
            username = pending_username.get(chat_id)

            if not username:
                login_state.pop(chat_id, None)
                pending_username.pop(chat_id, None)

                show_welcome(chat_id)
                return "OK", 200

            user = get_user_by_username(username)

            if not user:
                login_state.pop(chat_id, None)
                pending_username.pop(chat_id, None)

                show_welcome(chat_id)
                return "OK", 200

            entered_hash = hash_password(text)
            stored_hash = str(user.get("passwordHash", "")).strip()

            if entered_hash != stored_hash:
                send_message(
                    chat_id,
                    "كلمة المرور غير صحيحة.\nأدخل كلمة المرور من جديد:"
                )
                return "OK", 200

            logged_users[chat_id] = user
            login_state.pop(chat_id, None)
            pending_username.pop(chat_id, None)

            show_main_menu(chat_id, user)
            return "OK", 200

        user = logged_users.get(chat_id)

        if not user:
            show_welcome(chat_id)
            return "OK", 200

        if text == "القائمة الرئيسية":
            show_main_menu(chat_id, user)
            return "OK", 200

        if text == "إدارة المستخدمين":
            role = str(user.get("role", "")).strip().upper()

            if role != "CREATOR":
                send_message(
                    chat_id,
                    "ليس لديك صلاحية لإدارة المستخدمين."
                )
                return "OK", 200

            show_users_menu(chat_id)
            return "OK", 200

        if text == "إضافة مستخدم":
            send_message(
                chat_id,
                "وظيفة إضافة مستخدم ستتم برمجتها في الخطوة التالية."
            )
            return "OK", 200

        if text == "عرض المستخدمين":
            send_message(
                chat_id,
                "وظيفة عرض المستخدمين ستتم برمجتها في الخطوة التالية."
            )
            return "OK", 200

        if text == "تفعيل/تعطيل مستخدم":
            send_message(
                chat_id,
                "وظيفة تفعيل وتعطيل المستخدم ستتم برمجتها في الخطوة التالية."
            )
            return "OK", 200

        if text == "إدارة الأفران":
            send_message(chat_id, "إدارة الأفران قيد الإعداد.")
            return "OK", 200

        if text == "الحسميات":
            send_message(chat_id, "نظام الحسميات قيد الإعداد.")
            return "OK", 200

        if text == "الأعطال":
            send_message(chat_id, "نظام الأعطال قيد الإعداد.")
            return "OK", 200

        if text == "التقارير":
            send_message(chat_id, "نظام التقارير قيد الإعداد.")
            return "OK", 200

        if text == "إعدادات النظام":
            send_message(chat_id, "إعدادات النظام قيد الإعداد.")
            return "OK", 200

        if text == "مسح البيانات":
            send_message(
                chat_id,
                "مسح البيانات غير مفعّل بعد وسيتم حمايته بتأكيد مزدوج."
            )
            return "OK", 200

        send_message(chat_id, "هذا الخيار غير مضاف بعد.")
        return "OK", 200

    except Exception as error:
        print("WEBHOOK ERROR:", repr(error))
        return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
