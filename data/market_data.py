"""
data/market_data.py
Реальні дані через yfinance:
  - fetch_live_prices()   → поточні ціни для портфелю
  - search_ticker()       → пошук тікера за назвою/символом
  - fetch_ticker_info()   → ціна + назва + сектор для одного тікера
"""

import yfinance as yf
from functools import lru_cache
from data.stub_data import CalendarEvent, PORTFOLIO, RiskMetrics, Stock


RANGE_TO_YF = {
    "1D": ("1d", "15m", "%H:%M"),
    "1W": ("7d", "1h", "%d %b"),
    "1M": ("1mo", "1d", "%d %b"),
    "3M": ("3mo", "1d", "%d %b"),
    "1Y": ("1y", "1wk", "%d %b"),
}
TRADING_DAYS = 252
DEFAULT_RISK_FREE_RATE = 4.5
DEFAULT_MARKET_RETURN = 12.3


# ── Поточні ціни для всього портфелю ─────────────────────────────────────────
def fetch_watchlist_prices() -> dict[str, dict[str, float]]:
    return fetch_watchlist_prices_with_status()[0]


def fetch_watchlist_prices_with_status() -> tuple[dict[str, dict[str, float]], set[str]]:
    from data.stub_data import WATCHLIST
    tickers = [w.ticker for w in WATCHLIST]
    fallback_tickers: set[str] = set()
    try:
        data = yf.download(
            " ".join(tickers),
            period="2d",
            interval="1d",
            progress=False,
            group_by="ticker",
            auto_adjust=True,
        )
        result = {}
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    closes = data["Close"].dropna()
                else:
                    closes = data[ticker]["Close"].dropna()
                prev  = float(closes.iloc[-2])
                curr  = float(closes.iloc[-1])
                chg   = round((curr - prev) / prev * 100, 2)
                result[ticker] = {"price": round(curr, 2), "chg": chg}
            except Exception:
                w = next(w for w in WATCHLIST if w.ticker == ticker)
                result[ticker] = {"price": w.price, "chg": w.chg}
                fallback_tickers.add(ticker)
        return result, fallback_tickers
    except Exception as e:
        print(f"[market_data] watchlist error: {e}")
        return {w.ticker: {"price": w.price, "chg": w.chg} for w in WATCHLIST}, set(tickers)
    
def fetch_live_prices(portfolio: list[Stock] | None = None) -> dict[str, float]:
    return fetch_live_prices_with_status(portfolio)[0]


def fetch_live_prices_with_status(portfolio: list[Stock] | None = None) -> tuple[dict[str, float], set[str]]:
    """
    Повертає {ticker: price} для всіх позицій портфелю.
    Другим значенням повертає set тікерів, для яких використано fallback-ціни.
    """
    stocks = PORTFOLIO if portfolio is None else portfolio
    tickers = [s.ticker for s in stocks]
    if not tickers:
        return {}, set()
    fallback_tickers: set[str] = set()
    try:
        data = yf.download(
            tickers=" ".join(tickers),
            period="1d",
            interval="1m",
            progress=False,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
        )
        prices = {}
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    latest = float(data["Close"].dropna().iloc[-1])
                else:
                    latest = float(data[ticker]["Close"].dropna().iloc[-1])
                prices[ticker] = round(latest, 2)
            except Exception:
                prices[ticker] = next(s.price for s in stocks if s.ticker == ticker)
                fallback_tickers.add(ticker)
        return prices, fallback_tickers
    except Exception as e:
        print(f"[market_data] Yahoo Finance error: {e}")
        return {s.ticker: s.price for s in stocks}, set(tickers)


def _close_frame(tickers: list[str], period: str, interval: str):
    data = yf.download(
        " ".join(tickers),
        period=period,
        interval=interval,
        progress=False,
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        # prepost=True,
    )
    if len(tickers) == 1:
        return data["Close"].dropna().to_frame(tickers[0])
    return data.xs("Close", axis=1, level=1).dropna(how="all")


