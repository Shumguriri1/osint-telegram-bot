import os
import re
import ipaddress
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "OSINT Telegram Bot is running."


@web_app.route("/health")
def health():
    return "OK"


def run_web_server():
    web_app.run(
        host="0.0.0.0",
        port=PORT,
        use_reloader=False
    )


SITES = {
    "GitHub": "https://github.com/{u}",
    "GitLab": "https://gitlab.com/{u}",
    "Codeberg": "https://codeberg.org/{u}",
    "Bitbucket": "https://bitbucket.org/{u}",
    "Reddit": "https://www.reddit.com/user/{u}/",
    "X": "https://x.com/{u}",
    "Instagram": "https://www.instagram.com/{u}/",
    "TikTok": "https://www.tiktok.com/@{u}",
    "Threads": "https://www.threads.net/@{u}",
    "Facebook": "https://www.facebook.com/{u}",
    "LinkedIn": "https://www.linkedin.com/in/{u}/",
    "Telegram": "https://t.me/{u}",
    "VK": "https://vk.com/{u}",
    "Steam": "https://steamcommunity.com/id/{u}",
    "Twitch": "https://www.twitch.tv/{u}",
    "Roblox": "https://www.roblox.com/user.aspx?username={u}",
    "Pinterest": "https://www.pinterest.com/{u}/",
    "Tumblr": "https://{u}.tumblr.com/",
    "Medium": "https://medium.com/@{u}",
    "YouTube": "https://www.youtube.com/@{u}",
    "SoundCloud": "https://soundcloud.com/{u}",
    "Linktree": "https://linktr.ee/{u}",
    "Dev.to": "https://dev.to/{u}",
}


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
        "Поиск информации из открытых источников.\n\n"
        "Попробуй:\n"
        "/search 8.8.8.8\n"
        "/search example.com\n"
        "/search octocat\n"
        "/search https://example.com",
        reply_markup=main_menu(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    messages = {
        "username": "👤 Username\n\nПример:\n/search octocat",
        "domain": "🌐 Domain\n\nПример:\n/search example.com",
        "ip": "🌍 IP\n\nПример:\n/search 8.8.8.8",
        "url": "🔗 URL\n\nПример:\n/search https://example.com",
        "help": (
            "ℹ️ ПОМОЩЬ\n\n"
            "Бот проверяет только публичные источники.\n\n"
            "⚠️ Совпадение username не доказывает, "
            "что аккаунты принадлежат одному человеку."
        ),
    }

    await query.message.reply_text(
        messages.get(query.data, "Неизвестная команда.")
    )


def check_site(item):
    name, url = item

    try:
        response = requests.get(
            url,
            timeout=8,
            allow_redirects=False,
            headers={
                "User-Agent": "Mozilla/5.0 OSINT-Bot"
            },
        )

        status = response.status_code

        if status == 200:
            return name, url, "found", None

        if status == 404:
            return name, url, "not_found", None

        if status in (401, 403, 429):
            return name, url, "blocked", status

        if 300 <= status < 400:
            return name, url, "blocked", status

        return name, url, "unknown", status

    except requests.RequestException:
        return name, url, "error", None


async def username_search(update, username):
    username = username.lstrip("@").strip()

    if not re.match(r"^[a-zA-Z0-9._-]{2,64}$", username):
        await update.message.reply_text(
            "❌ Username содержит недопустимые символы."
        )
        return

    await update.message.reply_text(
        f"🔎 Проверяю @{username}\n\n"
        f"Сайтов: {len(SITES)}\n"
        "Подожди..."
    )

    items = [
        (name, url.format(u=username))
        for name, url in SITES.items()
    ]

    results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(check_site, item)
            for item in items
        ]

        for future in as_completed(futures):
            results.append(future.result())

    found = [r for r in results if r[2] == "found"]
    not_found = [r for r in results if r[2] == "not_found"]
    problems = [
        r for r in results
        if r[2] in ("blocked", "error", "unknown")
    ]

    found.sort()
    not_found.sort()
    problems.sort()

    text = (
        "👤 USERNAME SEARCH\n\n"
        f"Username: @{username}\n\n"
        f"📊 Проверено: {len(results)}\n"
        f"✅ Найдено: {len(found)}\n"
        f"❌ Не найдено: {len(not_found)}\n"
        f"⚠️ Не удалось проверить: {len(problems)}\n\n"
    )

    if found:
        text += "✅ НАЙДЕНО\n\n"

        for name, url, _, _ in found:
            text += f"• {name}\n{url}\n\n"

    if problems:
        text += "⚠️ НЕ ПОДТВЕРЖДЕНО\n\n"

        for name, _, status, code in problems:
            if code:
                text += f"• {name} — HTTP {code}\n"
            else:
                text += f"• {name} — ошибка проверки\n"

        text += "\n"

    text += (
        "⚠️ Наличие одинакового username "
        "на разных сайтах не подтверждает "
        "принадлежность аккаунтов одному человеку."
    )

    await update.message.reply_text(text[:4000])


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

        await update.message.reply_text(result)

    except Exception as error:
        logging.error(error)
        await update.message.reply_text(
            "❌ Не удалось получить информацию об IP."
        )


async def domain_search(update, domain):
    domain = domain.lower().strip()

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

        await update.message.reply_text(result[:4000])

    except Exception as error:
        logging.error(error)
        await update.message.reply_text(
            "❌ Не удалось получить DNS-информацию."
        )


async def url_search(update, url):
    try:
        response = requests.get(
            url,
            timeout=10,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 OSINT-Bot"
            }
        )

        result = (
            "🔗 URL INFORMATION\n\n"
            f"URL: {url}\n"
            f"Final URL: {response.url}\n"
            f"Status: {response.status_code}\n"
            f"Server: {response.headers.get('Server', '—')}\n"
            f"Content-Type: "
            f"{response.headers.get('Content-Type', '—')}"
        )

        await update.message.reply_text(result)

    except Exception as error:
        logging.error(error)
        await update.message.reply_text(
            "❌ Не удалось проанализировать URL."
        )


def is_domain(value):
    pattern = (
        r"^(?=.{1,253}$)"
        r"([a-zA-Z0-9]"
        r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
        r"[a-zA-Z]{2,}$"
    )

    return bool(re.match(pattern, value))


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🔎 Пример:\n\n"
            "/search 8.8.8.8\n"
            "/search example.com\n"
            "/search octocat\n"
            "/search https://example.com"
        )
        return

    target = context.args[0].strip()

    await update.message.reply_text(
        f"🔎 Анализирую:\n{target}\n\n"
        "Подожди..."
    )

    try:
        ipaddress.ip_address(target)
        await ip_search(update, target)
        return
    except ValueError:
        pass

    if target.startswith("http://") or target.startswith("https://"):
        await url_search(update, target)
        return

    if is_domain(target):
        await domain_search(update, target)
        return

    await username_search(update, target)


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не установлен")

    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("search", search)
    )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    print("Bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
