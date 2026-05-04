"""
data/stub_data.py
Усі рейкові дані портфелю, новин та watchlist-у.
"""

from dataclasses import dataclass, field
from typing import Literal

# ── Типи ─────────────────────────────────────────────────────────────────────

@dataclass
class Stock:
    ticker: str
    name: str
    qty: int
    avg: float
    price: float
    sector: str

@dataclass
class NewsItem:
    ticker: str
    time: str
    sentiment: Literal["positive", "neutral", "negative"]
    impact: Literal["high", "medium", "low"]
    score: str
    rec: Literal["buy", "hold", "watch", "reduce"]
    rec_label: str
    text: str
    # нові поля:
    metrics: dict = field(default_factory=dict)
    sources: list = field(default_factory=list)
    article_count: int = 0

@dataclass
class WatchItem:
    ticker: str
    price: float
    chg: float        # денна зміна, %

@dataclass
class CalendarEvent:
    label: str
    date: str
    color: str        # hex

@dataclass
class RiskMetrics:
    beta: float
    volatility: float   # %
    sharpe: float
    max_drawdown: float  # %, від'ємне

# ── Дані ─────────────────────────────────────────────────────────────────────

PORTFOLIO: list[Stock] = [
    Stock("AAPL",  "Apple Inc.",      15,  172.40, 189.30, "Tech"),
    Stock("MSFT",  "Microsoft Corp.", 8,   310.00, 378.90, "Tech"),
    Stock("NVDA",  "Nvidia Corp.",    5,   480.00, 874.15, "Semi"),
    Stock("GOOGL", "Alphabet Inc.",   10,  135.00, 160.20, "Tech"),
]

NEWS: list[NewsItem] = [
    NewsItem(
        ticker="AAPL", time="09:41",
        sentiment="neutral", impact="medium", score="+2.1",
        rec="hold", rec_label="Hold",
        text="Apple звітувала про квартальний виторг $119.6 млрд (+5% р/р). "
             "Продажі iPhone стабільні в Китаї попри конкуренцію Huawei. "
             "Goldman Sachs підвищили таргет до $210.",
    ),
    NewsItem(
        ticker="NVDA", time="10:15",
        sentiment="positive", impact="high", score="+8.4",
        rec="buy", rec_label="Buy more",
        text="Nvidia підтвердила масштабні контракти на H100/H200 для Azure та Google Cloud. "
             "Blackwell GPU рамп прискорюється — прогноз Q2 перевищив консенсус на 18%. "
             "Pre-market +4.2%.",
    ),
    NewsItem(
        ticker="MSFT", time="11:02",
        sentiment="positive", impact="high", score="+6.7",
        rec="buy", rec_label="Buy more",
        text="Azure Cloud +31% р/р, перевищив очікування. "
             "Copilot AI дав 1 млн корпоративних підписок. "
             "Дивіденд підвищено до $0.83/акція (+10%).",
    ),
    NewsItem(
        ticker="GOOGL", time="11:45",
        sentiment="neutral", impact="medium", score="-1.3",
        rec="watch", rec_label="Watch closely",
        text="Alphabet веде переговори щодо придбання HubSpot за ~$35 млрд. "
             "ЄС розпочав антимонопольне розслідування Google Search. "
             "Gemini показує сильні бенчмарки, але монетизація на ранній стадії.",
    ),
]

WATCHLIST: list[WatchItem] = [
    WatchItem("TSLA", 172.40, +3.2),
    WatchItem("META", 487.90, +1.8),
    WatchItem("AMZN", 183.50, -0.6),
    WatchItem("AMD",  162.30, -2.1),
]

CALENDAR: list[CalendarEvent] = [
    CalendarEvent("NVDA Earnings",    "28 Квіт", "#4F7FFF"),
    CalendarEvent("Fed Rate Decision","01 Трав", "#F5A623"),
    CalendarEvent("AAPL WWDC",        "05 Трав", "#2DD4A0"),
    CalendarEvent("MSFT Azure Summit","12 Трав", "#FF5B5B"),
]

RISK: RiskMetrics = RiskMetrics(
    beta=1.24,
    volatility=18.4,
    sharpe=1.87,
    max_drawdown=-14.2,
)