def fetch_portfolio_chart_data(
    portfolio: list[Stock],
    range_key: str,
) -> tuple[list[str], list[float], list[float]]:
    """Реальна нормована динаміка портфеля vs SPY через yfinance."""
    period, interval, fmt = RANGE_TO_YF.get(range_key, RANGE_TO_YF["1M"])
    tickers = [s.ticker for s in portfolio]
    if not tickers:
        raise ValueError("Portfolio is empty")
    quantities = {s.ticker: s.qty for s in portfolio}
    all_tickers = [*tickers, "SPY"]

    closes = _close_frame(all_tickers, period, interval).ffill().dropna(how="all")
    if closes.index.tz is not None:
        closes.index = closes.index.tz_convert("Europe/Kyiv")
    else:
        closes.index = closes.index.tz_localize("UTC").tz_convert("Europe/Kyiv")
    if closes.empty or "SPY" not in closes:
        raise ValueError("No historical data returned")

    portfolio_value = None
    for ticker in tickers:
        if ticker not in closes:
            continue
        series = closes[ticker].ffill() * quantities[ticker]
        portfolio_value = series if portfolio_value is None else portfolio_value.add(series, fill_value=0)

    if portfolio_value is None or portfolio_value.dropna().empty:
        raise ValueError("No portfolio history returned")

    combined = portfolio_value.to_frame("portfolio").join(closes["SPY"].rename("benchmark"), how="inner")
    combined = combined.dropna()
    if combined.empty:
        raise ValueError("No aligned chart data returned")

    port = (combined["portfolio"] / combined["portfolio"].iloc[0] * 100).round(4)
    bench = (combined["benchmark"] / combined["benchmark"].iloc[0] * 100).round(4)
    labels = [idx.strftime(fmt) for idx in combined.index]
    return labels, port.tolist(), bench.tolist()


def fetch_portfolio_day_change(portfolio: list[Stock]) -> float:
    """Реальна денна зміна портфеля за останні 2 денні close."""
    tickers = [s.ticker for s in portfolio]
    if not tickers:
        raise ValueError("Portfolio is empty")
    quantities = {s.ticker: s.qty for s in portfolio}
    closes = _close_frame(tickers, "5d", "1d").ffill().dropna(how="all")
    if len(closes) < 2:
        raise ValueError("Not enough daily data")

    values = None
    for ticker in tickers:
        if ticker not in closes:
            continue
        series = closes[ticker].ffill() * quantities[ticker]
        values = series if values is None else values.add(series, fill_value=0)

    if values is None or len(values.dropna()) < 2:
        raise ValueError("Not enough portfolio data")

    latest = float(values.dropna().iloc[-1])
    prev = float(values.dropna().iloc[-2])
    return round((latest - prev) / prev * 100, 2) if prev else 0.0


def fetch_portfolio_risk_metrics(portfolio: list[Stock]) -> RiskMetrics:
    """Beta, volatility, Sharpe, max drawdown з 1 року daily returns vs SPY."""
    tickers = [s.ticker for s in portfolio]
    if not tickers:
        raise ValueError("Portfolio is empty")
    quantities = {s.ticker: s.qty for s in portfolio}
    closes = _close_frame([*tickers, "SPY"], "1y", "1d").ffill().dropna(how="all")
    if closes.empty or "SPY" not in closes:
        raise ValueError("No risk history returned")

    portfolio_value = None
    for ticker in tickers:
        if ticker not in closes:
            continue
        series = closes[ticker].ffill() * quantities[ticker]
        portfolio_value = series if portfolio_value is None else portfolio_value.add(series, fill_value=0)

    if portfolio_value is None:
        raise ValueError("No portfolio risk series returned")

    combined = portfolio_value.to_frame("portfolio").join(closes["SPY"].rename("benchmark"), how="inner").dropna()
    returns = combined.pct_change().dropna()
    if len(returns) < 20:
        raise ValueError("Not enough returns for risk metrics")

    port_ret = returns["portfolio"]
    bench_ret = returns["benchmark"]
    variance = float(bench_ret.var())
    beta = float(port_ret.cov(bench_ret) / variance) if variance else 1.0
    volatility = float(port_ret.std() * (TRADING_DAYS ** 0.5) * 100)
    annual_return = float((combined["portfolio"].iloc[-1] / combined["portfolio"].iloc[0] - 1) * 100)
    risk_free = fetch_capm_assumptions()["risk_free_rate"]
    sharpe = (annual_return - risk_free) / volatility if volatility else 0.0
    running_max = combined["portfolio"].cummax()
    drawdown = (combined["portfolio"] / running_max - 1) * 100
    max_drawdown = float(drawdown.min())

    return RiskMetrics(
        beta=round(beta, 2),
        volatility=round(volatility, 1),
        sharpe=round(sharpe, 2),
        max_drawdown=round(max_drawdown, 1),
    )


