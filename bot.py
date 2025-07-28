
from telebot import TeleBot, types
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from datetime import datetime
import time
import os
from flask import Flask, request
TOKEN = os.environ.get("TOKEN")
bot = TeleBot(TOKEN)

APP_URL = "https://tablytsabot.onrender.com"  # URL на Render
WEBHOOK_PATH = f"/{TOKEN}"  # безопасный путь

app = Flask(__name__)

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

# === Настройки ===
SPREADSHEET_NAME = "Таблица маршрутная"
user_sessions = {}

# === Подключение к Google Таблице ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)

def get_machine_list():
    try:
        sheet = spreadsheet.worksheet("Лист1")
        return sheet.col_values(10)[1:]
    except:
        return []

def ensure_machine_sheet(name):
    try:
        return spreadsheet.worksheet(name)
    except:
        ws = spreadsheet.add_worksheet(title=name, rows="100", cols="10")
        ws.append_row(["Дата и время", "Водитель", "Литры", "Одометр", "Расход (л/100 км)"])
        return ws

# === Команды ===
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите ваше имя:")
    bot.register_next_step_handler(message, save_name)

def save_name(message):
    chat_id = message.chat.id
    name = message.text.strip()
    user_sessions[chat_id] = {"name": name}
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🚛 Начать маршрут")
    bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text == "🚛 Начать маршрут")
def begin_route(message):
    chat_id = message.chat.id
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for m in get_machine_list():
        keyboard.add(m)
    bot.send_message(chat_id, "Выберите машину:", reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text in get_machine_list())
def choose_machine(message):
    chat_id = message.chat.id
    user_sessions[chat_id]["machine"] = message.text
    hide_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Введите показатель одометра:", reply_markup=hide_keyboard)
    bot.register_next_step_handler(message, save_odometer_start)

def save_odometer_start(message):
    chat_id = message.chat.id
    odometer = message.text.strip()
    now = datetime.now()
    user = user_sessions[chat_id]
    user["start_time"] = now.strftime("%H:%M:%S")
    user["date"] = now.strftime("%Y-%m-%d")
    user["odometer_start"] = odometer

    ws = spreadsheet.worksheet("Лист1")
    last_row = len(ws.col_values(1)) + 1
    ws.update(f"A{last_row}", [[
        user["date"],        # A — Дата
        user["name"],        # B — Водитель
        user["machine"],     # C — Машина
        user["start_time"],  # D — Время начала маршрута
        odometer,            # E — Начало маршрута (одометр)
        "",                  # F — Время конца маршрута
        "",                  # G — Конец маршрута (одометр)
        ""                   # H — Пробег (км)
    ]])


    hide_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Пожалуйста, отправьте фото спидометра.", reply_markup=hide_keyboard)
    user["waiting_for_photo"] = "start_odometer_photo"


@bot.message_handler(func=lambda msg: msg.text == "⛽ Заправка")
def refuel_odometer(message):
    chat_id = message.chat.id
    hide_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Введите показатель одометра перед заправкой:", reply_markup=hide_keyboard)
    bot.register_next_step_handler(message, save_refuel_odometer)

def save_refuel_odometer(message):
    chat_id = message.chat.id
    user = user_sessions[chat_id]
    user["refuel_odometer"] = message.text.strip()
    
    hide_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Введите количество литров заправки:", reply_markup=hide_keyboard)
    bot.register_next_step_handler(message, save_refuel_liters)

def save_refuel_liters(message):
    chat_id = message.chat.id
    user = user_sessions[chat_id]
    liters = message.text.strip()
    sheet = ensure_machine_sheet(user["machine"])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Получаем все строки листа конкретной машины
    rows = sheet.get_all_values()
    if len(rows) >= 2:  # Есть хотя бы одна предыдущая запись
        last_odometer = int(rows[-1][3])  # Предыдущий одометр
        current_odometer = int(user["refuel_odometer"])
        distance = current_odometer - last_odometer
        if distance > 0:
            consumption = round((float(liters) / distance) * 100, 2)
        else:
            consumption = "Ошибка"
    else:
        distance = ""
        consumption = ""

    # Добавляем строку с датой, водителем, литрами, одометром и расходом
    sheet.append_row([now, user["name"], liters, user["refuel_odometer"], str(consumption)])

    hide_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Пожалуйста, отправьте фото заправки.", reply_markup=hide_keyboard)
    user["waiting_for_photo"] = "refuel_photo"


