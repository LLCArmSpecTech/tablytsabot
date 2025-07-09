
from telebot import TeleBot, types
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from datetime import datetime
import time

# === Настройки ===
TOKEN = "7749097735:AAEnCHA_fXAXZeFf_mER9b_u4enEqYzQLTg"
SPREADSHEET_NAME = "Таблица маршрутная"
bot = TeleBot(TOKEN)
user_sessions = {}

# === Подключение к Google Таблице ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import json
import os
creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)

def get_machine_list():
    try:
        sheet = spreadsheet.worksheet("Машины")
        return sheet.col_values(1)[1:]  # Первый столбец, со 2-й строки
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
    bot.send_message(chat_id, "Введите показатель одометра:")
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


    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("⛽ Заправка", "🏁 Конец маршрута")
    bot.send_message(chat_id, "Маршрут сохранён. Выберите действие:", reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text == "⛽ Заправка")
def refuel_odometer(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите показатель одометра перед заправкой:")
    bot.register_next_step_handler(message, save_refuel_odometer)

def save_refuel_odometer(message):
    chat_id = message.chat.id
    user_sessions[chat_id]["refuel_odometer"] = message.text.strip()

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🔙 Вернуться в предыдущее меню")
    bot.send_message(chat_id, "Введите количество литров:", reply_markup=keyboard)
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

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("⛽ Заправка", "🏁 Конец маршрута")
    bot.send_message(chat_id, "Заправка сохранена. Выберите действие:", reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text == "🏁 Конец маршрута")
def end_route(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите показатель одометра в конце маршрута:")
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

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🚛 Начать маршрут")
    bot.send_message(chat_id, "Маршрут завершён. Выберите следующее действие:", reply_markup=keyboard)

# === Запуск ===
from flask import Flask, request

app = Flask(__name__)

@app.route('/', methods=['POST'])
def webhook():
    update = types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200

@app.route('/', methods=['GET'])
def index():
    return "Bot is running!", 200

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url="https://tablytsabot.onrender.com")
    app.run(host="0.0.0.0", port=10000)
