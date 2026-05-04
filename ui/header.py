"""
ui/header.py
Верхній хедер: логотип | SearchBar | live-статус + годинник
+ рядок метрик портфелю (4 картки).
"""

import customtkinter as ctk
from datetime import datetime

from ui.theme import C, F
from ui.widgets import MetricCard
from utils.calc import portfolio_metrics, daily_change


class Header(ctk.CTkFrame):
    """
    Хедер приймає on_stock_added — callback що передається до SearchBar.
    Імпорт SearchBar відкладений всередину методу, щоб уникнути
    циклічних залежностей при старті.
    """

    def __init__(self, master, on_stock_added=None, **kwargs):
        super().__init__(
            master,
            fg_color=C["bg_panel"],
            corner_radius=0,
            height=62,
            **kwargs,
        )
        self.pack_propagate(False)
        self._on_stock_added = on_stock_added
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22)

        # ── Logo (ліворуч) ────────────────────────────────────────────────────
        logo = ctk.CTkFrame(inner, fg_color="transparent")
        logo.pack(side="left", pady=14)
        ctk.CTkLabel(
            logo, text="●", text_color=C["accent"],
            font=("SF Pro Text", 20),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            logo, text="Portfolio Intelligence",
            text_color=C["text_1"], font=F["head"],
        ).pack(side="left")

        # ── Права частина: clock + status ─────────────────────────────────────
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", pady=14)

        self._dot = ctk.CTkLabel(
            right, text="●", text_color=C["green"],
            font=("SF Pro Text", 12),
        )
        self._dot.pack(side="left", padx=(0, 4))

        self._status = ctk.CTkLabel(
            right, text="Live",
            text_color=C["text_2"], font=F["small"],
        )
        self._status.pack(side="left", padx=(0, 18))

        self._clock = ctk.CTkLabel(
            right, text="",
            text_color=C["text_3"], font=F["mono"],
        )
        self._clock.pack(side="left")
        self._tick_clock()

        # ── SearchBar (по центру між logo і right) ────────────────────────────
        if self._on_stock_added is not None:
            # Відкладений імпорт щоб уникнути кола залежностей
            from ui.search_bar import SearchBar
            search = SearchBar(inner, on_stock_added=self._on_stock_added)
            search.pack(side="left", padx=(24, 0))

    # ── Clock ─────────────────────────────────────────────────────────────────

    def _tick_clock(self):
        self._clock.configure(
            text=datetime.now().strftime("%H:%M:%S  %d.%m.%Y")
        )
        self.after(1000, self._tick_clock)

    def set_status(self, live: bool):
        if live:
            self._dot.configure(text_color=C["green"])
            self._status.configure(text="Live")
        else:
            self._dot.configure(text_color=C["amber"])
            self._status.configure(text="Оновлення...")


# ── Metrics bar ───────────────────────────────────────────────────────────────

class MetricsBar(ctk.CTkFrame):
    def __init__(self, master, prices: dict[str, float], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._cards: dict[str, MetricCard] = {}
        self._build(prices)

    def _build(self, prices: dict[str, float]):
        m   = portfolio_metrics(prices)
        day = daily_change(prices)
        day_color = C["green"] if day >= 0 else C["red"]
        day_sign  = "+" if day >= 0 else ""

        specs = [
            ("total", "Вартість портфелю", f"${m['total_value']:,.0f}", None),
            ("pnl",   "P&L абсолютний",    f"+${m['pnl']:,.0f}",        C["green"]),
            ("ret",   "Дохідність",         f"+{m['pnl_pct']:.1f}%",     C["green"]),
            ("day",   "Денна зміна",        f"{day_sign}{day:.2f}%",    day_color),
        ]

        for key, label, value, color in specs:
            card = MetricCard(self, label=label, value=value, value_color=color)
            card.pack(side="left", fill="x", expand=True, padx=4)
            self._cards[key] = card

    def refresh(self, prices: dict[str, float]):
        m   = portfolio_metrics(prices)
        day = daily_change(prices)
        day_color = C["green"] if day >= 0 else C["red"]
        day_sign  = "+" if day >= 0 else ""

        self._cards["total"].update_value(f"${m['total_value']:,.0f}")
        self._cards["pnl"].update_value(f"+${m['pnl']:,.0f}")
        self._cards["ret"].update_value(f"+{m['pnl_pct']:.1f}%")
        self._cards["day"].update_value(f"{day_sign}{day:.2f}%", day_color)