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
user_creation_state = {}
new_user_data = {}


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

        data = response.json()

        if not data.get("ok"):
            return None

        if not data.get("found"):
            return None

        return data.get("user")

    except Exception as error:
        print("Apps Script get user error:", repr(error))
        return None


def add_user_to_sheet(user_data):
    try:
        response = requests.post(
            APPS_SCRIPT_URL,
            json={
                "secret": API_SECRET,
                "action": "addUser",
                "username": user_data.get("username"),
                "passwordHash": user_data.get("passwordHash"),
                "role": user_data.get("role"),
                "fullName": user_data.get("fullName"),
                "bakeryId": user_data.get("bakeryId", "")
            },
            timeout=60
        )

        return response.json()

    except Exception as error:
        print("Apps Script add user error:", repr(error))

        return {
            "ok": False,
            "error": "CONNECTION_ERROR"
        }


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


def role_from_arabic(text):
    roles = {
        "المنشئ": "CREATOR",
        "المشرف": "SUPERVISOR",
        "مدير التجارة": "TRADE_MANAGER",
        "المفتش": "INSPECTOR",
        "الديوان": "DIWAN",
        "صاحب الفرن": "BAKERY",
        "الجمعية": "ASSOCIATION"
    }

    return roles.get(
        str(text).strip()
    )


def show_welcome(chat_id):
    send_message(
        chat_id,
        "أهلاً بك في نظام إدارة الأفران\n\nيرجى تسجيل الدخول للمتابعة.",
        [
            ["تسجيل الدخول"]
        ]
    )


def show_main_menu(chat_id, user):
    full_name = str(
        user.get("fullName", "")
    )

    role = str(
        user.get("role", "")
    ).strip().upper()

    role_name = role_arabic(role)

    bakery_id = str(
        user.get("bakeryId", "")
    ).strip()

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


def cancel_user_creation(chat_id):
    user_creation_state.pop(
        chat_id,
        None
    )

    new_user_data.pop(
        chat_id,
        None
    )


def start_user_creation(chat_id):
    new_user_data[
        chat_id
    ] = {}

    user_creation_state[
        chat_id
    ] = "WAITING_FULL_NAME"

    send_message(
        chat_id,
        "أدخل الاسم الكامل للمستخدم:",
        [
            ["إلغاء"]
        ]
    )


def send_creation_confirmation(chat_id):
    data = new_user_data.get(
        chat_id,
        {}
    )

    text = (
        "تأكيد إضافة المستخدم\n\n"
        f"الاسم: {data.get('fullName', '')}\n"
        f"اسم المستخدم: {data.get('username', '')}\n"
        f"الصلاحية: {role_arabic(data.get('role', ''))}"
    )

    bakery_id = data.get(
        "bakeryId",
        ""
    )

    if bakery_id:
        text += f"\nرقم الفرن: {bakery_id}"

    send_message(
        chat_id,
        text,
        [
            ["تأكيد الإضافة"],
            ["إلغاء"]
        ]
    )


