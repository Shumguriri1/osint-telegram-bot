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

# =========================
# SETTINGS
# =========================

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

# =========================
# RENDER WEB SERVER
# =========================

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "OSINT Search Bot is running."


@web_app.route("/health")
def health():
    return "OK"


def run_web():
    web_app.run(
        host="0.0.0.0",
        port=PORT,
        use_reloader=False,
    )


# =========================
# PUBLIC SOURCES
# =========================

SITES = {
    "GitHub": "https://github.com/{u}",
    "GitLab": "https://gitlab.com/{u}",
    "Codeberg": "https://codeberg.org/{u}",
    "Bitbucket": "https://bitbucket.org/{u}",
    "Reddit": "https://www.reddit.com/user/{u}/",
    "X": "https://x.com/{u}",
    "Instagram": "https://www.instagram.com/{u}/",
    "TikTok": "https://www.tiktok.com/@{u}",
    "Threads": "https://www.threads.com/@{u}",
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


# =========================
# MENU
# =========================

def menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "👤 Username",
                callback_data="username",
            ),
            InlineKeyboardButton(
                "🌐 Domain",
                callback_data="domain",
            ),
        ],
        [
            InlineKeyboardButton(
                "🌍 IP",
                callback_data="ip",
            ),
            InlineKeyboardButton(
                "🔗 URL",
                callback_data="url",
            ),
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔎 OSINT SEARCH v4\n\n"
        "Поиск информации из публичных источников.\n\n"
        "Команды:\n\n"
        "/search @username\n"
        "/search example.com\n"
        "/search 8.8.8.8\n"
        "/search https://example.com",
        reply_markup=menu(),
    )


# =========================
# BUTTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
            "ℹ️ HELP\n\n"
            "Бот работает только с публичной информацией.\n\n"
            "Он не получает приватные данные,\n"
            "не обходит авторизацию и не использует\n"
            "закрытые или слитые базы."
        )


# =========================
# CONTACT EXTRACTION
# =========================

def extract_public_contacts(html):

    emails = set()
    phones = set()

    # Удаляем JavaScript.
    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        html,
        flags=re.I | re.S,
    )

    # Удаляем CSS.
    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.I | re.S,
    )

    # Удаляем HTML.
    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    # =========================
    # EMAIL
    # =========================

    email_pattern = (
        r"\b[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )

    ignored_emails = {
        "example@example.com",
        "email@example.com",
        "test@test.com",
        "test@example.com",
        "user@example.com",
        "name@example.com",
        "admin@example.com",
        "info@example.com",
    }

    for email in re.findall(
        email_pattern,
        text,
        flags=re.I,
    ):

        email = email.lower().strip()

        if email not in ignored_emails:
            emails.add(email)

    # =========================
    # PHONE
    # =========================

    phone_pattern = (
        r"(?<![\d.])"
        r"(?:\+\d{1,3}[\s().-]*)?"
        r"(?:\d[\s().-]*){7,15}"
        r"(?![\d.])"
    )

    for match in re.findall(
        phone_pattern,
        text,
    ):

        phone = match.strip()

        digits = re.sub(
            r"\D",
            "",
            phone,
        )

        if not 8 <= len(digits) <= 15:
            continue

        # IP address.
        try:

            ipaddress.ip_address(
                phone.replace(" ", "")
            )

            continue

        except ValueError:

            pass

        # Координаты.
        if (
            "." in phone
            and "+" not in phone
            and "(" not in phone
            and "-" not in phone
        ):
            continue

        # Даты.
        if re.fullmatch(
            r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}",
            phone,
        ):
            continue

        # Технические числа.
        if re.fullmatch(
            r"\d{12,}",
            digits,
        ):
            continue

        # Номер должен иметь форматирование.
        if (
            "+" not in phone
            and not re.search(
                r"[\s().-]",
                phone,
            )
        ):
            continue

        if len(phone) > 25:
            continue

        phone = re.sub(
            r"\s+",
            " ",
            phone,
        ).strip()

        phones.add(phone)

    return (
        set(sorted(emails)[:10]),
        set(sorted(phones)[:10]),
    )


# =========================
# CHECK PROFILE
# =========================

