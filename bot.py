import os
import telebot
from flask import Flask, request

TOKEN = os.environ.get("TOKEN") or "8439264693:AAEE7Zq-4uxAfK70Vop27Ff8zt5nfOkRPQA"  # подставь свой токен или используй переменные
APP_URL = os.environ.get("APP_URL") or "https://tablytsabot.onrender.com"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

print("✅ Бот инициализирован")

# Обработка команды /start
@bot.message_handler(commands=['start'])
def start_message(message):
    print("🚀 Получена команда /start")
    bot.send_message(message.chat.id, "Привет! Введите ваше имя:")

# Flask endpoint для Telegram webhook
@app.route(f"/{TOKEN}", methods=['POST'])
def telegram_webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

# Установка вебхука при старте
@app.before_first_request
def setup_webhook():
    print("⚙️ Устанавливаем webhook...")
    bot.remove_webhook()
    success = bot.set_webhook(url=f"{APP_URL}/{TOKEN}")
    print(f"✅ Webhook установлен: {success}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 10000)))
