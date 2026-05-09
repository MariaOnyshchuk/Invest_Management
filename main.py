"""
main.py
Точка входу. Збирає всі панелі в єдиний дашборд.
Весь контент (окрім хедера і bottom bar) — вертикально скролиться.

Запуск:
    pip install customtkinter matplotlib yfinance
    python main.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import threading
import tkinter as tk
import customtkinter as ctk

from ui.theme import C
from ui.header import Header, MetricsBar
from ui.chart_panel import ChartPanel
from ui.positions_panel import PositionsPanel
from ui.valuation_panel import ValuationPanel
from ui.risk_panel import RiskPanel
from ui.news_panel import NewsFeedPanel
from ui.sidebar_panel import SidebarPanel
from ui.bottom_bar import BottomBar
from data.stub_data import PORTFOLIO, Stock


LIVE_REFRESH_MS = 60_000
LEFT_COL_W      = 560   # фіксована ширина лівої колонки
class ScrollableBody(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color="transparent",
            scrollbar_button_color=C["bg_input"],
            scrollbar_button_hover_color=C["border"],
            **kwargs
        )

class PortfolioDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Portfolio Intelligence")
        self.geometry("1440x960")
        self.minsize(1280, 800)
        self.configure(fg_color=C["bg_main"])

        self._portfolio: list[Stock] = list(PORTFOLIO)
        self._prices: dict[str, float] = {s.ticker: s.price for s in self._portfolio}

        self._build()
        self._fetch_live(initial=True)
        self.after(LIVE_REFRESH_MS, self._schedule_live_fetch)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header — завжди зверху, не скролиться
        self._header = Header(self, on_stock_added=self._on_stock_added)
        self._header.pack(fill="x", side="top")

        # Bottom bar — завжди знизу, не скролиться
        self._bottom = BottomBar(
            self,
            on_refresh=self._on_manual_refresh,
            get_portfolio=lambda: list(self._portfolio),
            get_prices=lambda: dict(self._prices),
        )
        self._bottom.pack(fill="x", side="bottom", padx=18, pady=(0, 4))

        # Scrollable body
        self._scroll_body = ScrollableBody(self)
        self._scroll_body.pack(fill="both", expand=True)

        inner = self._scroll_body

        # Metrics bar
        self._metrics = MetricsBar(inner, self._prices, self._portfolio)
        self._metrics.pack(fill="x", padx=18, pady=(12, 0))

        # Columns
        columns = ctk.CTkFrame(inner, fg_color="transparent")
        columns.pack(fill="x", padx=18, pady=12)

        left = ctk.CTkFrame(columns, fg_color="transparent", width=LEFT_COL_W)
        left.pack(side="left", fill="both", padx=(0, 10))

        right = ctk.CTkFrame(columns, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # # Ліва колонка
        self._chart = ChartPanel(left, portfolio=self._portfolio, height=380)
        self._chart.pack(fill="x", pady=(0, 10))

        self._positions = PositionsPanel(
            left,
            portfolio=self._portfolio,
            on_remove=self._on_stock_removed,
        )
        self._positions.pack(fill="x", pady=(0, 10))

        self._valuation = ValuationPanel(left, portfolio=self._portfolio, prices=self._prices)
        self._valuation.pack(fill="x", pady=(0, 10))

        # Права колонка
        # self._sidebar = SidebarPanel(right)
        # self._sidebar.pack(fill="x", pady=(0, 10))

        # self._risk = RiskPanel(right, self._prices)
        # self._risk.pack(fill="x", pady=(0, 10))
        watchlist_risk_row = ctk.CTkFrame(right, fg_color="transparent")
        watchlist_risk_row.pack(fill="x", pady=(0, 10))

        self._sidebar = SidebarPanel(watchlist_risk_row, self._prices, self._portfolio)
        self._sidebar.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self._risk = RiskPanel(watchlist_risk_row, self._prices, self._portfolio)
        self._risk.pack(side="left", fill="both", expand=True)

        self._news_panel = NewsFeedPanel(right)
        self._news_panel.pack(fill="both", expand=True)

    # ── Додавання позиції через пошук ────────────────────────────────────────

    def _on_stock_added(self, stock: Stock):
        existing = next((s for s in self._portfolio if s.ticker == stock.ticker), None)
        if existing:
            total_cost = existing.qty * existing.avg + stock.qty * stock.avg
            existing.qty += stock.qty
            existing.avg = round(total_cost / existing.qty, 4)
            existing.price = stock.price
        else:
            self._portfolio.append(stock)
            self._prices[stock.ticker] = stock.price

        self._positions.rebuild(self._portfolio, self._prices)
        self._valuation.rebuild(self._portfolio, self._prices)
        self._chart.update_portfolio(self._portfolio)
        self._metrics.refresh(self._prices, self._portfolio)
        self._risk.rebuild(self._prices, self._portfolio)
        self._sidebar.update_sector_concentration(self._prices, self._portfolio)

    def _on_stock_removed(self, ticker: str):
        self._portfolio = [s for s in self._portfolio if s.ticker != ticker]
        self._prices.pop(ticker, None)

        self._positions.rebuild(self._portfolio, self._prices)
        self._valuation.rebuild(self._portfolio, self._prices)
        self._chart.update_portfolio(self._portfolio)
        self._metrics.refresh(self._prices, self._portfolio)
        self._risk.rebuild(self._prices, self._portfolio)
        self._sidebar.update_sector_concentration(self._prices, self._portfolio)

    # ── Live fetch ────────────────────────────────────────────────────────────

    def _schedule_live_fetch(self):
        self._fetch_live()
        self.after(LIVE_REFRESH_MS, self._schedule_live_fetch)

    def _fetch_live(self, initial: bool = False):
        if not initial:
            self._header.set_status(False)
        threading.Thread(target=self._live_worker, daemon=True).start()

    def _live_worker(self):
        try:
            from data.market_data import (
                fetch_live_prices_with_status,
                fetch_watchlist_prices_with_status,
            )
            live, live_fallback = fetch_live_prices_with_status(self._portfolio)
            watchlist, watch_fallback = fetch_watchlist_prices_with_status()
            if live or watchlist:
                self.after(
                    0,
                    lambda: self._apply_live(live, watchlist, live_fallback, watch_fallback),
                )
        except Exception as e:
            print(f"[main] live fetch error: {e}")

    def _apply_live(
        self,
        live: dict[str, float],
        watchlist: dict,
        live_fallback: set[str] | None = None,
        watch_fallback: set[str] | None = None,
    ):
        old = dict(self._prices)
        for ticker, price in live.items():
            if ticker in self._prices:
                self._prices[ticker] = price
                for s in self._portfolio:
                    if s.ticker == ticker:
                        s.price = price
        self._positions.update_prices(self._prices, old)
        self._valuation.update_prices(self._prices)
        self._metrics.refresh(self._prices, self._portfolio)
        fallback_count = len(live_fallback or set()) + len(watch_fallback or set())
        if fallback_count:
            self._header.set_status(True, f"Partial fallback ({fallback_count})")
        else:
            self._header.set_status(True)
        self._sidebar.update_watchlist(watchlist)
        self._sidebar.update_sector_concentration(self._prices, self._portfolio)

    # ── Manual refresh ────────────────────────────────────────────────────────

    def _on_manual_refresh(self, news=None):
        self._chart.refresh()
        if news:
            self._news_panel.update_news(news)

    def on_refresh(self, news=None):
        if news:
            self._news_panel.update_news(news)

if __name__ == "__main__":
    app = PortfolioDashboard()
    app.mainloop()
