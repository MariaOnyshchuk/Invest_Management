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
from ui.risk_panel import RiskPanel
from ui.news_panel import NewsFeedPanel
from ui.sidebar_panel import SidebarPanel
from ui.bottom_bar import BottomBar
from data.stub_data import PORTFOLIO, Stock


LIVE_REFRESH_MS = 60_000
LEFT_COL_W      = 500   # фіксована ширина лівої колонки


class ScrollableBody(ctk.CTkFrame):
    """
    Фрейм із вертикальним скролом через стандартний tk.Canvas.
    Дочірні елементи додаються до self.inner — звичайний CTkFrame
    з повною шириною canvas.
    Скрол: колесо миші + scrollbar праворуч.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        # Canvas — прозорий фон
        self._canvas = tk.Canvas(
            self,
            bg=C["bg_main"],
            highlightthickness=0,
            bd=0,
        )

        # Scrollbar
        self._sb = ctk.CTkScrollbar(
            self,
            orientation="vertical",
            command=self._canvas.yview,
            fg_color=C["bg_main"],
            button_color=C["bg_input"],
            button_hover_color=C["border"],
            width=8,
        )
        self._canvas.configure(yscrollcommand=self._sb.set)

        self._sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        # Внутрішній фрейм для контенту
        self.inner = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._win_id = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw",
        )

        # Оновлюємо scroll-регіон при зміні розміру inner
        self.inner.bind("<Configure>", self._on_inner_configure)
        # Оновлюємо ширину inner при зміні розміру canvas
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Скрол колесом миші — прив'язуємо до canvas і до всіх дочірніх
        self._canvas.bind_all("<MouseWheel>",     self._on_mousewheel)   # Windows/macOS
        self._canvas.bind_all("<Button-4>",        self._on_scroll_up)    # Linux
        self._canvas.bind_all("<Button-5>",        self._on_scroll_down)  # Linux

    def _on_inner_configure(self, _event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # inner завжди займає повну ширину canvas
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _on_mousewheel(self, event):
        # macOS delta кратний 1, Windows — 120
        delta = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(delta, "units")

    def _on_scroll_up(self, _event):
        self._canvas.yview_scroll(-1, "units")

    def _on_scroll_down(self, _event):
        self._canvas.yview_scroll(1, "units")


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
        self._bottom = BottomBar(self, on_refresh=self._on_manual_refresh)
        self._bottom.pack(fill="x", side="bottom", padx=18, pady=(0, 4))

        # Scrollable body — між хедером і bottom bar
        self._scroll_body = ScrollableBody(self)
        self._scroll_body.pack(fill="both", expand=True)

        inner = self._scroll_body.inner

        # Metrics bar
        self._metrics = MetricsBar(inner, self._prices)
        self._metrics.pack(fill="x", padx=18, pady=(12, 0))

        # Двоколонковий layout
        columns = ctk.CTkFrame(inner, fg_color="transparent")
        columns.pack(fill="x", padx=18, pady=12)

        left = ctk.CTkFrame(columns, fg_color="transparent", width=LEFT_COL_W)
        left.pack(side="left", fill="both", padx=(0, 10))
        left.pack_propagate(False)

        right = ctk.CTkFrame(columns, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # Ліва колонка
        self._chart = ChartPanel(left, height=380)
        self._chart.pack(fill="x", pady=(0, 10))
        # self._chart.pack_propagate(False)

        self._positions = PositionsPanel(left, portfolio=self._portfolio)
        self._positions.pack(fill="x", pady=(0, 10))

        # Права колонка
        # self._sidebar = SidebarPanel(right)
        # self._sidebar.pack(fill="x", pady=(0, 10))

        # self._risk = RiskPanel(right, self._prices)
        # self._risk.pack(fill="x", pady=(0, 10))
        watchlist_risk_row = ctk.CTkFrame(right, fg_color="transparent")
        watchlist_risk_row.pack(fill="x", pady=(0, 10))

        self._sidebar = SidebarPanel(watchlist_risk_row)
        self._sidebar.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self._risk = RiskPanel(watchlist_risk_row, self._prices)
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
        self._metrics.refresh(self._prices)

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
            from data.market_data import fetch_live_prices, fetch_watchlist_prices
            live     = fetch_live_prices()
            watchlist = fetch_watchlist_prices()
            if live:
                self.after(0, lambda: self._apply_live(live, watchlist))
        except Exception as e:
            print(f"[main] live fetch error: {e}")

    def _apply_live(self, live: dict[str, float], watchlist: dict):
        old = dict(self._prices)
        for ticker, price in live.items():
            if ticker in self._prices:
                self._prices[ticker] = price
                for s in self._portfolio:
                    if s.ticker == ticker:
                        s.price = price
        self._positions.update_prices(self._prices, old)
        self._metrics.refresh(self._prices)
        self._header.set_status(True)
        self._sidebar.update_watchlist(watchlist)

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