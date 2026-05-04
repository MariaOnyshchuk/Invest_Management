import argparse
import datetime as dt
import json
from typing import List, Dict, Optional

import feedparser
import requests
import trafilatura

# Перелік RSS‑стрічок для збору новин
FEED_URLS: List[str] = [
    # РБК‑Україна економіка – містить повні тексти
    "https://www.rbc.ua/static/rss/ukrnet.economic.ukr.rss.xml",
    # Економічна правда – у стрічці довгі описи статей
    "https://epravda.com.ua/rss/",
    # BBC Business – заголовки та посилання
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    # CNBC Economy – перелік статей із посиланнями
    "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    # CNN Business/Economy – приклад; доступність залежить від сервера
    "https://rss.cnn.com/rss/edition_business.rss",
]

# Скільки днів у минуле збирати новини
DEFAULT_LOOKBACK_DAYS = 7

def fetch_url(url: str, timeout: float = 10.0) -> Optional[str]:
    """Завантажує URL і повертає текстову відповідь."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None

def extract_full_text(url: str) -> Optional[str]:
    """Завантажує сторінку та витягує основний текст за допомогою trafilatura."""
    html = fetch_url(url)
    if not html:
        return None
    try:
        return trafilatura.extract(html)
    except Exception:
        return None

def parse_feed(feed_url: str, days: int) -> List[Dict[str, Optional[str]]]:
    """Парсить RSS‑стрічку та повертає список новин з повним текстом."""
    stories: List[Dict[str, Optional[str]]] = []
    feed_data = fetch_url(feed_url)
    if not feed_data:
        return stories
    feed = feedparser.parse(feed_data)
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    for entry in feed.entries:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = dt.datetime(*entry.published_parsed[:6])
            if published < cutoff:
                continue
        text: Optional[str] = None
        # якщо у стрічці є елемент content або summary – пробуємо використати його
        if "content" in entry:
            c = entry.content[0] if entry.content else None
            if c and isinstance(c, dict):
                text = c.get("value")
        elif getattr(entry, "summary", None) and len(entry.summary) > 500:
            text = entry.summary
        # якщо текст короткий, завантажуємо сторінку
        if not text or len(text) < 500:
            full_text = extract_full_text(entry.link)
            if full_text:
                text = full_text
        stories.append({
            "title": entry.title,
            "link": entry.link,
            "published": published.isoformat() if published else None,
            "text": text,
            "source": feed_url,
        })
    return stories

def collect_all_feeds(feed_urls: List[str], days: int) -> List[Dict[str, Optional[str]]]:
    all_stories: List[Dict[str, Optional[str]]] = []
    for url in feed_urls:
        all_stories.extend(parse_feed(url, days))
    return all_stories

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Агрегатор економічних новин")
    parser.add_argument("-d", "--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help="Скільки днів у минуле збирати новини (за замовчуванням 7)")
    parser.add_argument("-o", "--output", type=str, default="news_full.json",
                        help="Назва файлу для збереження JSON (за замовчуванням news_full.json)")
    args = parser.parse_args()
    news = collect_all_feeds(FEED_URLS, days=args.days)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    print(f"Збережено {len(news)} записів у {args.output}")