def continue_user_creation(chat_id, text):
    state = user_creation_state.get(
        chat_id
    )

    if text == "إلغاء":
        cancel_user_creation(
            chat_id
        )

        show_users_menu(
            chat_id
        )

        return True

    if state == "WAITING_FULL_NAME":
        new_user_data[
            chat_id
        ]["fullName"] = text

        user_creation_state[
            chat_id
        ] = "WAITING_NEW_USERNAME"

        send_message(
            chat_id,
            "أدخل اسم المستخدم الجديد:",
            [
                ["إلغاء"]
            ]
        )

        return True

    if state == "WAITING_NEW_USERNAME":
        existing = get_user_by_username(
            text
        )

        if existing:
            send_message(
                chat_id,
                "اسم المستخدم مستخدم مسبقاً.\nأدخل اسماً آخر:"
            )

            return True

        new_user_data[
            chat_id
        ]["username"] = text

        user_creation_state[
            chat_id
        ] = "WAITING_NEW_PASSWORD"

        send_message(
            chat_id,
            "أدخل كلمة المرور للمستخدم الجديد:",
            [
                ["إلغاء"]
            ]
        )

        return True

    if state == "WAITING_NEW_PASSWORD":
        if len(text) < 4:
            send_message(
                chat_id,
                "كلمة المرور يجب أن تكون 4 محارف على الأقل.\n"
                "أدخل كلمة مرور جديدة:"
            )

            return True

        new_user_data[
            chat_id
        ]["passwordHash"] = hash_password(
            text
        )

        user_creation_state[
            chat_id
        ] = "WAITING_ROLE"

        send_message(
            chat_id,
            "اختر صلاحية المستخدم:",
            [
                ["المشرف", "مدير التجارة"],
                ["المفتش", "الديوان"],
                ["صاحب الفرن", "الجمعية"],
                ["المنشئ"],
                ["إلغاء"]
            ]
        )

        return True

    if state == "WAITING_ROLE":
        selected_role = role_from_arabic(
            text
        )

        if not selected_role:
            send_message(
                chat_id,
                "اختر الصلاحية من الأزرار."
            )

            return True

        new_user_data[
            chat_id
        ]["role"] = selected_role

        if selected_role == "BAKERY":
            user_creation_state[
                chat_id
            ] = "WAITING_BAKERY_ID"

            send_message(
                chat_id,
                "أدخل رقم الفرن:",
                [
                    ["إلغاء"]
                ]
            )

            return True

        new_user_data[
            chat_id
        ]["bakeryId"] = ""

        user_creation_state[
            chat_id
        ] = "WAITING_CONFIRMATION"

        send_creation_confirmation(
            chat_id
        )

        return True

    if state == "WAITING_BAKERY_ID":
        new_user_data[
            chat_id
        ]["bakeryId"] = text

        user_creation_state[
            chat_id
        ] = "WAITING_CONFIRMATION"

        send_creation_confirmation(
            chat_id
        )

        return True

    if state == "WAITING_CONFIRMATION":
        if text != "تأكيد الإضافة":
            send_message(
                chat_id,
                "اختر تأكيد الإضافة أو إلغاء."
            )

            return True

        result = add_user_to_sheet(
            new_user_data.get(
                chat_id,
                {}
            )
        )

        if result.get("ok"):
            user_id = result.get(
                "userId",
                ""
            )

            cancel_user_creation(
                chat_id
            )

            send_message(
                chat_id,
                f"تمت إضافة المستخدم بنجاح.\nرقم المستخدم: {user_id}"
            )

            show_users_menu(
                chat_id
            )

            return True

        error = result.get(
            "error",
            "UNKNOWN_ERROR"
        )

        error_messages = {
            "USERNAME_EXISTS": "اسم المستخدم موجود مسبقاً.",
            "BAKERY_ID_REQUIRED": "رقم الفرن مطلوب.",
            "CONNECTION_ERROR": "تعذر الاتصال بقاعدة البيانات.",
            "MISSING_FIELDS": "هناك بيانات ناقصة.",
            "INVALID_ROLE": "الصلاحية غير صحيحة."
        }

        send_message(
            chat_id,
            "تعذر إضافة المستخدم.\n"
            + error_messages.get(
                error,
                f"الخطأ: {error}"
            )
        )

        return True

    return False


