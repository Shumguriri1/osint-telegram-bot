import os
import logging
import ipaddress
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    "Stack Overflow": "https://stackoverflow.com/users/{u}",
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
        "Команды:\n"
        "/search username\n"
        "/search example.com\n"
        "/search 8.8.8.8\n"
        "/search https://example.com",
        reply_markup=main_menu(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "username":
        await query.message.reply_text(
            "👤 Username\n\n"
            "Пример:\n"
            "/search octocat"
        )

    elif query.data == "domain":
        await query.message.reply_text(
            "🌐 Domain\n\n"
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
            "Бот проверяет только публичные источники.\n\n"
            "⚠️ Совпадение username не доказывает,\n"
            "что аккаунты принадлежат одному человеку."
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
            return {
                "name": name,
                "url": url,
                "status": "found",
            }

        if status == 404:
            return {
                "name": name,
                "url": url,
                "status": "not_found",
            }

        if status in (401, 403, 429):
            return {
                "name": name,
                "url": url,
                "status": "blocked",
                "code": status,
            }

        if 300 <= status < 400:
            return {
                "name": name,
                "url": url,
                "status": "blocked",
                "code": status,
            }

        return {
            "name": name,
            "url": url,
            "status": "unknown",
            "code": status,
        }

    except requests.RequestException:
        return {
            "name": name,
            "url": url,
            "status": "error",
        }


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

    found = [
        r for r in results
        if r["status"] == "found"
    ]

    not_found = [
        r for r in results
        if r["status"] == "not_found"
    ]

    blocked = [
        r for r in results
        if r["status"] in ("blocked", "error", "unknown")
    ]

    found.sort(key=lambda x: x["name"])
    not_found.sort(key=lambda x: x["name"])
    blocked.sort(key=lambda x: x["name"])

    text = (
        "👤 USERNAME SEARCH\n\n"
        f"Username: @{username}\n\n"
        f"📊 Проверено: {len(results)}\n"
        f"✅ Найдено: {len(found)}\n"
        f"❌ Не найдено: {len(not_found)}\n"
        f"⚠️ Не удалось проверить: {len(blocked)}\n\n"
    )

    if found:
        text += "✅ НАЙДЕНО\n\n"

        for r in found:
            text += (
                f"• {r['name']}\n"
                f"{r['url']}\n\n"
            )

    if blocked:
        text += "⚠️ НЕ ПОДТВЕРЖДЕНО\n\n"

        for r in blocked:
            code = r.get("code")

            if code:
                text += (
                    f"• {r['name']} — HTTP {code}\n"
                )
            else:
                text += (
                    f"• {r['name']} — ошибка проверки\n"
                )

        text += "\n"

    text += (
        "⚠️ Важно:\n"
        "наличие одинакового username на разных "
        "сайтах не подтверждает принадлежность "
        "аккаунтов одному человеку."
    )

    if len(text) > 4000:
        text = text[:3900] + "\n..."

    await update.message.reply_text(text)


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


def is_domain(value):

    pattern = (
        r"^(?=.{1,253}$)"
        r"([a-zA-Z0-9]"
        r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
        r"[a-zA-Z]{2,}$"
    )

    return bool(re.match(pattern, value))


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

        if len(result) > 4000:
            result = result[:3900] + "\n..."

        await update.message.reply_text(result)

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
            f"Server: "
            f"{response.headers.get('Server', '—')}\n"
            f"Content-Type: "
            f"{response.headers.get('Content-Type', '—')}"
        )

        await update.message.reply_text(result)

    except Exception as error:

        logging.error(error)

        await update.message.reply_text(
            "❌ Не удалось проанализировать URL."
        )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
