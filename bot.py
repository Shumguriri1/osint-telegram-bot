import os
import re
import ipaddress
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

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
    "Pinterest": "https://www.pinterest.com/{u}/",
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
        "Поиск публичной информации.\n\n"
        "Примеры:\n"
        "/search 8.8.8.8\n"
        "/search example.com\n"
        "/search octocat\n"
        "/search https://example.com",
        reply_markup=main_menu(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data == "username":

        await query.message.reply_text(
            "👤 USERNAME\n\n"
            "Пример:\n"
            "/search octocat"
        )

    elif query.data == "domain":

        await query.message.reply_text(
            "🌐 DOMAIN\n\n"
            "Пример:\n"
            "/search example.com"
        )

    elif query.data == "ip":

        await query.message.reply_text(
            "🌍 IP\n\n"
            "Пример:\n"
            "/search 8.8.8.8"
        )

    elif query.data == "url":

        await query.message.reply_text(
            "🔗 URL\n\n"
            "Пример:\n"
            "/search https://example.com"
        )

    elif query.data == "help":

        await query.message.reply_text(
            "ℹ️ ПОМОЩЬ\n\n"
            "Бот работает с публичной информацией.\n\n"
            "Он не получает приватные данные "
            "и не использует закрытые базы.\n\n"
            "Совпадение username не означает, "
            "что аккаунты принадлежат одному человеку."
        )


def extract_contacts(html):

    emails = set()
    phones = set()
    links = set()

    # Email

    email_pattern = r"""
        [A-Za-z0-9._%+-]+
        @
        [A-Za-z0-9.-]+\.[A-Za-z]{2,}
    """

    for match in re.findall(
        email_pattern,
        html,
        re.VERBOSE
    ):

        emails.add(match.lower())

    # Телефонные номера.

    phone_pattern = r"""
        (?<!\d)
        (?:\+\d{1,3}[\s.-]?)?
        (?:\(?\d{2,4}\)?[\s.-]?)
        \d{2,4}[\s.-]
        \d{2,4}[\s.-]?
        \d{0,4}
        (?!\d)
    """

    for match in re.findall(
        phone_pattern,
        html,
        re.VERBOSE
    ):

        cleaned = re.sub(
            r"\s+",
            " ",
            match
        ).strip()

        digits = re.sub(
            r"\D",
            "",
            cleaned
        )

        if 7 <= len(digits) <= 15:

            phones.add(cleaned)

    # URL

    url_pattern = r'https?://[^\s"\'<>]+'

    for match in re.findall(
        url_pattern,
        html
    ):

        links.add(match.rstrip(").,;"))

    return emails, phones, links


def check_profile(item):

    name, url = item

    try:

        response = requests.get(
            url,
            timeout=8,
            allow_redirects=True,
            headers={
                "User-Agent":
                "Mozilla/5.0 (compatible; OSINTBot/1.0)"
            },
        )

        status = response.status_code

        if status != 200:

            return {
                "name": name,
                "url": url,
                "status": "blocked"
                if status in (401, 403, 429)
                else "not_found",
                "emails": set(),
                "phones": set(),
                "links": set(),
            }

        emails, phones, links = extract_contacts(
            response.text
        )

        return {
            "name": name,
            "url": response.url,
            "status": "found",
            "emails": emails,
            "phones": phones,
            "links": links,
        }

    except requests.RequestException:

        return {
            "name": name,
            "url": url,
            "status": "error",
            "emails": set(),
            "phones": set(),
            "links": set(),
        }


async def username_search(update, username):

    username = username.lstrip("@").strip()

    if not re.match(
        r"^[a-zA-Z0-9._-]{2,64}$",
        username
    ):

        await update.message.reply_text(
            "❌ Недопустимый username."
        )

        return

    await update.message.reply_text(
        f"🔎 Начинаю публичный OSINT-поиск\n\n"
        f"Username: @{username}\n\n"
        f"Проверяю {len(SITES)} источников..."
    )

    items = [
        (
            name,
            url.format(u=username)
        )
        for name, url in SITES.items()
    ]

    results = []

    with ThreadPoolExecutor(
        max_workers=10
    ) as executor:

        futures = [
            executor.submit(
                check_profile,
                item
            )
            for item in items
        ]

        for future in as_completed(futures):

            results.append(
                future.result()
            )

    found = [
        r for r in results
        if r["status"] == "found"
    ]

    blocked = [
        r for r in results
        if r["status"] in (
            "blocked",
            "error"
        )
    ]

    emails = set()
    phones = set()
    links = set()

    for result in found:

        emails.update(
            result["emails"]
        )

        phones.update(
            result["phones"]
        )

        links.update(
            result["links"]
        )

    text = (
        "🔎 PUBLIC OSINT REPORT\n\n"
        f"👤 Username: @{username}\n\n"
        "📊 РЕЗУЛЬТАТ\n"
        f"Проверено: {len(results)}\n"
        f"Публичных страниц: {len(found)}\n"
        f"Не удалось проверить: {len(blocked)}\n\n"
    )

    if found:

        text += "🌐 ПРОФИЛИ\n\n"

        for result in sorted(
            found,
            key=lambda x: x["name"]
        ):

            text += (
                f"✅ {result['name']}\n"
                f"{result['url']}\n\n"
            )

    if emails:

        text += "📧 ПУБЛИЧНЫЕ EMAIL\n\n"

        for email in sorted(emails):

            text += (
                f"• {email}\n"
            )

        text += "\n"

    if phones:

        text += "📞 ПУБЛИЧНЫЕ ТЕЛЕФОНЫ\n\n"

        for phone in sorted(phones):

            text += (
                f"• {phone}\n"
            )

        text += "\n"

    if links:

        # Оставляем только несколько уникальных
        # ссылок, чтобы Telegram-сообщение
        # не стало слишком большим.

        useful_links = []

        for link in sorted(links):

            if link not in useful_links:

                useful_links.append(link)

            if len(useful_links) >= 10:
                break

        text += "🔗 ССЫЛКИ\n\n"

        for link in useful_links:

            text += (
                f"• {link}\n"
            )

        text += "\n"

    if not emails:

        text += (
            "📧 Публичный email: не найден\n\n"
        )

    if not phones:

        text += (
            "📞 Публичный телефон: не найден\n\n"
        )

    text += (
        "⚠️ ВАЖНО\n\n"
        "Показанные контакты относятся только "
        "к публично доступному содержимому страниц. "
        "Совпадение username не подтверждает "
        "личность владельца аккаунта."
    )

    await update.message.reply_text(
        text[:4000]
    )


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

        await update.message.reply_text(
            result
        )

    except Exception as error:

        logging.error(error)

        await update.message.reply_text(
            "❌ Не удалось получить информацию об IP."
        )


def is_domain(value):

    pattern = (
        r"^(?=.{1,253}$)"
        r"([a-zA-Z0-9]"
        r"(?:[a-zA-Z0-9-]{0,61}"
        r"[a-zA-Z0-9])?\.)+"
        r"[a-zA-Z]{2,}$"
    )

    return bool(
        re.match(pattern, value)
    )


async def domain_search(update, domain):

    domain = domain.lower().strip()

    try:

        a = dns_lookup(domain, "A")
        aaaa = dns_lookup(domain, "AAAA")
        mx = dns_lookup(domain, "MX")
        ns = dns_lookup(domain, "NS")

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
            f"{chr(10).join(ns) if ns else '—'}"
        )

        await update.message.reply_text(
            result[:4000]
        )

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
                "User-Agent":
                "Mozilla/5.0 OSINT-Bot"
            }
        )

        emails, phones, links = extract_contacts(
            response.text
        )

        result = (
            "🔗 URL INFORMATION\n\n"
            f"URL: {url}\n"
            f"Final URL: {response.url}\n"
            f"Status: {response.status_code}\n"
            f"Server: "
            f"{response.headers.get('Server', '—')}\n"
            f"Content-Type: "
            f"{response.headers.get('Content-Type', '—')}\n\n"
            "📧 Public email:\n"
            f"{chr(10).join(sorted(emails)) if emails else '—'}\n\n"
            "📞 Public phone:\n"
            f"{chr(10).join(sorted(phones)) if phones else '—'}"
        )

        await update.message.reply_text(
            result[:4000]
        )

    except Exception as error:

        logging.error(error)

        await update.message.reply_text(
            "❌ Не удалось проанализировать URL."
        )


async def search(update, context):

    if not context.args:

        await update.message.reply_text(
            "🔎 Использование:\n\n"
            "/search 8.8.8.8\n"
            "/search example.com\n"
            "/search octocat\n"
            "/search https://example.com"
        )

        return

    target = context.args[0].strip()

    try:

        ipaddress.ip_address(target)

        await ip_search(
            update,
            target
        )

        return

    except ValueError:

        pass

    if (
        target.startswith("http://")
        or target.startswith("https://")
    ):

        await url_search(
            update,
            target
        )

        return

    if is_domain(target):

        await domain_search(
            update,
            target
        )

        return

    await username_search(
        update,
        target
    )


def main():

    if not TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не установлен"
        )

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
