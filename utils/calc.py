"""
utils/calc.py
Розрахункові функції: метрики портфелю, сектори, генерація
псевдо-цін для price-ticker та дані для графіку.
"""

from datetime import datetime, timedelta
from data.stub_data import PORTFOLIO, Stock
from data.market_data import (
    fetch_capm_assumptions,
    fetch_portfolio_risk_metrics,
    fetch_ticker_fundamentals,
    fetch_ticker_sector,
)


# ── Метрики ───────────────────────────────────────────────────────────────────

def portfolio_metrics(prices: dict[str, float], portfolio: list[Stock] | None = None) -> dict:
    """Повертає словник з total_value, pnl, pnl_pct."""
    stocks = PORTFOLIO if portfolio is None else portfolio
    total_val  = sum(s.qty * prices.get(s.ticker, s.price) for s in stocks)
    total_cost = sum(s.qty * s.avg for s in stocks)
    pnl        = total_val - total_cost
    pnl_pct    = (pnl / total_cost) * 100 if total_cost else 0
    return {"total_value": total_val, "pnl": pnl, "pnl_pct": pnl_pct}


def allocation(prices: dict[str, float], portfolio: list[Stock] | None = None) -> dict[str, float]:
    """Повертає частку кожного тікера у відсотках."""
    stocks = PORTFOLIO if portfolio is None else portfolio
    total = sum(s.qty * prices.get(s.ticker, s.price) for s in stocks)
    if total <= 0:
        return {s.ticker: 0.0 for s in stocks}
    return {
        s.ticker: (s.qty * prices.get(s.ticker, s.price) / total * 100)
        for s in stocks
    }


def sector_weights(prices: dict[str, float], portfolio: list[Stock] | None = None) -> dict[str, float]:
    """Повертає вагу кожного сектору у відсотках."""
    stocks = PORTFOLIO if portfolio is None else portfolio
    total = sum(s.qty * prices.get(s.ticker, s.price) for s in stocks)
    if total <= 0:
        return {}
    weights: dict[str, float] = {}
    for s in stocks:
        label = fetch_ticker_sector(s.ticker) or s.sector
        weights[label] = weights.get(label, 0) + s.qty * prices.get(s.ticker, s.price)
    return {k: v / total * 100 for k, v in weights.items()}


def stock_beta(ticker: str) -> float:
    """Повертає real beta з yfinance або нейтральну beta=1.0."""
    beta = fetch_ticker_fundamentals(ticker).get("beta")
    try:
        return float(beta) if beta is not None else 1.0
    except (TypeError, ValueError):
        return 1.0


def capm_expected_return(beta: float) -> float:
    """CAPM: E[r] = rf + beta * (Rm - rf), у відсотках."""
    assumptions = fetch_capm_assumptions()
    return assumptions["risk_free_rate"] + beta * assumptions["market_premium"]


def expected_position_return(stock: Stock, price: float) -> float:
    """Поточна дохідність позиції відносно середньої ціни входу, у відсотках."""
    return ((price - stock.avg) / stock.avg * 100) if stock.avg else 0.0


def capm_rows(
    portfolio: list[Stock],
    prices: dict[str, float],
) -> list[dict[str, float | str]]:
    """Рядки для аналізу позицій через CAPM та alpha."""
    rows = []
    allocs = allocation(prices, portfolio)
    for stock in portfolio:
        price = prices.get(stock.ticker, stock.price)
        beta = stock_beta(stock.ticker)
        actual_return = expected_position_return(stock, price)
        capm_return = capm_expected_return(beta)
        rows.append({
            "ticker": stock.ticker,
            "allocation": allocs.get(stock.ticker, 0.0),
            "return": actual_return,
            "beta": beta,
            "capm": capm_return,
            "alpha": actual_return - capm_return,
        })
    return rows