def check_profile(item):

    name, url = item

    try:

        response = requests.get(
            url,
            timeout=4,
            allow_redirects=True,
            headers={
                "User-Agent":
                "Mozilla/5.0 "
                "(compatible; OSINTSearchBot/4.0)",
            },
        )

        if response.status_code != 200:

            return {
                "name": name,
                "url": url,
                "found": False,
                "blocked": response.status_code in (
                    401,
                    403,
                    429,
                ),
                "emails": set(),
                "phones": set(),
            }

        emails, phones = extract_public_contacts(
            response.text
        )

        return {
            "name": name,
            "url": response.url,
            "found": True,
            "blocked": False,
            "emails": emails,
            "phones": phones,
        }

    except Exception:

        return {
            "name": name,
            "url": url,
            "found": False,
            "blocked": False,
            "emails": set(),
            "phones": set(),
        }


# =========================
# USERNAME SEARCH
# =========================

async def username_search(
    update,
    username,
):

    username = (
        username
        .lstrip("@")
        .strip()
    )

    if not re.match(
        r"^[a-zA-Z0-9._-]{2,64}$",
        username,
    ):

        await update.message.reply_text(
            "❌ Некорректный username."
        )

        return

    message = await update.message.reply_text(
        f"🔎 OSINT-ПРОВЕРКА @{username}\n\n"
        f"Источников: {len(SITES)}\n"
        "⚡ Проверяю параллельно..."
    )

    items = [
        (
            name,
            url.format(u=username),
        )
        for name, url in SITES.items()
    ]

    results = []

    # Все проверки выполняются параллельно.
    with ThreadPoolExecutor(
        max_workers=21,
    ) as executor:

        futures = [
            executor.submit(
                check_profile,
                item,
            )
            for item in items
        ]

        for future in as_completed(
            futures
        ):

            results.append(
                future.result()
            )

    found = [
        result
        for result in results
        if result["found"]
    ]

    blocked = [
        result
        for result in results
        if result["blocked"]
    ]

    emails = set()
    phones = set()

    for result in found:

        emails.update(
            result["emails"]
        )

        phones.update(
            result["phones"]
        )

    # =========================
    # REPORT
    # =========================

    text = (
        "🔎 PUBLIC OSINT REPORT\n\n"
        f"👤 Username: @{username}\n\n"
        "📊 РЕЗУЛЬТАТ\n"
        f"Проверено: {len(results)}\n"
        f"Публичных страниц: {len(found)}\n"
        f"Ограничено: {len(blocked)}\n\n"
    )

    # Profiles.
    text += "🌐 ПРОФИЛИ\n\n"

    if found:

        for result in sorted(
            found,
            key=lambda x: x["name"],
        ):

            text += (
                f"✅ {result['name']}\n"
                f"{result['url']}\n\n"
            )

    else:

        text += (
            "Не найдено.\n\n"
        )

    # Emails.
    text += "📧 ПУБЛИЧНЫЕ EMAIL\n\n"

    if emails:

        for email in sorted(emails):

            text += (
                f"• {email}\n"
            )

    else:

        text += (
            "Не найдено на проверенных страницах.\n"
        )

    text += "\n"

    # Phones.
    text += "📞 ПУБЛИЧНЫЕ ТЕЛЕФОНЫ\n\n"

    if phones:

        for phone in sorted(phones):

            text += (
                f"• {phone}\n"
            )

    else:

        text += (
            "Не найдено на проверенных страницах.\n"
        )

    text += (
        "\n⚠️ ВАЖНО\n\n"
        "Результаты получены из публично "
        "доступных страниц. Совпадение "
        "username не подтверждает личность "
        "владельца аккаунта."
    )

    # Telegram limit.
    if len(text) > 4000:

        text = text[:3900]

        text += (
            "\n\n…результат сокращён."
        )

    try:

        await message.edit_text(
            text
        )

    except Exception:

        await update.message.reply_text(
            text
        )


# =========================
# DNS
# =========================

def dns_lookup(
    domain,
    record_type,
):

    response = requests.get(
        "https://cloudflare-dns.com/dns-query",
        params={
            "name": domain,
            "type": record_type,
        },
        headers={
            "Accept": "application/dns-json",
        },
        timeout=5,
    )

    response.raise_for_status()

    data = response.json()

    return [
        answer.get("data")
        for answer in data.get(
            "Answer",
            [],
        )
    ]


# =========================
# IP SEARCH
# =========================

