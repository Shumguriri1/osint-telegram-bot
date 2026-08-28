import os
import re
import ipaddress
import logging

import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")


def dns_lookup(domain, record_type):
    response = requests.get(
        "https://cloudflare-dns.com/dns-query",
        params={
            "name": domain,
            "type": record_type,
        },
        headers={
            "Accept": "application/dns-json"
        },
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    return [
        answer.get("data")
        for answer in data.get("Answer", [])
    ]


def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("👤 Username", callback_data="username"),
            InlineKeyboardButton("🌐 Domain", callback_data="domain"),
        ],
        [
            InlineKeyboardButton("🌍 IP", callback_data="ip"),
            InlineKeyboardButton("🔗 URL", callback_data="url"),
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data="help"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔎 OSINT SEARCH\n\n"
        "Добро пожаловать!\n\n"
        "Я могу искать информацию из открытых источников.\n\n"
        "Выбери тип поиска:",
        reply_markup=main_menu(),
    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "username":
        await query.message.reply_text(
            "👤 Username\n\n"
            "Использование:\n"
            "/search username"
        )

    elif query.data == "domain":
        await query.message.reply_text(
            "🌐 Domain\n\n"
            "Использование:\n"
            "/search example.com"
        )

    elif query.data == "ip":
        await query.message.reply_text(
            "🌍 IP\n\n"
            "Использование:\n"
            "/search 8.8.8.8"
        )

    elif query.data == "url":
        await query.message.reply_text(
            "🔗 URL\n\n"
            "Использование:\n"
            "/search https://example.com"
        )

    elif query.data == "help":
        await query.message.reply_text(
            "ℹ️ ПОМОЩЬ\n\n"
            "Используй:\n\n"
            "/search 8.8.8.8\n"
            "/search example.com\n"
            "/search username\n\n"
            "Бот работает только с публичной информацией."
        )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "🔎 Что будем искать?\n\n"
            "Примеры:\n"
            "/search 8.8.8.8\n"
            "/search example.com\n"
            "/search octocat"
        )

        return

    target = context.args[0].strip()

    await update.message.reply_text(
        f"🔎 Анализирую:\n{target}\n\n"
        "Подожди немного..."
    )

    # Проверяем IP

    try:

        ipaddress.ip_address(target)

        await ip_search(
            update,
            target
        )

        return

    except ValueError:
        pass

    # Проверяем URL

    if target.startswith("http://") or target.startswith("https://"):

        await url_search(
            update,
            target
        )

        return

    # Проверяем домен

    if is_domain(target):

        await domain_search(
            update,
            target
        )

        return

    # Иначе считаем username

    await username_search(
        update,
        target
    )


def is_domain(value):

    pattern = r"^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"

    return bool(
        re.match(pattern, value)
    )


async def ip_search(update, ip):

    try:

        response = requests.get(
            f"https://ipinfo.io/{ip}/json",
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        result = (
            "🌍 IP INFORMATION\n\n"
            f"IP: {data.get('ip', '—')}\n"
            f"Hostname: {data.get('hostname', '—')}\n"
            f"Country: {data.get('country', '—')}\n"
            f"Region: {data.get('region', '—')}\n"
            f"City: {data.get('city', '—')}\n"
            f"Timezone: {data.get('timezone', '—')}\n"
            f"Organization: {data.get('org', '—')}\n"
            f"Location: {data.get('loc', '—')}"
        )

        await update.message.reply_text(
            result
        )

    except Exception as error:

        logging.error(error)

        await update.message.reply_text(
            "❌ Не удалось получить информацию об IP."
        )


async def domain_search(update, domain):

    domain = domain.lower()

    try:

        a = dns_lookup(domain, "A")
        aaaa = dns_lookup(domain, "AAAA")
        mx = dns_lookup(domain, "MX")
        ns = dns_lookup(domain, "NS")
        txt = dns_lookup(domain, "TXT")

        result = (
            "🌐 DOMAIN INFORMATION\n\n"
            f"Domain: {domain}\n\n"

            f"🔹 A:\n"
            f"{chr(10).join(a) if a else '—'}\n\n"

            f"🔹 AAAA:\n"
            f"{chr(10).join(aaaa) if aaaa else '—'}\n\n"

            f"🔹 MX:\n"
            f"{chr(10).join(mx) if mx else '—'}\n\n"

            f"🔹 NS:\n"
            f"{chr(10).join(ns) if ns else '—'}\n\n"

            f"🔹 TXT:\n"
            f"{chr(10).join(txt) if txt else '—'}"
        )

        if len(result) > 4000:

            result = result[:3900] + "\n..."

        await update.message.reply_text(
            result
        )

    except Exception as error:

        logging.error(error)

        await update.message.reply_text(
            "❌ Не удалось получить DNS-информацию."
        )


async def username_search(update, username):

    username = username.lstrip("@")

    sites = {

        "GitHub":
            f"https://github.com/{username}",

        "Reddit":
            f"https://www.reddit.com/user/{username}/",

        "GitLab":
            f"https://gitlab.com/{username}",

        "Codeberg":
            f"https://codeberg.org/{username}",

    }

    found = []

    for name, url in sites.items():

        try:

            response = requests.get(
                url,
                timeout=8,
                allow_redirects=True,
                headers={
                    "User-Agent":
                    "Mozilla/5.0 OSINT-Bot"
                }
            )

            if response.status_code == 200:

                found.append(
                    f"✅ {name}\n{url}"
                )

            elif response.status_code == 404:

                found.append(
                    f"❌ {name}"
                )

            else:

                found.append(
                    f"⚠️ {name}: "
                    f"HTTP {response.status_code}"
                )

        except requests.RequestException:

            found.append(
                f"⚠️ {name}: ошибка проверки"
            )

    result = (
        "👤 USERNAME SEARCH\n\n"
        f"Username: @{username}\n\n"
        + "\n\n".join(found)
        + "\n\n⚠️ Наличие страницы "
          "не подтверждает личность владельца."
    )

    await update.message.reply_text(
        result
    )


async def url_search(update, url):

    try:

        response = requests.get(
            url,
            timeout=10,
            allow_redirects=True,
            headers={
                "User-Agent":
                "Mozilla/5.0 OSINT-Bot"
            }
        )

        final_url = response.url

        result = (
            "🔗 URL INFORMATION\n\n"
            f"URL: {url}\n"
            f"Final URL: {final_url}\n"
            f"Status: {response.status_code}\n"
            f"Server: "
            f"{response.headers.get('Server', '—')}\n"
            f"Content-Type: "
            f"{response.headers.get('Content-Type', '—')}\n"
            f"Content-Length: "
            f"{response.headers.get('Content-Length', '—')}"
        )

        await update.message.reply_text(
            result
        )

    except Exception as error:

        logging.error(error)

        await update.message.reply_text(
            "❌ Не удалось проанализировать URL."
        )


def main():

    if not TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не установлен"
        )

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "search",
            search
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    print("Bot started")

    app.run_polling()


if __name__ == "__main__":

    main()
