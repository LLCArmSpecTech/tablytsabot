import os
import telebot
from flask import Flask, request

TOKEN = os.environ.get("TOKEN", "<УКАЖИ_СВОЙ_ТОКЕН>")
APP_URL = os.environ.get("APP_URL", "https://tablytsabot.onrender.com")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

print(f"✅ BOT ИНИЦИАЛИЗИРОВАН С TOKEN: {TOKEN[:10]}...")

@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    print("🚀 Обработка /start")  # лог в консоль
    bot.send_message(chat_id, "Привет! Введите ваше имя:")

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "It works!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{APP_URL}/{TOKEN}")
    print("✅ Вебхук установлен:", f"{APP_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))