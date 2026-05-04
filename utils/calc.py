"""
utils/calc.py
Розрахункові функції: метрики портфелю, сектори, генерація
псевдо-цін для price-ticker та дані для графіку.
"""

import random
import math
from datetime import datetime, timedelta
from data.stub_data import PORTFOLIO, Stock


# ── Метрики ───────────────────────────────────────────────────────────────────

def portfolio_metrics(prices: dict[str, float]) -> dict:
    """Повертає словник з total_value, pnl, pnl_pct."""
    total_val  = sum(s.qty * prices[s.ticker] for s in PORTFOLIO)
    total_cost = sum(s.qty * s.avg            for s in PORTFOLIO)
    pnl        = total_val - total_cost
    pnl_pct    = (pnl / total_cost) * 100 if total_cost else 0
    return {"total_value": total_val, "pnl": pnl, "pnl_pct": pnl_pct}


def allocation(prices: dict[str, float]) -> dict[str, float]:
    """Повертає частку кожного тікера у відсотках."""
    total = sum(s.qty * prices[s.ticker] for s in PORTFOLIO)
    return {s.ticker: (s.qty * prices[s.ticker] / total * 100) for s in PORTFOLIO}


def sector_weights(prices: dict[str, float]) -> dict[str, float]:
    """Повертає вагу кожного сектору у відсотках."""
    total = sum(s.qty * prices[s.ticker] for s in PORTFOLIO)
    weights: dict[str, float] = {}
    for s in PORTFOLIO:
        weights[s.sector] = weights.get(s.sector, 0) + s.qty * prices[s.ticker]
    return {k: v / total * 100 for k, v in weights.items()}


def daily_change(prices: dict[str, float]) -> float:
    """Псевдо-денна зміна (рандом у межах ±1.5%)."""
    return round(random.uniform(-1.5, 1.5), 2)


# ── Price ticker ──────────────────────────────────────────────────────────────

# def randomize_prices(prices: dict[str, float]) -> dict[str, float]:
    # """Повертає нові ціни з невеликим рандомним дрейфом ±0.8%."""
    # return {
    #     ticker: round(price * (1 + random.uniform(-0.008, 0.008)), 2)
    #     for ticker, price in prices.items()
    # }


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

    pv, bv = 100.0, 100.0
    for i in range(points, -1, -1):
        if cfg["unit"] == "minutes":
            dt = now - timedelta(minutes=i * abs(cfg.get("delta_min", -15)))
        else:
            dt = now - timedelta(days=i * abs(cfg.get("delta_days", 1)))
        labels.append(dt.strftime(cfg["fmt"]))
        pv = round(pv * (1 + random.uniform(-0.025, 0.030)), 4)
        bv = round(bv * (1 + random.uniform(-0.018, 0.022)), 4)
        port.append(pv)
        bench.append(bv)

    return labels, port, bench