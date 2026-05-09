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
  weighted_sentiment = Σ(sentiment × impact × ticker_relevance) / Σ(impact × ticker_relevance)
  avg_risk           = Σ(risk_score × ticker_relevance) / Σ(ticker_relevance)
  raw_score          = weighted_sentiment × (1 - avg_risk) × 10
  momentum           = small nudge only when news has a meaningful signal
  final_score        = raw_score × 0.9 + momentum_nudge
"""

import json
import os
import datetime as dt
import re
from typing import Optional, Callable

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from data.stub_data import PORTFOLIO, NewsItem, RiskMetrics, Stock
from data.market_data import fetch_live_prices, fetch_ticker_fundamentals
from parsing_v3 import collect_all_sources, FEED_URLS

MODEL     = "gpt-4o-mini"
NEWS_DAYS = 7
MAX_TEXT  = 3000
DEBUG_MODE    = False   # ← змінити на False для продакшну
DEBUG_MAX_ARTICLES = 5
MAX_ARTICLES_TO_SCORE = 30
MIN_TICKER_RELEVANCE = 0.15
MIN_NEWS_IMPACT = 0.10
FALLBACK_SIGNAL_SOURCE = "Market signal"

COMPANY_SUFFIX_RE = re.compile(
    r"\b(inc|inc\.|corp|corp\.|corporation|co|co\.|ltd|ltd\.|plc|llc|sa|nv|ag|class [abc])\b",
    re.IGNORECASE,
)
SECTOR_KEYWORDS = {
    "tech": ["technology", "software", "cloud", "ai", "artificial intelligence"],
    "semi": ["semiconductor", "chip", "gpu", "ai chip", "data center"],
    "technology": ["technology", "software", "cloud", "ai", "artificial intelligence"],
    "financial": ["bank", "rates", "credit", "lending", "financial"],
    "finance": ["bank", "rates", "credit", "lending", "financial"],
    "health": ["healthcare", "pharma", "drug", "medical"],
    "consumer": ["consumer", "retail", "spending"],
}


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _clean_company_name(name: str) -> str:
    clean = COMPANY_SUFFIX_RE.sub("", name or "")
    clean = re.sub(r"\s+", " ", clean).strip(" ,.-")
    return clean


def _clean_summary(summary: str, title: str) -> str:
    text = re.sub(r"\s+", " ", summary or "").strip()
    if not text:
        return ""

    vague_start = re.compile(
        r"^(ця новина|ця стаття|цей матеріал|цей сюжет|this news|this article)\b",
        re.IGNORECASE,
    )
    if vague_start.search(text):
        short_title = re.sub(r"\s+", " ", title or "").strip()
        short_title = short_title[:90].rstrip(" .,-")
        if short_title:
            text = vague_start.sub(f"Матеріал «{short_title}»", text, count=1)

    return text


def _bounded_score(value: float) -> float:
    return max(-10.0, min(10.0, value))


def _labels_for_score(score: float) -> tuple[str, str, str]:
    sentiment = (
        "positive" if score >= 2.0 else
        "negative" if score <= -2.0 else
        "neutral"
    )
    if score >= 4.0:
        rec, rec_label = "buy", "Buy more"
    elif score >= 1.5:
        rec, rec_label = "buy", "Add position"
    elif score >= -1.5:
        rec, rec_label = "hold", "Hold"
    elif score >= -4.0:
        rec, rec_label = "watch", "Watch closely"
    else:
        rec, rec_label = "reduce", "Reduce"
    return sentiment, rec, rec_label


def _market_signal_item(stock: Stock, price: float, raw_news_count: int = 0) -> NewsItem:
    momentum_pct = ((price - stock.avg) / stock.avg * 100) if stock.avg else 0.0
    fundamentals = fetch_ticker_fundamentals(stock.ticker)
    target = fundamentals.get("target_mean_price") or fundamentals.get("target_median_price")
    beta = _num(fundamentals.get("beta"), 1.0)

    target_gap_pct = 0.0
    has_target = False
    if target and price:
        target_gap_pct = (_num(target) - price) / price * 100
        has_target = _num(target) > 0

    risk_penalty = max(0.0, beta - 1.0) * 0.6
    score = _bounded_score((momentum_pct / 18) + (target_gap_pct / 12 if has_target else 0) - risk_penalty)
    sentiment, rec, rec_label = _labels_for_score(score)

    if has_target:
        valuation_text = f"analyst target gap {target_gap_pct:+.1f}%"
    else:
        valuation_text = "analyst target unavailable"

    text = (
        f"Немає достатньо прямої новини для {stock.ticker}, тому використано fallback-сигнал: "
        f"позиція має P&L {momentum_pct:+.1f}% від середньої ціни входу, {valuation_text}, "
        f"beta {beta:.2f}. Це не новинний catalyst, а market/valuation read-through для MVP."
    )

    return NewsItem(
        ticker=stock.ticker,
        time=dt.datetime.now().strftime("%H:%M"),
        sentiment=sentiment,
        impact="low",
        score=f"{score:+.1f}",
        rec=rec,
        rec_label=rec_label,
        text=text,
        metrics={
            "signal_type": FALLBACK_SIGNAL_SOURCE,
            "momentum_pct": round(momentum_pct, 2),
            "target_gap_pct": round(target_gap_pct, 2) if has_target else None,
            "beta": round(beta, 2),
            "raw_news_seen": raw_news_count,
        },
        sources=[],
        article_count=0,
    )


def _build_company_profiles(portfolio: list[Stock]) -> dict[str, dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {}
    for stock in portfolio:
        ticker = stock.ticker.upper()
        clean_name = _clean_company_name(stock.name)
        aliases = {ticker, stock.name, clean_name}

        first_token = clean_name.split(" ")[0] if clean_name else ""
        if len(first_token) >= 3:
            aliases.add(first_token)

        sector_terms = SECTOR_KEYWORDS.get(stock.sector.lower(), [])
        profiles[ticker] = {
            "ticker": ticker,
            "name": stock.name,
            "sector": stock.sector,
            "aliases": sorted(alias for alias in aliases if alias),
            "sector_keywords": sector_terms,
            "avg_price": stock.avg,
            "quantity": stock.qty,
        }
    return profiles


def _search_keywords(profiles: dict[str, dict[str, object]]) -> list[str]:
    keywords: set[str] = set()
    for profile in profiles.values():
        keywords.update(str(alias) for alias in profile["aliases"])
        keywords.update(str(term) for term in profile["sector_keywords"])
    return sorted(keyword for keyword in keywords if len(keyword) >= 2)


def _article_text(news_item: dict) -> str:
    return " ".join(
        str(news_item.get(key) or "")
        for key in ("title", "text", "source")
    ).lower()


def _article_matches_profiles(news_item: dict, profiles: dict[str, dict[str, object]]) -> bool:
    text = _article_text(news_item)
    for profile in profiles.values():
        aliases = [str(alias).lower() for alias in profile["aliases"]]
        sector_terms = [str(term).lower() for term in profile["sector_keywords"]]
        if any(alias and alias in text for alias in aliases):
            return True
        if any(term and term in text for term in sector_terms):
            return True
    return False


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

def _enrich_for_all_tickers(news_item: dict, profiles: dict[str, dict[str, object]]) -> Optional[dict]:
    client = _openai_client()
    if client is None:
        print("[agent] OPENAI_API_KEY is missing; skipping AI enrichment")
        return None

    tickers = list(profiles)
    tickers_fmt  = "\n".join(
        f'  "{t}": {{"ticker_relevance": 0-1, "sentiment": -1..1, '
        f'"impact": 0-1, "risk_score": 0-1, "summary": "Ukrainian sentence"}}'
        for t in tickers
    )

    prompt = f"""Analyze this financial news and score its relevance for each company.

