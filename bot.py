import os
import logging
import ipaddress
import re

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")


def dns_lookup(domain, record_type):
    response = requests.get(
        "https://cloudflare-dns.com/dns-query",
        params={
            "name": domain,
            "type": record_type
        },
        headers={
            "Accept": "application/dns-json"
        },
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    return [
        answer.get("data")
        for answer in data.get("Answer", [])
    ]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 OSINT SEARCH\n\n"
        "Команды:\n\n"
        "/ip 8.8.8.8\n"
        "/domain example.com\n"
        "/username username\n\n"
        "Используются публичные источники."
    )


async def ip_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Пример:\n/ip 8.8.8.8"
        )
        return

    ip = context.args[0]

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный IP-адрес."
        )
        return

    await update.message.reply_text(
        "🔎 Ищу информацию об IP..."
    )

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


async def domain_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Пример:\n/domain example.com"
        )
        return

    domain = context.args[0].lower()

    domain = re.sub(
        r"^https?://",
        "",
        domain
    )

    domain = domain.split("/")[0]

    await update.message.reply_text(
        f"🔎 Анализирую {domain}..."
    )

    try:
        a = dns_lookup(domain, "A")
        aaaa = dns_lookup(domain, "AAAA")
        mx = dns_lookup(domain, "MX")
        ns = dns_lookup(domain, "NS")
        txt = dns_lookup(domain, "TXT")

        result = (
            f"🌐 DOMAIN INFORMATION\n\n"
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


async def username_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Пример:\n/username octocat"
        )
        return

    username = context.args[0].lstrip("@")

    sites = {
        "GitHub": f"https://github.com/{username}",
        "Reddit": f"https://www.reddit.com/user/{username}/",
        "GitLab": f"https://gitlab.com/{username}",
        "Codeberg": f"https://codeberg.org/{username}"
    }

    await update.message.reply_text(
        f"🔎 Проверяю публичные страницы @{username}..."
    )

    found = []

    for name, url in sites.items():

        try:
            response = requests.get(
                url,
                timeout=8,
                allow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0"
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
                    f"⚠️ {name}: HTTP {response.status_code}"
                )

        except requests.RequestException:
            found.append(
                f"⚠️ {name}: ошибка проверки"
            )

    result = (
        f"👤 USERNAME SEARCH\n\n"
        f"Username: @{username}\n\n"
        + "\n\n".join(found)
        + "\n\n⚠️ Наличие страницы не доказывает, "
          "что она принадлежит конкретному человеку."
    )

    await update.message.reply_text(result)


def main():

    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не установлен"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("ip", ip_search)
    )

    app.add_handler(
        CommandHandler("domain", domain_search)
    )

    app.add_handler(
        CommandHandler("username", username_search)
    )

    print("Bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