@lru_cache(maxsize=256)
def fetch_ticker_fundamentals(ticker: str) -> dict:
    """Lightweight cached yfinance fundamentals used by CAPM/valuation."""
    try:
        info = yf.Ticker(ticker.upper()).info
        return {
            "beta": info.get("beta"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_median_price": info.get("targetMedianPrice"),
            "current_price": (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("previousClose")
            ),
        }
    except Exception as e:
        print(f"[market_data] fundamentals fallback for {ticker}: {e}")
        return {}


@lru_cache(maxsize=1)
def fetch_capm_assumptions() -> dict[str, float]:
    """Risk-free rate from ^TNX and 1Y SPY return for market return."""
    risk_free = DEFAULT_RISK_FREE_RATE
    market_return = DEFAULT_MARKET_RETURN

    try:
        tnx = yf.Ticker("^TNX").history(period="5d", interval="1d")
        if not tnx.empty:
            risk_free = round(float(tnx["Close"].dropna().iloc[-1]), 2)
    except Exception as e:
        print(f"[market_data] ^TNX fallback: {e}")

    try:
        spy = yf.Ticker("SPY").history(period="1y", interval="1d", auto_adjust=True)
        closes = spy["Close"].dropna()
        if len(closes) >= 2:
            market_return = round((float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100, 2)
    except Exception as e:
        print(f"[market_data] SPY return fallback: {e}")

    return {
        "risk_free_rate": risk_free,
        "market_return": market_return,
        "market_premium": market_return - risk_free,
    }


def fetch_portfolio_calendar(portfolio: list[Stock]) -> list[CalendarEvent]:
    """Пробує отримати upcoming earnings calendar для поточного портфеля."""
    events: list[CalendarEvent] = []
    colors = ["#4F7FFF", "#F5A623", "#2DD4A0", "#FF5B5B", "#7C6AF7"]

    for idx, stock in enumerate(portfolio):
        try:
            calendar = yf.Ticker(stock.ticker).calendar
            earnings_date = None

            if isinstance(calendar, dict):
                earnings_date = calendar.get("Earnings Date") or calendar.get("EarningsDate")
            else:
                try:
                    earnings_date = calendar.loc["Earnings Date"][0]
                except Exception:
                    earnings_date = None

            if isinstance(earnings_date, (list, tuple)) and earnings_date:
                earnings_date = earnings_date[0]

            if earnings_date is None:
                continue

            try:
                date_label = earnings_date.strftime("%d %b")
            except Exception:
                date_label = str(earnings_date)[:10]

            events.append(
                CalendarEvent(
                    label=f"{stock.ticker} Earnings",
                    date=date_label,
                    color=colors[idx % len(colors)],
                )
            )
        except Exception as e:
            print(f"[market_data] calendar fallback for {stock.ticker}: {e}")

    return events


# ── Пошук тікера ──────────────────────────────────────────────────────────────

def search_ticker(query: str) -> list[dict]:
    """
    Шукає компанії за символом або назвою.
    Повертає список словників:
      [{"ticker": "AAPL", "name": "Apple Inc.", "exchange": "NMS", "type": "EQUITY"}, ...]
    Максимум 8 результатів.
    """
    if not query or len(query.strip()) < 1:
        return []
    try:
        results = yf.Search(query.strip(), max_results=8)
        quotes = results.quotes  # list of dicts
        out = []
        for q in quotes:
            symbol = q.get("symbol", "")
            name   = q.get("longname") or q.get("shortname") or symbol
            exch   = q.get("exchDisp", "")
            qtype  = q.get("quoteType", "")
            # Фільтруємо: тільки акції та ETF
            if qtype not in ("EQUITY", "ETF"):
                continue
            out.append({
                "ticker":   symbol,
                "name":     name,
                "exchange": exch,
                "type":     qtype,
            })
        return out
    except Exception as e:
        print(f"[market_data] Search error: {e}")
        return []


# ── Деталі одного тікера ──────────────────────────────────────────────────────

def fetch_ticker_info(ticker: str) -> dict | None:
    """
    Повертає словник з базовою інформацією про тікер:
      {
        "ticker":   "AAPL",
        "name":     "Apple Inc.",
        "price":    189.30,
        "sector":   "Technology",
        "currency": "USD",
        "market_cap": 2_900_000_000_000,
      }
    Або None при помилці.
    """
    try:
        t = yf.Ticker(ticker.upper())
        info = t.info

        # Поточна ціна
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        if price is None:
            # Fallback: остання 1-хвилинна свічка
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                price = round(float(hist["Close"].iloc[-1]), 2)

        return {
            "ticker":     ticker.upper(),
            "name":       info.get("longName") or info.get("shortName") or ticker,
            "price":      round(float(price), 2) if price else 0.0,
            "sector":     info.get("sector") or info.get("category") or "Other",
            "currency":   info.get("currency", "USD"),
            "market_cap": info.get("marketCap"),
        }
    except Exception as e:
        print(f"[market_data] fetch_ticker_info({ticker}) error: {e}")
        return None