@bot.message_handler(func=lambda msg: msg.text == "🏁 Конец маршрута")
def end_route(message):
    chat_id = message.chat.id
    hide_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Введите показатель одометра в конце маршрута:", reply_markup=hide_keyboard)
    bot.register_next_step_handler(message, save_odometer_end)

def save_odometer_end(message):
    chat_id = message.chat.id
    odometer_end = message.text.strip()
    user = user_sessions[chat_id]
    now = datetime.now()
    time_end = now.strftime("%H:%M:%S")
    mileage = int(odometer_end) - int(user["odometer_start"])

    ws = spreadsheet.worksheet("Лист1")
    records = ws.get_all_values()
    for i in range(len(records)-1, 0, -1):
        if records[i][0] == user["date"] and records[i][1] == user["name"] and records[i][2] == user["machine"]:
            ws.update(f"F{i+1}", [[time_end]])
            ws.update(f"G{i+1}", [[odometer_end]])
            ws.update(f"H{i+1}", [[str(mileage)]])
            break

    # Теперь просим фото и ждём
    hide_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Пожалуйста, отправьте фото одометра в конце маршрута.", reply_markup=hide_keyboard)
    user["waiting_for_photo"] = "end_odometer_photo"

@bot.message_handler(func=lambda msg: msg.text == "📦 Новая почта")
def nova_poshta_branch(message):
    chat_id = message.chat.id
    reply_markup = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "На каком отделении Вы находитесь?", reply_markup=reply_markup)
    user_sessions[chat_id]["state"] = "awaiting_branch"

@bot.message_handler(func=lambda msg: user_sessions.get(msg.chat.id, {}).get("state") == "awaiting_branch")
def save_branch_and_ask_action(message):
    chat_id = message.chat.id
    user = user_sessions[chat_id]
    user["branch"] = message.text.strip()
    user["state"] = "awaiting_nova_poshta_action"

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📥 Получение", "📤 Отправка", "❌ Нет почты")
    keyboard.add("🔙 Назад")

    bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text == "📥 Получение")
def nova_poshta_receive(message):
    chat_id = message.chat.id
    user = user_sessions.get(chat_id)
    if not user or user.get("state") != "awaiting_nova_poshta_action":
        return
    
    reply_markup = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Сколько посылок получено?", reply_markup=reply_markup)
    user["state"] = "awaiting_receive_count"

@bot.message_handler(func=lambda msg: user_sessions.get(msg.chat.id, {}).get("state") == "awaiting_receive_count")
def save_receive_count(message):
    chat_id = message.chat.id
    user = user_sessions[chat_id]
    user["receive_count"] = message.text.strip()
    user["state"] = "awaiting_receive_photo"
    user["waiting_for_photo"] = "nova_receive"

    reply_markup = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Пожалуйста, отправьте фото посылок.", reply_markup=reply_markup)

@bot.message_handler(func=lambda msg: msg.text == "📤 Отправка")
def nova_poshta_send(message):
    chat_id = message.chat.id
    user = user_sessions.get(chat_id)
    if not user or user.get("state") != "awaiting_nova_poshta_action":
        return

    reply_markup = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Сколько посылок отправлено?", reply_markup=reply_markup)
    user["state"] = "awaiting_send_count"