Companies:
{json.dumps(profiles, indent=2, ensure_ascii=False)}

News:
Title: {news_item.get('title', '')}
Published: {news_item.get('published', '')}
Text: {(news_item.get('text') or '')[:MAX_TEXT]}

Return ONLY valid JSON (no markdown):
{{
{tickers_fmt}
}}

Definitions:
- ticker_relevance: 0=unrelated, 1=direct company news. Use 0.15-0.4 for sector, competitor, supply-chain, or macro news that plausibly affects this company.
- sentiment: -1=very bearish, 0=neutral, 1=very bullish
- impact: 0=noise, 1=major price catalyst
- risk_score: 0=safe signal, 1=high uncertainty/risk
- If the article has no practical read-through for a ticker, use ticker_relevance=0, impact=0, risk_score=0, summary="".
- summary: one Ukrainian sentence naming the concrete catalyst/topic. Never start with "ця новина", "ця стаття", "цей матеріал", "this news", or "this article"; mention the article topic/title instead.
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
      weighted_sentiment = Σ(sentiment × impact × ticker_relevance) / Σ(impact × ticker_relevance)
      avg_risk           = Σ(risk_score × ticker_relevance) / Σ(ticker_relevance)
      raw_score          = weighted_sentiment × (1 - avg_risk) × 10
      momentum           = (price - avg_price) / avg_price, used only as a small nudge when news has signal
      final_score        = raw_score × 0.9 + momentum × 10 × 0.1
    """
    relevant = [
        e for e in enriched
        if (
            _num(e["scores"].get("ticker_relevance")) >= MIN_TICKER_RELEVANCE
            and _num(e["scores"].get("impact")) >= MIN_NEWS_IMPACT
        )
    ]

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
    signal_weight = sum(
        max(0.0, _num(s.get("impact"))) * max(0.0, _num(s.get("ticker_relevance")))
        for s in scores_list
    )

    if signal_weight > 0:
        weighted_sentiment = sum(
            _num(s.get("sentiment")) * _num(s.get("impact")) * _num(s.get("ticker_relevance"))
            for s in scores_list
        ) / signal_weight
    else:
        weighted_sentiment = 0.0

    avg_risk = sum(
        _num(s.get("risk_score")) * _num(s.get("ticker_relevance"))
        for s in scores_list
    ) / max(sum(_num(s.get("ticker_relevance")) for s in scores_list), 1e-9)

    raw_score = weighted_sentiment * (1 - avg_risk) * 10

    momentum    = ((price - avg_price) / avg_price) if avg_price > 0 else 0.0
    momentum_component = momentum * 10 * 0.1 if signal_weight >= MIN_NEWS_IMPACT else 0.0
    final_score = raw_score * 0.9 + momentum_component
    final_score = max(-10.0, min(10.0, final_score))

    # labels
    sentiment_label, rec, rec_label = _labels_for_score(final_score)
    avg_impact_val = sum(_num(s.get("impact")) for s in scores_list) / n
    impact_label = (
        "high"   if avg_impact_val >= 0.6 else
        "medium" if avg_impact_val >= 0.3 else
        "low"
    )

    # top-2 sources by impact × relevance
    top = sorted(
        relevant,
        key=lambda e: _num(e["scores"].get("impact")) * _num(e["scores"].get("ticker_relevance")),
        reverse=True,
    )
    summaries = [
        _clean_summary(e["scores"].get("summary", ""), e["news"].get("title", ""))
        for e in top[:2]
        if e["scores"].get("summary")
    ]
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
        "momentum_used":      round(momentum_component, 2),
        "signal_weight":      round(signal_weight, 3),
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
    portfolio: Optional[list[Stock]] = None,
    prices: Optional[dict[str, float]] = None,
) -> list[NewsItem]:
    """
    on_progress(current, total, status) — called after each article is scored.
    Returns list[NewsItem], one per portfolio ticker.
    """
    active_portfolio = list(PORTFOLIO if portfolio is None else portfolio)
    profiles = _build_company_profiles(active_portfolio)
    tickers = list(profiles)
    keywords = _search_keywords(profiles)

    if not tickers:
        if on_progress:
            on_progress(0, 0, "Portfolio is empty")
        return []

    if prices is None:
        print("[agent] Fetching live prices...")
        prices = fetch_live_prices(active_portfolio)
    avg_prices = {s.ticker: s.avg for s in active_portfolio}
    by_ticker = {s.ticker: s for s in active_portfolio}

    if not os.getenv("OPENAI_API_KEY"):
        if on_progress:
            on_progress(0, len(tickers), "OPENAI_API_KEY missing; using market signals...")
        return [
            _market_signal_item(
                stock=stock,
                price=prices.get(stock.ticker, avg_prices.get(stock.ticker, stock.price)),
            )
            for stock in active_portfolio
        ]

    print("[agent] Collecting news from RSS/API sources...")
    raw_news = collect_all_sources(
        FEED_URLS,
        days=NEWS_DAYS,
        keywords=keywords,
        tickers=tickers,
    )
    filtered_news = [
        item for item in raw_news
        if _article_matches_profiles(item, profiles)
    ]
    if len(filtered_news) > MAX_ARTICLES_TO_SCORE:
        filtered_news = filtered_news[:MAX_ARTICLES_TO_SCORE]

    if DEBUG_MODE:
        filtered_news = filtered_news[:DEBUG_MAX_ARTICLES]
    total = len(filtered_news)
    print(f"[agent] Fetched {len(raw_news)} articles, scoring {total} relevant candidates")

    if on_progress:
        on_progress(0, total, f"Fetched {len(raw_news)} articles, scoring {total} candidates...")

    # per_ticker: list of {scores: dict, news: dict}
    per_ticker: dict[str, list[dict]] = {t: [] for t in tickers}

    # Stage 1
    for i, item in enumerate(filtered_news):
        title = (item.get("title") or "")[:60]
        print(f"[agent] [{i+1}/{total}] {title}")

        scores = _enrich_for_all_tickers(item, profiles)
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
        relevant = sum(
            1 for e in enriched
            if (
                _num(e["scores"].get("ticker_relevance")) >= MIN_TICKER_RELEVANCE
                and _num(e["scores"].get("impact")) >= MIN_NEWS_IMPACT
            )
        )
        print(f"[agent] {ticker}: {relevant}/{len(enriched)} relevant")

        item = _aggregate(
            ticker=ticker,
            enriched=enriched,
            price=prices.get(ticker, avg_prices.get(ticker, 0)),
            avg_price=avg_prices.get(ticker, 0),
        )
        if item.article_count == 0:
            item = _market_signal_item(
                stock=by_ticker[ticker],
                price=prices.get(ticker, avg_prices.get(ticker, by_ticker[ticker].price)),
                raw_news_count=len(raw_news),
            )
        results.append(item)
        print(f"[agent] {ticker}: score={item.score} → {item.rec_label}")

    return results