def portfolio_capm_summary(
    portfolio: list[Stock],
    prices: dict[str, float],
) -> dict[str, float]:
    """Зведені CAPM-показники портфеля."""
    rows = capm_rows(portfolio, prices)
    if not rows:
        assumptions = fetch_capm_assumptions()
        return {
            "beta": 0.0,
            "capm": 0.0,
            "return": 0.0,
            "alpha": 0.0,
            "risk_free_rate": assumptions["risk_free_rate"],
            "market_premium": assumptions["market_premium"],
        }
    portfolio_beta = sum(row["beta"] * row["allocation"] / 100 for row in rows)
    expected_return = capm_expected_return(portfolio_beta)
    # Alpha порівнюємо з 1Y trailing return портфеля (той самий горизонт, що й Rm у CAPM),
    # а не зі зваженим P&L від середньої ціни входу.
    try:
        actual_return = float(fetch_portfolio_risk_metrics(portfolio).trailing_annual_return)
    except Exception:
        actual_return = sum(row["return"] * row["allocation"] / 100 for row in rows)
    assumptions = fetch_capm_assumptions()
    return {
        "beta": portfolio_beta,
        "capm": expected_return,
        "return": actual_return,
        "alpha": actual_return - expected_return,
        "risk_free_rate": assumptions["risk_free_rate"],
        "market_premium": assumptions["market_premium"],
    }


def fair_value(ticker: str, price: float) -> float:
    """Оціночна ціна з analyst target або нейтральний fallback."""
    fundamentals = fetch_ticker_fundamentals(ticker)
    target = fundamentals.get("target_mean_price") or fundamentals.get("target_median_price")
    try:
        return float(target) if target is not None and float(target) > 0 else price
    except (TypeError, ValueError):
        return price


def valuation_rows(
    portfolio: list[Stock],
    prices: dict[str, float],
) -> list[dict[str, float | str]]:
    """Target gap / valuation rows для панелі рішень."""
    rows = []
    for stock in portfolio:
        price = prices.get(stock.ticker, stock.price)
        value = fair_value(stock.ticker, price)
        npv = value - price
        gap_pct = (npv / price * 100) if price else 0.0
        beta = stock_beta(stock.ticker)
        required_return = capm_expected_return(beta)

        if gap_pct >= 8:
            decision = "buy"
            decision_label = "Докупити"
        elif gap_pct <= -8:
            decision = "reduce"
            decision_label = "Зменшити"
        else:
            decision = "hold"
            decision_label = "Тримати"

        rows.append({
            "ticker": stock.ticker,
            "fair_value": value,
            "price": price,
            "npv": npv,
            "gap_pct": gap_pct,
            "required_return": required_return,
            "valuation_source": "Analyst target" if value != price else "No analyst target",
            "decision": decision,
            "decision_label": decision_label,
        })

    return sorted(rows, key=lambda row: row["gap_pct"], reverse=True)


def daily_change(prices: dict[str, float]) -> float:
    """Fallback для денної зміни, якщо market data недоступна."""
    return 0.0


# ── Дані для графіку ──────────────────────────────────────────────────────────

RANGE_CFG = {
    "1D":  {"points": 48, "delta_min": -15,    "unit": "minutes", "fmt": "%H:%M"},
    "1W":  {"points": 35, "delta_days": -1,    "unit": "days",    "fmt": "%d %b"},
    "1M":  {"points": 30, "delta_days": -1,    "unit": "days",    "fmt": "%d %b"},
    "3M":  {"points": 45, "delta_days": -2,    "unit": "days",    "fmt": "%d %b"},
    "1Y":  {"points": 52, "delta_days": -7,    "unit": "days",    "fmt": "%d %b"},
}

def generate_chart_data(range_key: str) -> tuple[list[str], list[float], list[float]]:
    """
    Генерує (labels, portfolio_values, benchmark_values).
    Значення нормовані на 100 на старті.
    """
    cfg = RANGE_CFG.get(range_key, RANGE_CFG["1M"])
    points = cfg["points"]
    now    = datetime.now()
    labels: list[str]  = []
    port:   list[float] = []
    bench:  list[float] = []

    for i in range(points, -1, -1):
        if cfg["unit"] == "minutes":
            dt = now - timedelta(minutes=i * abs(cfg.get("delta_min", -15)))
        else:
            dt = now - timedelta(days=i * abs(cfg.get("delta_days", 1)))
        labels.append(dt.strftime(cfg["fmt"]))
        port.append(100.0)
        bench.append(100.0)

    return labels, port, bench