@bot.message_handler(func=lambda msg: user_sessions.get(msg.chat.id, {}).get("state") == "awaiting_send_count")
def save_send_count(message):
    chat_id = message.chat.id
    user = user_sessions[chat_id]
    user["send_count"] = message.text.strip()
    user["state"] = "awaiting_send_photo"
    user["waiting_for_photo"] = "nova_send"

    reply_markup = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Пожалуйста, отправьте фото посылок.", reply_markup=reply_markup)

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    chat_id = message.chat.id
    user = user_sessions.get(chat_id)
    if not user:
        bot.send_message(chat_id, "Сначала введите имя с помощью команды /start.")
        return

    if user.get("waiting_for_photo") == "start_odometer_photo":
        file_id = message.photo[-1].file_id
        group_chat_id = -1002734636283
        caption = f"📸 Фото одометра *в начале маршрута* от водителя {user['name']}"
        bot.send_photo(group_chat_id, file_id, caption=caption)

        user.pop("waiting_for_photo", None)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("⛽ Заправка", "🏁 Конец маршрута", "📦 Новая почта")
        bot.send_message(chat_id, "Маршрут сохранён. Выберите действие:", reply_markup=keyboard)
        return

    elif user.get("waiting_for_photo") == "end_odometer_photo":
        file_id = message.photo[-1].file_id
        group_chat_id = -1002734636283
        caption = f"📸 Фото одометра *в конце маршрута* от водителя {user['name']}"
        bot.send_photo(group_chat_id, file_id, caption=caption)

        user.pop("waiting_for_photo", None)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("🚛 Начать маршрут")
        bot.send_message(chat_id, "Маршрут завершён. Выберите следующее действие:", reply_markup=keyboard)
        return

    elif user.get("waiting_for_photo") == "refuel_photo":
        file_id = message.photo[-1].file_id
        group_chat_id = -1002734636283
        caption = f"⛽ Фото заправки от {user['name']} (машина: {user['machine']})"
        bot.send_photo(group_chat_id, file_id, caption=caption)

        user.pop("waiting_for_photo", None)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("⛽ Заправка", "🏁 Конец маршрута", "📦 Новая почта")
        bot.send_message(chat_id, "Заправка сохранена. Выберите действие:", reply_markup=keyboard)
        return

        return

    # === НОВА ПОШТА — ПОЛУЧЕНИЕ ===
    elif user.get("waiting_for_photo") == "nova_receive":
        file_id = message.photo[-1].file_id
        group_chat_id = -1002780836350
        caption = f"📦 Получение\n👤 Водитель: {user.get('name')}\n🏢 Отделение: {user.get('branch')}\n📦 Кол-во посылок: {user.get('receive_count')}"
        bot.send_photo(group_chat_id, file_id, caption=caption)

        user.pop("waiting_for_photo", None)
        user["state"] = None

        # Вернуться в меню маршрута
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("⛽ Заправка", "🏁 Конец маршрута", "📦 Новая почта")
        bot.send_message(chat_id, "Выберите следующее действие:", reply_markup=keyboard)

    # === НОВА ПОШТА — ОТПРАВКА ===
    elif user.get("waiting_for_photo") == "nova_send":
        file_id = message.photo[-1].file_id
        group_chat_id = -1002780836350
        caption = f"📤 Отправка\n👤 Водитель: {user.get('name')}\n🏢 Отделение: {user.get('branch')}\n📦 Кол-во посылок: {user.get('send_count')}"
        bot.send_photo(group_chat_id, file_id, caption=caption)

        user.pop("waiting_for_photo", None)
        user["state"] = None

        # Вернуться в меню маршрута
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("⛽ Заправка", "🏁 Конец маршрута", "📦 Новая почта")
        bot.send_message(chat_id, "Выберите следующее действие:", reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text == "❌ Нет почты")
def nova_poshta_cancel(message):
    chat_id = message.chat.id
    user = user_sessions.get(chat_id)

    if not user or user.get("state") != "awaiting_nova_poshta_action":
        return

    # Сообщение в группу
    group_chat_id = -1002780836350
    text = (
        f"❌ Почта *отсутствует*\n"
        f"👤 Водитель: {user.get('name')}\n"
        f"🏢 Отделение: {user.get('branch')}"
    )
    bot.send_message(group_chat_id, text, parse_mode="Markdown")

    # Очистка состояния
    user["state"] = None

    # Вернуться в меню маршрута
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("⛽ Заправка", "🏁 Конец маршрута", "📦 Новая почта")
    bot.send_message(chat_id, "Выберите следующее действие:", reply_markup=keyboard)

bot.remove_webhook()
bot.set_webhook(url=APP_URL + "/" + TOKEN)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

