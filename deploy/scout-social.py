"""Competitor scan for Telegram and VK pages that are only reachable from a Russian IP.

Run on the server:  docker compose exec -T video-mcp python - < deploy/scout-social.py
Prints subscribers, the latest posts with views and the links they push, for pasting back to Claude.
"""

import html
import re

import httpx

TELEGRAM = [
    "chat_yandexeda", "couriers_chat", "delivery_yandex", "courier_fight", "kurier_spb", "courierNeva",
    "BogatiyKurier", "King_of_Delivery", "dostavista_official", "flowwow_courier",
    "taxoparkbazhin", "antonbbazhin", "dohod_na_dostavke",
]
VK = ["dedvadim64", "clubantonbazhin", "bogatiykurier", "yandex.eda", "samokat_courier", "kuper_couriers"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}


def text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def telegram(name: str) -> None:
    page = httpx.get(f"https://t.me/s/{name}", headers=UA, timeout=30, follow_redirects=True).text
    title = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    counters = [text(c) for c in re.findall(r'class="tgme_header_counter">(.*?)</', page)]
    extra = re.search(r'class="tgme_page_extra">(.*?)</div>', page, re.S)
    print(f"\n=== TG @{name}: {html.unescape(title.group(1)) if title else '?'} | "
          f"{', '.join(counters) or (text(extra.group(1)) if extra else 'no public preview (chat?)')}")
    posts = re.findall(r'tgme_widget_message_text[^>]*>(.*?)</div>.*?tgme_widget_message_views">([^<]*)<',
                       page, re.S)
    for body, views in posts[-6:]:
        links = sorted(set(re.findall(r'href="(https?://[^"]+)"', body)))[:4]
        print(f"  [{views} views] {text(body)[:220]}" + (f"\n      links: {' '.join(links)}" if links else ""))


def vk(name: str) -> None:
    page = httpx.get(f"https://vk.com/{name}", headers=UA, timeout=30, follow_redirects=True).text
    title = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    desc = re.search(r'<meta (?:property="og:description"|name="description") content="([^"]*)"', page)
    members = re.findall(r"([\d\s\xa0.,KМK]+)\s*(?:подписчик|участник|followers|members)", text(page))
    print(f"\n=== VK {name}: {html.unescape(title.group(1)) if title else '?'} | members: "
          f"{members[0].strip() if members else '?'}\n  {html.unescape(desc.group(1))[:300] if desc else ''}")


for channel in TELEGRAM:
    try:
        telegram(channel)
    except Exception as exc:  # one broken page should not stop the scan
        print(f"\n=== TG @{channel}: error {exc}")
for group in VK:
    try:
        vk(group)
    except Exception as exc:
        print(f"\n=== VK {group}: error {exc}")