async def ip_search(
    update,
    ip,
):

    try:

        response = requests.get(
            f"https://ipinfo.io/{ip}/json",
            timeout=8,
        )

        response.raise_for_status()

        data = response.json()

        text = (
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
            text
        )

    except Exception as error:

        logging.error(
            "IP error: %s",
            error,
        )

        await update.message.reply_text(
            "❌ Не удалось получить информацию об IP."
        )


# =========================
# DOMAIN
# =========================

def is_domain(value):

    pattern = (
        r"^(?=.{1,253}$)"
        r"([a-zA-Z0-9]"
        r"(?:[a-zA-Z0-9-]{0,61}"
        r"[a-zA-Z0-9])?\.)+"
        r"[a-zA-Z]{2,}$"
    )

    return bool(
        re.match(
            pattern,
            value,
        )
    )


async def domain_search(
    update,
    domain,
):

    domain = (
        domain
        .lower()
        .strip()
    )

    try:

        a = dns_lookup(
            domain,
            "A",
        )

        aaaa = dns_lookup(
            domain,
            "AAAA",
        )

        mx = dns_lookup(
            domain,
            "MX",
        )

        ns = dns_lookup(
            domain,
            "NS",
        )

        text = (
            "🌐 DOMAIN INFORMATION\n\n"
            f"Domain: {domain}\n\n"
            "🔹 A:\n"
            f"{chr(10).join(a) if a else '—'}\n\n"
            "🔹 AAAA:\n"
            f"{chr(10).join(aaaa) if aaaa else '—'}\n\n"
            "🔹 MX:\n"
            f"{chr(10).join(mx) if mx else '—'}\n\n"
            "🔹 NS:\n"
            f"{chr(10).join(ns) if ns else '—'}"
        )

        await update.message.reply_text(
            text[:4000]
        )

    except Exception as error:

        logging.error(
            "DNS error: %s",
            error,
        )

        await update.message.reply_text(
            "❌ Ошибка DNS-поиска."
        )


# =========================
# URL
# =========================

async def url_search(
    update,
    url,
):

    try:

        response = requests.get(
            url,
            timeout=8,
            allow_redirects=True,
            headers={
                "User-Agent":
                "Mozilla/5.0 "
                "(compatible; OSINTSearchBot/4.0)",
            },
        )

        emails, phones = (
            extract_public_contacts(
                response.text
            )
        )

        text = (
            "🔗 URL INFORMATION\n\n"
            f"URL: {url}\n"
            f"Final URL: {response.url}\n"
            f"Status: {response.status_code}\n"
            f"Server: "
            f"{response.headers.get('Server', '—')}\n\n"
            "📧 PUBLIC EMAIL\n"
            f"{chr(10).join(sorted(emails)) if emails else '—'}\n\n"
            "📞 PUBLIC PHONE\n"
            f"{chr(10).join(sorted(phones)) if phones else '—'}"
        )

        await update.message.reply_text(
            text[:4000]
        )

    except Exception as error:

        logging.error(
            "URL error: %s",
            error,
        )

        await update.message.reply_text(
            "❌ Ошибка анализа URL."
        )


# =========================
# SEARCH
# =========================

async def search(
    update,
    context,
):

    if not context.args:

        await update.message.reply_text(
            "🔎 Использование:\n\n"
            "/search @username\n"
            "/search example.com\n"
            "/search 8.8.8.8\n"
            "/search https://example.com"
        )

        return

    target = (
        context.args[0]
        .strip()
    )

    # IP.
    try:

        ipaddress.ip_address(
            target
        )

        await ip_search(
            update,
            target,
        )

        return

    except ValueError:

        pass

    # URL.
    if (
        target.startswith("http://")
        or target.startswith("https://")
    ):

        await url_search(
            update,
            target,
        )

        return

    # Domain.
    if is_domain(
        target
    ):

        await domain_search(
            update,
            target,
        )

        return

    # Username.
    await username_search(
        update,
        target,
    )


# =========================
# MAIN
# =========================

def main():

    if not TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не установлен."
        )

    # Web server for Render.
    threading.Thread(
        target=run_web,
        daemon=True,
    ).start()

    application = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "search",
            search,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            buttons,
        )
    )

    print(
        "OSINT Search Bot v4 started."
    )

    application.run_polling()


if __name__ == "__main__":

    main()
