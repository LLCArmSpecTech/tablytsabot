
import telebot
import time
import os
import json
from flask import Flask, request
from telebot import types as tb_types

TOKEN = os.getenv('BOT_TOKEN', 'ВАШ_ТОКЕН_ЗДЕСЬ')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
monitor_started = False

# Установка webhook
bot.remove_webhook()
time.sleep(1)
bot.set_webhook(url='https://tablytsabot.onrender.com')

# Обработка входящих POST-запросов от Telegram
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('Content-Type') != 'application/json':
        return 'Invalid content type', 403

    global monitor_started
    json_str = request.get_data().decode('UTF-8')
    print('📥 Получено обновление:', json_str)
    update = tb_types.Update.de_json(json_str)
    bot.process_new_updates([update])

    if not monitor_started:
        print("🔁 Webhook активирован")
        monitor_started = True

    return '', 200

# Обработка команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id, "Бот работает. Привет, {}!".format(message.from_user.first_name))

if __name__ == "__main__":
    app.run(debug=True)
    