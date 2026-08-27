import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 OSINT SEARCH\n\n"
        "Добро пожаловать!\n\n"
        "Доступные команды:\n"
        "/username — поиск username\n"
        "/domain — информация о домене\n"
        "/ip — информация об IP\n\n"
        "Используй только информацию из открытых источников."
    )


async def username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пример:\n/username example")
        return

    name = context.args[0].lstrip("@")

    await update.message.reply_text(
        f"🔎 Username: @{name}\n\n"
        "Модуль поиска будет подключён следующим шагом."
    )


async def domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пример:\n/domain example.com")
        return

    domain_name = context.args[0]

    await update.message.reply_text(
        f"🌐 Домен: {domain_name}\n\n"
        "Анализ домена будет подключён следующим шагом."
    )


async def ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пример:\n/ip 8.8.8.8")
        return

    ip_address = context.args[0]

    await update.message.reply_text(
        f"🌍 IP: {ip_address}\n\n"
        "Анализ IP будет подключён следующим шагом."
    )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не установлен")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("username", username))
    app.add_handler(CommandHandler("domain", domain))
    app.add_handler(CommandHandler("ip", ip))

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
