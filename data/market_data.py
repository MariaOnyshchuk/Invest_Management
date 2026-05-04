"""
data/market_data.py
Реальні дані через yfinance:
  - fetch_live_prices()   → поточні ціни для портфелю
  - search_ticker()       → пошук тікера за назвою/символом
  - fetch_ticker_info()   → ціна + назва + сектор для одного тікера
"""

import yfinance as yf
from data.stub_data import PORTFOLIO, Stock


# ── Поточні ціни для всього портфелю ─────────────────────────────────────────
def fetch_watchlist_prices() -> dict[str, float]:
    from data.stub_data import WATCHLIST
    tickers = [w.ticker for w in WATCHLIST]
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
        return result
    except Exception as e:
        print(f"[market_data] watchlist error: {e}")
        return {w.ticker: {"price": w.price, "chg": w.chg} for w in WATCHLIST}
    
def fetch_live_prices() -> dict[str, float]:
    """
    Повертає {ticker: price} для всіх позицій портфелю.
    При помилці — повертає stub-ціни.
    """
    tickers = [s.ticker for s in PORTFOLIO]
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
                prices[ticker] = next(s.price for s in PORTFOLIO if s.ticker == ticker)
        return prices
    except Exception as e:
        print(f"[market_data] Yahoo Finance error: {e}")
        return {s.ticker: s.price for s in PORTFOLIO}


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