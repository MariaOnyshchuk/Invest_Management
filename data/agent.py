"""
data/agent.py
Optimized two-stage pipeline with progress callback, metrics, and sources.

Stage 1: one GPT call per news item → scores for ALL tickers at once (n_articles calls)
Stage 2: aggregate per ticker → NewsItem with visible metrics + source links

Metrics per (news × ticker):
  - ticker_relevance: 0-1
  - sentiment:       -1..1
  - impact:          0-1
  - risk_score:      0-1

Aggregation formula:
  weighted_sentiment = Σ(sentiment × impact × ticker_relevance) / n
  avg_risk           = Σ(risk_score × ticker_relevance) / n
  raw_score          = weighted_sentiment × (1 - avg_risk) × 10
  momentum           = (current_price - avg_buy_price) / avg_buy_price
  final_score        = raw_score × 0.8 + momentum × 10 × 0.2
"""

import json
import os
import datetime as dt
from typing import Optional, Callable

from openai import OpenAI
from data.stub_data import PORTFOLIO, NewsItem, RiskMetrics
from data.market_data import fetch_live_prices
from parsing_v2 import collect_all_feeds, FEED_URLS

from dotenv import load_dotenv
load_dotenv()

client    = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL     = "gpt-4o-mini"
NEWS_DAYS = 1
MAX_TEXT  = 3000
DEBUG_MODE    = False   # ← змінити на False для продакшну
DEBUG_MAX_ARTICLES = 5

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


# ── Risk metrics agent summary ────────────────────────────────────────────────

def generate_risk_metrics_analysis(
    risk: RiskMetrics,
    sectors: dict[str, float],
) -> dict[str, object]:
    """
    Lightweight agent-style interpretation for static portfolio risk metrics.
    Kept local so the dashboard can render immediately without spending an API
    call every time the UI starts.
    """
    top_sector, top_weight = max(sectors.items(), key=lambda x: x[1]) if sectors else ("—", 0)

    risk_flags: list[str] = []
    if risk.beta >= 1.2:
        risk_flags.append("Beta вище ринку: портфель сильніше реагує на рух індексів.")
    elif risk.beta <= 0.8:
        risk_flags.append("Beta нижче ринку: портфель менш чутливий до broad market swings.")
    else:
        risk_flags.append("Beta близька до 1: ринкова чутливість збалансована.")

    if risk.volatility >= 22:
        risk_flags.append("Волатильність підвищена, тому варто тримати більший cash buffer.")
    elif risk.volatility >= 15:
        risk_flags.append("Волатильність помірна, але позиції можуть різко змінювати P&L.")
    else:
        risk_flags.append("Волатильність контрольована для growth-heavy портфеля.")

    if risk.sharpe >= 1.5:
        risk_flags.append("Sharpe сильний: дохідність добре компенсує поточний ризик.")
    elif risk.sharpe >= 1.0:
        risk_flags.append("Sharpe прийнятний, але є простір для кращої risk-adjusted return.")
    else:
        risk_flags.append("Sharpe слабкий: ризик поки не достатньо оплачується дохідністю.")

    if abs(risk.max_drawdown) >= 20:
        risk_flags.append("Max drawdown значний: потрібні правила зменшення експозиції.")
    else:
        risk_flags.append("Max drawdown не критичний, але його треба моніторити під час sell-off.")

    concentration_note = (
        f"Найбільша секторна вага: {top_sector} ({top_weight:.0f}%). "
        "Це головний драйвер як upside, так і просадки."
    )

    score = 0
    score += 1 if risk.beta >= 1.2 else 0
    score += 1 if risk.volatility >= 18 else 0
    score += 1 if abs(risk.max_drawdown) >= 15 else 0
    score += 1 if top_weight >= 55 else 0
    score -= 1 if risk.sharpe >= 1.5 else 0

    if score >= 3:
        severity = "high"
        title = "Risk posture: elevated"
    elif score >= 1:
        severity = "medium"
        title = "Risk posture: moderate"
    else:
        severity = "low"
        title = "Risk posture: controlled"

    return {
        "severity": severity,
        "title": title,
        "summary": concentration_note,
        "bullets": risk_flags[:3],
    }


# ── Stage 1: score one news item for ALL tickers in one GPT call ──────────────

def _enrich_for_all_tickers(news_item: dict, tickers: list[str]) -> Optional[dict]:
    companies    = {t: COMPANY_NAMES.get(t, t) for t in tickers}
    tickers_fmt  = "\n".join(
        f'  "{t}": {{"ticker_relevance": 0-1, "sentiment": -1..1, '
        f'"impact": 0-1, "risk_score": 0-1, "summary": "Ukrainian sentence"}}'
        for t in tickers
    )

    prompt = f"""Analyze this financial news and score its relevance for each company.

Companies:
{json.dumps(companies, indent=2)}

News:
Title: {news_item.get('title', '')}
Published: {news_item.get('published', '')}
Text: {(news_item.get('text') or '')[:MAX_TEXT]}

Return ONLY valid JSON (no markdown):
{{
{tickers_fmt}
}}

Definitions:
- ticker_relevance: 0=unrelated, 1=directly about this company
- sentiment: -1=very bearish, 0=neutral, 1=very bullish
- impact: 0=noise, 1=major price catalyst
- risk_score: 0=safe signal, 1=high uncertainty/risk
- summary: one sentence key takeaway for this ticker in Ukrainian
"""
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": "Financial news analyst. Output strict JSON only."},
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

