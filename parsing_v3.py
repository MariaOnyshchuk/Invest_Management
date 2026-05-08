import argparse
import datetime as dt
from email.utils import parsedate_to_datetime
import json
from typing import List, Dict, Optional, Any

import feedparser
import requests
import trafilatura

FEED_URLS: List[str] = [
    # РБК‑Україна економіка
    "https://www.rbc.ua/static/rss/ukrnet.economic.ukr.rss.xml",
    # Економічна правда
    "https://epravda.com.ua/rss/",
    # BBC Business
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    # CNBC Economy
    "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    # CNN Business/Economy
    "https://rss.cnn.com/rss/edition_business.rss",
]

BENZINGA_API_KEY = "bz.BFBTBNHNALGQFMEQ7RMJXOZTWFNX5IGG"
POLYGON_API_KEY = "xNk8ZB1U_tXZILOv4SRNQwOmQ93rbdD1"
BENZINGA_API_URL = "https://api.benzinga.com/api/v2/news"
POLYGON_NEWS_API_URL = "https://api.polygon.io/v2/reference/news"

DEFAULT_LOOKBACK_DAYS = 7


def utc_now() -> dt.datetime:
    return dt.datetime.utcnow()


def to_utc_naive(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is not None:
        return value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return value


def parse_any_date(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None

    raw = str(value).strip()
    if not raw:
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        return to_utc_naive(dt.datetime.fromisoformat(normalized))
    except Exception:
        pass
    try:
        return to_utc_naive(parsedate_to_datetime(raw))
    except Exception:
        return None


def is_recent(published: Optional[dt.datetime], days: int) -> bool:
    if published is None:
        return True
    cutoff = utc_now() - dt.timedelta(days=days)
    return published >= cutoff


def fetch_url(url: str, timeout: float = 10.0) -> Optional[str]:
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; investment-news-parser/1.0)",
            },
        )
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def extract_full_text(url: str) -> Optional[str]:
    html = fetch_url(url)
    if not html:
        return None
    try:
        return trafilatura.extract(html)
    except Exception:
        return None

def parse_feed(feed_url: str, days: int) -> List[Dict[str, Optional[str]]]:
    stories: List[Dict[str, Optional[str]]] = []
    feed_data = fetch_url(feed_url)
    if not feed_data:
        return stories

    feed = feedparser.parse(feed_data)

    for entry in feed.entries:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = dt.datetime(*entry.published_parsed[:6])
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published = dt.datetime(*entry.updated_parsed[:6])

        if not is_recent(published, days):
            continue

        text: Optional[str] = None
        if "content" in entry:
            c = entry.content[0] if entry.content else None
            if c and isinstance(c, dict):
                text = c.get("value")
        elif getattr(entry, "summary", None) and len(entry.summary) > 500:
            text = entry.summary

        link = entry.get("link", "")
        if (not text or len(text) < 500) and link:
            full_text = extract_full_text(link)
            if full_text:
                text = full_text

        stories.append({
            "title": entry.get("title", "").strip(),
            "link": link,
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

def request_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
) -> Optional[Any]:
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"API помилка для {url}: {exc}")
        return None


def parse_benzinga_api(days: int) -> List[Dict[str, Optional[str]]]:
    params = {
        "token": BENZINGA_API_KEY,
    }
    data = request_json(BENZINGA_API_URL, params=params)
    if not data:
        return []

    items = data if isinstance(data, list) else data.get("data", []) or data.get("news", [])

    stories: List[Dict[str, Optional[str]]] = []
    for item in items:
        published = parse_any_date(item.get("created") or item.get("updated"))
        if not is_recent(published, days):
            continue

        link = item.get("url") or ""
        text = item.get("body") or item.get("teaser") or item.get("summary")
        if (not text or len(str(text)) < 500) and link:
            full_text = extract_full_text(link)
            if full_text:
                text = full_text

        stories.append({
            "title": item.get("title", ""),
            "link": link,
            "published": published.isoformat() if published else None,
            "text": text,
            "source": "benzinga_api",
        })

    return stories


def parse_polygon_api(days: int) -> List[Dict[str, Optional[str]]]:
    if not POLYGON_API_KEY:
        return []

    start = (utc_now() - dt.timedelta(days=days)).date().isoformat()
    params = {
        "apiKey": POLYGON_API_KEY,
        "published_utc.gte": start,
        "order": "desc",
        "sort": "published_utc",
        "limit": 100,
    }

    data = request_json(POLYGON_NEWS_API_URL, params=params)
    if not data:
        return []

    items = data.get("results", []) if isinstance(data, dict) else []

    stories: List[Dict[str, Optional[str]]] = []
    for item in items:
        published = parse_any_date(item.get("published_utc"))
        if not is_recent(published, days):
            continue

        link = item.get("article_url") or item.get("amp_url") or ""
        text = item.get("description")

        insights = item.get("insights") or []
        if insights:
            insight_lines = []
            for insight in insights[:5]:
                ticker = insight.get("ticker")
                sentiment = insight.get("sentiment")
                reason = insight.get("sentiment_reasoning")
                insight_lines.append(f"{ticker}: {sentiment}. {reason}")
            text = (text or "") + "\n\nPolygon insights:\n" + "\n".join(insight_lines)

        stories.append({
            "title": item.get("title", ""),
            "link": link,
            "published": published.isoformat() if published else None,
            "text": text,
            "source": "polygon_io",
        })

    return stories


def collect_api_sources(days: int) -> List[Dict[str, Optional[str]]]:
    all_stories: List[Dict[str, Optional[str]]] = []

    all_stories.extend(parse_benzinga_api(days))

    all_stories.extend(parse_polygon_api(days))

    return all_stories


def collect_all_sources(feed_urls: List[str], days: int) -> List[Dict[str, Optional[str]]]:
    all_news: List[Dict[str, Optional[str]]] = []
    all_news.extend(collect_all_feeds(feed_urls, days))
    all_news.extend(collect_api_sources(days))
    return all_news


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Агрегатор економічних новин")
    parser.add_argument(
        "-d", "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Скільки днів у минуле збирати новини (за замовчуванням 7)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="news_full.json",
        help="Назва файлу для збереження JSON (за замовчуванням news_full.json)",
    )
    args = parser.parse_args()

    news = collect_all_sources(FEED_URLS, days=args.days)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)

    print(f"Збережено {len(news)} записів у {args.output}")
