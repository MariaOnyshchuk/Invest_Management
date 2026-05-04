"""
data/agent.py
Optimized two-stage pipeline:
  Stage 1: one GPT call per news item → scores for ALL tickers at once
  Stage 2: aggregate per ticker → final NewsItem recommendation

Metrics per (news, ticker):
  - ticker_relevance: 0-1
  - sentiment:       -1..1
  - impact:          0-1
  - risk_score:      0-1
  - summary:         str (Ukrainian)

Final score formula:
  weighted_sentiment = Σ(sentiment × impact × ticker_relevance) / n
  avg_risk           = Σ(risk_score × ticker_relevance) / n
  raw_score          = weighted_sentiment × (1 - avg_risk) × 10
  momentum           = (current_price - avg_buy_price) / avg_buy_price
  final_score        = raw_score × 0.8 + momentum × 10 × 0.2
"""

import json
import os
import datetime as dt
from typing import Optional

from openai import OpenAI
from data.stub_data import PORTFOLIO, NewsItem
from data.market_data import fetch_live_prices
from parsing_v2 import collect_all_feeds, FEED_URLS

from dotenv import load_dotenv
load_dotenv()

client    = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL     = "gpt-4o-mini"
NEWS_DAYS = 1
MAX_TEXT  = 3000

COMPANY_NAMES = {
    "AAPL":  "Apple Inc.",
    "MSFT":  "Microsoft Corporation",
    "NVDA":  "Nvidia Corporation",
    "GOOGL": "Alphabet / Google",
    "TSLA":  "Tesla Inc.",
    "META":  "Meta Platforms",
    "AMZN":  "Amazon",
    "AMD":   "Advanced Micro Devices",
}


# ── Stage 1: score one news item for ALL tickers in one GPT call ──────────────

def _enrich_for_all_tickers(news_item: dict, tickers: list[str]) -> Optional[dict]:
    """
    Single GPT call per news item.
    Returns {ticker: {ticker_relevance, sentiment, impact, risk_score, summary}}
    """
    companies = {t: COMPANY_NAMES.get(t, t) for t in tickers}

    tickers_block = "\n".join(
        f'  "{t}": {{"ticker_relevance": 0-1, "sentiment": -1..1, "impact": 0-1, "risk_score": 0-1, "summary": "Ukrainian sentence"}}'
        for t in tickers
    )

    prompt = f"""Analyze this financial news for the following companies and return scores for each.

Companies to analyze:
{json.dumps(companies, indent=2)}

News:
Title: {news_item.get('title', '')}
Published: {news_item.get('published', '')}
Text: {(news_item.get('text') or '')[:MAX_TEXT]}

Return ONLY valid JSON (no markdown):
{{
{tickers_block}
}}

Definitions:
- ticker_relevance: how directly this news affects the company (0=unrelated, 1=directly about it)
- sentiment: market direction (-1=very bearish, 0=neutral, 1=very bullish)
- impact: expected price-moving importance (0=noise, 1=major catalyst)
- risk_score: uncertainty or downside risk (0=safe, 1=high risk)
- summary: one sentence key takeaway for this ticker in Ukrainian
"""
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": "You are a financial news analyst. Output strict JSON only."},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[agent] enrich error: {e}")
        return None


# ── Stage 2: aggregate per ticker → NewsItem ──────────────────────────────────