@app.route("/", methods=["GET"])
def home():
    return "Bakery Management Bot is running", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(
            silent=True
        )

        if not update:
            return "OK", 200

        message = update.get(
            "message"
        )

        if not message:
            return "OK", 200

        chat_id = str(
            message.get(
                "chat",
                {}
            ).get(
                "id",
                ""
            )
        ).strip()

        text = str(
            message.get(
                "text",
                ""
            )
        ).strip()

        if not chat_id or not text:
            return "OK", 200

        if text == "/start":
            login_state.pop(
                chat_id,
                None
            )

            pending_username.pop(
                chat_id,
                None
            )

            logged_users.pop(
                chat_id,
                None
            )

            cancel_user_creation(
                chat_id
            )

            show_welcome(
                chat_id
            )

            return "OK", 200

        if text == "تسجيل الدخول":
            login_state[
                chat_id
            ] = "WAITING_USERNAME"

            pending_username.pop(
                chat_id,
                None
            )

            send_message(
                chat_id,
                "أدخل اسم المستخدم:",
                remove_keyboard=True
            )

            return "OK", 200

        if text == "تسجيل الخروج":
            login_state.pop(
                chat_id,
                None
            )

            pending_username.pop(
                chat_id,
                None
            )

            logged_users.pop(
                chat_id,
                None
            )

            cancel_user_creation(
                chat_id
            )

            show_welcome(
                chat_id
            )

            return "OK", 200

        login_status = login_state.get(
            chat_id
        )

        if login_status == "WAITING_USERNAME":
            user = get_user_by_username(
                text
            )

            if not user:
                send_message(
                    chat_id,
                    "اسم المستخدم غير موجود.\n"
                    "أدخل اسم المستخدم من جديد:"
                )

                return "OK", 200

            status = str(
                user.get(
                    "status",
                    ""
                )
            ).strip().upper()

            if status != "ACTIVE":
                login_state.pop(
                    chat_id,
                    None
                )

                pending_username.pop(
                    chat_id,
                    None
                )

                send_message(
                    chat_id,
                    "هذا الحساب غير فعال. يرجى مراجعة إدارة النظام."
                )

                return "OK", 200

            pending_username[
                chat_id
            ] = user.get(
                "username"
            )

            login_state[
                chat_id
            ] = "WAITING_PASSWORD"

            send_message(
                chat_id,
                "أدخل كلمة المرور:"
            )

            return "OK", 200

        if login_status == "WAITING_PASSWORD":
            username = pending_username.get(
                chat_id
            )

            if not username:
                login_state.pop(
                    chat_id,
                    None
                )

                pending_username.pop(
                    chat_id,
                    None
                )

                show_welcome(
                    chat_id
                )

                return "OK", 200

            user = get_user_by_username(
                username
            )

            if not user:
                login_state.pop(
                    chat_id,
                    None
                )

                pending_username.pop(
                    chat_id,
                    None
                )

                show_welcome(
                    chat_id
                )

                return "OK", 200

            entered_hash = hash_password(
                text
            )

            stored_hash = str(
                user.get(
                    "passwordHash",
                    ""
                )
            ).strip()

            if entered_hash != stored_hash:
                send_message(
                    chat_id,
                    "كلمة المرور غير صحيحة.\n"
                    "أدخل كلمة المرور من جديد:"
                )

                return "OK", 200

            logged_users[
                chat_id
            ] = user

            login_state.pop(
                chat_id,
                None
            )

            pending_username.pop(
                chat_id,
                None
            )

            show_main_menu(
                chat_id,
                user
            )

            return "OK", 200

        user = logged_users.get(
            chat_id
        )

        if not user:
            show_welcome(
                chat_id
            )

            return "OK", 200

        if user_creation_state.get(
            chat_id
        ):
            handled = continue_user_creation(
                chat_id,
                text
            )

            if handled:
                return "OK", 200

        if text == "القائمة الرئيسية":
            cancel_user_creation(
                chat_id
            )

            show_main_menu(
                chat_id,
                user
            )

            return "OK", 200

        if text == "إدارة المستخدمين":
            role = str(
                user.get(
                    "role",
                    ""
                )
            ).strip().upper()

            if role != "CREATOR":
                send_message(
                    chat_id,
                    "ليس لديك صلاحية لإدارة المستخدمين."
                )

                return "OK", 200

            show_users_menu(
                chat_id
            )

            return "OK", 200

        if text == "إضافة مستخدم":
            role = str(
                user.get(
                    "role",
                    ""
                )
            ).strip().upper()

            if role != "CREATOR":
                send_message(
                    chat_id,
                    "ليس لديك صلاحية لإضافة مستخدم."
                )

                return "OK", 200

            start_user_creation(
                chat_id
            )

            return "OK", 200

        if text == "عرض المستخدمين":
            users = get_all_users()

            if not users:
                send_message(
                    chat_id,
                    "لا يوجد مستخدمون مسجلون."
                )
                return "OK", 200

            lines = ["المستخدمون المسجلون:\n"]

            for item in users:
                user_id = str(item.get("userId", ""))
                username = str(item.get("username", ""))
                full_name = str(item.get("fullName", ""))
                role = role_arabic(item.get("role", ""))
                status = str(item.get("status", "")).upper()

                status_ar = (
                    "فعال"
                    if status == "ACTIVE"
                    else "غير فعال"
                )

                lines.append(
                    f"{user_id} - {full_name}\n"
                    f"اسم المستخدم: {username}\n"
                    f"الصلاحية: {role}\n"
                    f"الحالة: {status_ar}\n"
                )

            send_message(
                chat_id,
                "\n".join(lines)
            )

            return "OK", 200

        if text == "إدارة الأفران":
            send_message(
                chat_id,
                "إدارة الأفران قيد الإعداد."
            )

            return "OK", 200

        if text == "الحسميات":
            send_message(
                chat_id,
                "نظام الحسميات قيد الإعداد."
            )

            return "OK", 200

        if text == "الأعطال":
            send_message(
                chat_id,
                "نظام الأعطال قيد الإعداد."
            )

            return "OK", 200

        if text == "التقارير":
            send_message(
                chat_id,
                "نظام التقارير قيد الإعداد."
            )

            return "OK", 200

        if text == "إعدادات النظام":
            send_message(
                chat_id,
                "إعدادات النظام قيد الإعداد."
            )

            return "OK", 200

        if text == "مسح البيانات":
            send_message(
                chat_id,
                "مسح البيانات غير مفعّل بعد وسيتم حمايته بتأكيد مزدوج."
            )

            return "OK", 200

        send_message(
            chat_id,
            "هذا الخيار غير مضاف بعد."
        )

        return "OK", 200

    except Exception as error:
        print(
            "WEBHOOK ERROR:",
            repr(error)
        )

        return "OK", 200


if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
