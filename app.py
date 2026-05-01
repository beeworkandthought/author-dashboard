import feedparser
import urllib.parse
import os
import json
import time as _time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def extract_first_img(html):
    if not html:
        return ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        src = m.group(1)
        if not src.startswith("data:"):
            return src
    return ""

DESIGN_FEEDS = [
    {
        "name": "Dezeen",
        "url": "https://www.dezeen.com/technology/feed/",
        "avatarColor": "#1a1a1a",
    },
    {
        "name": "Dezeen Architecture",
        "url": "https://www.dezeen.com/architecture/feed/",
        "avatarColor": "#444444",
    },
    {
        "name": "Designboom",
        "url": "https://www.designboom.com/technology/feed/",
        "avatarColor": "#e63d27",
    },
    {
        "name": "It's Nice That",
        "url": "https://www.itsnicethat.com/rss",
        "avatarColor": "#FF4F00",
    },
    {
        "name": "Colossal",
        "url": "https://www.thisiscolossal.com/feed/",
        "avatarColor": "#2D6A4F",
    },
    {
        "name": "Yanko Design",
        "url": "https://www.yankodesign.com/feed/",
        "avatarColor": "#0066CC",
    },
    {
        "name": "Core77",
        "url": "https://www.core77.com/rss",
        "avatarColor": "#333333",
    },
    {
        "name": "Creative Boom",
        "url": "https://www.creativeboom.com/feed/",
        "avatarColor": "#E91E8C",
    },
    {
        "name": "Wallpaper*",
        "url": "https://www.wallpaper.com/feeds/latest.rss",
        "avatarColor": "#8B6914",
    },
]


def to_relative_time(published_parsed):
    if not published_parsed:
        return ""
    try:
        dt = datetime.fromtimestamp(_time.mktime(published_parsed))
        diff = datetime.now() - dt
        hours = int(diff.total_seconds() / 3600)
        if hours < 1:
            return "방금 전"
        elif hours < 24:
            return f"{hours}시간 전"
        else:
            days = hours // 24
            return f"{days}일 전"
    except Exception:
        return ""


def fetch_og_data(url, timeout=5):
    if not HAS_REQUESTS:
        return "", ""
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"})
        soup = BeautifulSoup(r.text, "html.parser")
        image = ""
        for attrs in [{"property": "og:image"}, {"name": "twitter:image"}]:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content", "").strip():
                image = tag["content"].strip()
                break
        description = ""
        for attrs in [{"property": "og:description"}, {"name": "description"}]:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content", "").strip():
                description = tag["content"].strip()[:300]
                break
        return image, description
    except Exception:
        return "", ""


def fetch_feed_items(feed_config, max_items=10):
    feed = feedparser.parse(feed_config["url"])
    items = []
    for entry in feed.entries[:max_items]:
        image = ""
        for mc in getattr(entry, "media_content", []):
            if mc.get("url", ""):
                image = mc["url"]
                break
        if not image:
            for mt in getattr(entry, "media_thumbnail", []):
                if mt.get("url", ""):
                    image = mt["url"]
                    break
        if not image:
            for enc in getattr(entry, "enclosures", []):
                if enc.get("type", "").startswith("image"):
                    image = enc.get("href", "")
                    break
        if not image:
            for content_item in getattr(entry, "content", []):
                image = extract_first_img(content_item.get("value", ""))
                if image:
                    break
        if not image:
            image = extract_first_img(getattr(entry, "summary", "") or "")

        items.append({
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", "#"),
            "published": entry.get("published", "")[:16],
            "relative_time": to_relative_time(entry.get("published_parsed")),
            "source": feed_config["name"],
            "avatarColor": feed_config.get("avatarColor", "#C0181E"),
            "image": image,
            "summary": "",
        })
    return items


def fetch_all_feeds():
    all_items = []
    for feed_config in DESIGN_FEEDS:
        all_items.extend(fetch_feed_items(feed_config))

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fetch_og_data, item["link"]): i for i, item in enumerate(all_items)}
        for future in as_completed(futures, timeout=25):
            idx = futures[future]
            try:
                image, desc = future.result()
                if not all_items[idx]["image"]:
                    all_items[idx]["image"] = image
                all_items[idx]["summary"] = desc
            except Exception:
                pass

    return all_items


def build_cards_json(items):
    cards = []
    for item in items:
        raw_img = item.get("image", "")
        proxied_img = f"/api/img-proxy?url={urllib.parse.quote(raw_img, safe='')}" if raw_img else ""
        img_style = (
            f"background: url('{proxied_img}') center/cover #1a1a1a;"
            if proxied_img else ""
        )
        cards.append({
            "author": item["source"],
            "avatarColor": item.get("avatarColor", "#C0181E"),
            "time": item.get("relative_time", ""),
            "title": item["title"],
            "type": "image" if proxied_img else "text",
            "tag": "디자인",
            "summary": item.get("summary", ""),
            "imgStyle": img_style,
            "image": proxied_img,
            "subtitle": f"{item['source']} · {item.get('published', '')}",
            "url": item["link"],
            "published": item.get("published", ""),
        })

    cards.sort(key=lambda x: x.get("published", ""), reverse=True)
    return cards


def main():
    print("피드를 가져오는 중...")
    items = fetch_all_feeds()
    cards = build_cards_json(items)

    cards_path = os.path.join(os.path.dirname(__file__), "cards.json")
    with open(cards_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    print(f"cards.json 생성 완료: {cards_path}")


if __name__ == "__main__":
    main()