def _aggregate(ticker: str, enriched: list[dict], price: float, avg_price: float) -> NewsItem:
    """
    enriched = list of per-news scores for this ticker
    Formula:
      weighted_sentiment = Σ(sentiment × impact × ticker_relevance) / n
      avg_risk           = Σ(risk_score × ticker_relevance) / n
      raw_score          = weighted_sentiment × (1 - avg_risk) × 10
      momentum           = (price - avg_price) / avg_price
      final_score        = raw_score × 0.8 + momentum × 10 × 0.2
    """
    relevant = [e for e in enriched if e.get("ticker_relevance", 0) >= 0.15]

    if not relevant:
        return NewsItem(
            ticker=ticker,
            time=dt.datetime.now().strftime("%H:%M"),
            sentiment="neutral", impact="low", score="+0.0",
            rec="hold", rec_label="Hold",
            text="No relevant news found for this ticker today.",
        )

    n = len(relevant)

    weighted_sentiment = sum(
        e["sentiment"] * e["impact"] * e["ticker_relevance"]
        for e in relevant
    ) / n

    avg_risk = sum(
        e["risk_score"] * e["ticker_relevance"]
        for e in relevant
    ) / n

    raw_score = weighted_sentiment * (1 - avg_risk) * 10

    momentum    = ((price - avg_price) / avg_price) if avg_price > 0 else 0.0
    final_score = raw_score * 0.8 + momentum * 10 * 0.2
    final_score = max(-10.0, min(10.0, final_score))

    # sentiment label
    if final_score >= 2.0:
        sentiment_label = "positive"
    elif final_score <= -2.0:
        sentiment_label = "negative"
    else:
        sentiment_label = "neutral"

    # impact label
    avg_impact_val = sum(e["impact"] for e in relevant) / n
    if avg_impact_val >= 0.6:
        impact_label = "high"
    elif avg_impact_val >= 0.3:
        impact_label = "medium"
    else:
        impact_label = "low"

    # recommendation
    if final_score >= 4.0:
        rec, rec_label = "buy",    "Buy more"
    elif final_score >= 1.5:
        rec, rec_label = "buy",    "Add position"
    elif final_score >= -1.5:
        rec, rec_label = "hold",   "Hold"
    elif final_score >= -4.0:
        rec, rec_label = "watch",  "Watch closely"
    else:
        rec, rec_label = "reduce", "Reduce"

    # top-2 summaries by impact × relevance
    top = sorted(relevant, key=lambda e: e["impact"] * e["ticker_relevance"], reverse=True)
    summaries = [e["summary"] for e in top[:2] if e.get("summary")]
    text = " ".join(summaries) or "Analysis based on aggregated news signals."

    return NewsItem(
        ticker=ticker,
        time=dt.datetime.now().strftime("%H:%M"),
        sentiment=sentiment_label,
        impact=impact_label,
        score=f"{final_score:+.1f}",
        rec=rec,
        rec_label=rec_label,
        text=text,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def generate_recommendations() -> list[NewsItem]:
    """Called from UI on 'Actualize' button. Returns list[NewsItem]."""
    print("[agent] Collecting news from RSS feeds...")
    raw_news = collect_all_feeds(FEED_URLS, days=NEWS_DAYS)
    print(f"[agent] Fetched {len(raw_news)} articles")

    print("[agent] Fetching live prices...")
    prices     = fetch_live_prices()
    avg_prices = {s.ticker: s.avg for s in PORTFOLIO}
    tickers    = [s.ticker for s in PORTFOLIO]

    # per_ticker_scores[ticker] = list of score dicts
    per_ticker_scores: dict[str, list[dict]] = {t: [] for t in tickers}

    # Stage 1: one GPT call per news item
    for i, item in enumerate(raw_news):
        print(f"[agent] Scoring article {i+1}/{len(raw_news)}: {item.get('title', '')[:60]}")
        scores = _enrich_for_all_tickers(item, tickers)
        if not scores:
            continue
        for ticker in tickers:
            if ticker in scores and isinstance(scores[ticker], dict):
                per_ticker_scores[ticker].append(scores[ticker])

    # Stage 2: aggregate per ticker
    results: list[NewsItem] = []
    for ticker in tickers:
        enriched = per_ticker_scores[ticker]
        relevant = sum(1 for e in enriched if e.get("ticker_relevance", 0) >= 0.15)
        print(f"[agent] {ticker}: {relevant}/{len(enriched)} relevant articles")

        news_item = _aggregate(
            ticker=ticker,
            enriched=enriched,
            price=prices.get(ticker, avg_prices.get(ticker, 0)),
            avg_price=avg_prices.get(ticker, 0),
        )
        results.append(news_item)
        print(f"[agent] {ticker}: score={news_item.score} → {news_item.rec_label}")

    return results