def _aggregate(
    ticker:     str,
    enriched:   list[dict],   # list of {score_dict, news_item}
    price:      float,
    avg_price:  float,
) -> NewsItem:
    """
    Formula:
      weighted_sentiment = Σ(sentiment × impact × ticker_relevance) / n
      avg_risk           = Σ(risk_score × ticker_relevance) / n
      raw_score          = weighted_sentiment × (1 - avg_risk) × 10
      momentum           = (price - avg_price) / avg_price
      final_score        = raw_score × 0.8 + momentum × 10 × 0.2
    """
    relevant = [e for e in enriched if e["scores"].get("ticker_relevance", 0) >= 0.15]

    if not relevant:
        return NewsItem(
            ticker=ticker,
            time=dt.datetime.now().strftime("%H:%M"),
            sentiment="neutral", impact="low", score="+0.0",
            rec="hold", rec_label="Hold",
            text="No relevant news found for this ticker today.",
            metrics={}, sources=[], article_count=0,
        )

    n = len(relevant)
    scores_list = [e["scores"] for e in relevant]

    weighted_sentiment = sum(
        s["sentiment"] * s["impact"] * s["ticker_relevance"]
        for s in scores_list
    ) / n

    avg_risk = sum(
        s["risk_score"] * s["ticker_relevance"]
        for s in scores_list
    ) / n

    raw_score = weighted_sentiment * (1 - avg_risk) * 10

    momentum    = ((price - avg_price) / avg_price) if avg_price > 0 else 0.0
    final_score = raw_score * 0.8 + momentum * 10 * 0.2
    final_score = max(-10.0, min(10.0, final_score))

    # labels
    sentiment_label = (
        "positive" if final_score >= 2.0 else
        "negative" if final_score <= -2.0 else
        "neutral"
    )
    avg_impact_val = sum(s["impact"] for s in scores_list) / n
    impact_label = (
        "high"   if avg_impact_val >= 0.6 else
        "medium" if avg_impact_val >= 0.3 else
        "low"
    )

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

    # top-2 sources by impact × relevance
    top = sorted(
        relevant,
        key=lambda e: e["scores"]["impact"] * e["scores"]["ticker_relevance"],
        reverse=True,
    )
    summaries = [e["scores"]["summary"] for e in top[:2] if e["scores"].get("summary")]
    text = " ".join(summaries) or "Analysis based on aggregated news signals."

    sources = [
        {
            "title":  e["news"].get("title", ""),
            "link":   e["news"].get("link",  ""),
            "source": e["news"].get("source", ""),
        }
        for e in top[:3]
    ]

    metrics = {
        "weighted_sentiment": round(weighted_sentiment, 3),
        "avg_risk":           round(avg_risk, 3),
        "raw_score":          round(raw_score, 2),
        "momentum_pct":       round(momentum * 100, 2),
        "relevant_articles":  n,
        "total_articles":     len(enriched),
    }

    return NewsItem(
        ticker=ticker,
        time=dt.datetime.now().strftime("%H:%M"),
        sentiment=sentiment_label,
        impact=impact_label,
        score=f"{final_score:+.1f}",
        rec=rec,
        rec_label=rec_label,
        text=text,
        metrics=metrics,
        sources=sources,
        article_count=n,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def generate_recommendations(
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> list[NewsItem]:
    """
    on_progress(current, total, status) — called after each article is scored.
    Returns list[NewsItem], one per portfolio ticker.
    """
    print("[agent] Collecting news from RSS feeds...")
    raw_news = collect_all_feeds(FEED_URLS, days=NEWS_DAYS)
    if DEBUG_MODE:
        raw_news = raw_news[:DEBUG_MAX_ARTICLES]
    total    = len(raw_news)
    print(f"[agent] Fetched {total} articles")

    if on_progress:
        on_progress(0, total, f"Fetched {total} articles, scoring...")

    print("[agent] Fetching live prices...")
    prices     = fetch_live_prices()
    avg_prices = {s.ticker: s.avg for s in PORTFOLIO}
    tickers    = [s.ticker for s in PORTFOLIO]

    # per_ticker: list of {scores: dict, news: dict}
    per_ticker: dict[str, list[dict]] = {t: [] for t in tickers}

    # Stage 1
    for i, item in enumerate(raw_news):
        title = (item.get("title") or "")[:60]
        print(f"[agent] [{i+1}/{total}] {title}")

        scores = _enrich_for_all_tickers(item, tickers)
        if scores:
            for ticker in tickers:
                if ticker in scores and isinstance(scores[ticker], dict):
                    per_ticker[ticker].append({
                        "scores": scores[ticker],
                        "news":   item,
                    })

        if on_progress:
            on_progress(i + 1, total, f"Scored {i+1}/{total}: {title[:40]}...")

    # Stage 2
    results: list[NewsItem] = []
    for ticker in tickers:
        enriched = per_ticker[ticker]
        relevant = sum(1 for e in enriched if e["scores"].get("ticker_relevance", 0) >= 0.15)
        print(f"[agent] {ticker}: {relevant}/{len(enriched)} relevant")

        item = _aggregate(
            ticker=ticker,
            enriched=enriched,
            price=prices.get(ticker, avg_prices.get(ticker, 0)),
            avg_price=avg_prices.get(ticker, 0),
        )
        results.append(item)
        print(f"[agent] {ticker}: score={item.score} → {item.rec_label}")

    return results
