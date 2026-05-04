"""
ui/positions_panel.py
Таблиця позицій портфелю з динамічними цінами.
Підтримує rebuild() — перебудову після додавання нової позиції.
"""

import customtkinter as ctk
from ui.theme import C, F
from ui.widgets import SectionPanel, TickerTag
from data.stub_data import Stock
from utils.calc import allocation

COLS = [
    ("Тікер",  72),
    ("Назва",  130),
    ("Ціна",   80),
    ("P&L %",  68),
    ("Алок.",  68),
    ("Кіл-ть", 52),
]


class PositionsPanel(SectionPanel):
    def __init__(self, master, portfolio: list[Stock], **kwargs):
        self._portfolio = portfolio
        super().__init__(master, title="Позиції", subtitle=f"{len(portfolio)} активів", **kwargs)
        self._price_labels: dict[str, ctk.CTkLabel] = {}
        self._build_structure()
        self._render_rows(self._portfolio, {s.ticker: s.price for s in portfolio})

    # ── Незмінна структура (заголовки + скролл) ───────────────────────────────

    def _build_structure(self):
        hdr = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=0)
        hdr.pack(fill="x", padx=12, pady=(6, 2))
        for name, width in COLS:
            ctk.CTkLabel(
                hdr, text=name, text_color=C["text_3"],
                font=F["tiny"], width=width, anchor="w",
            ).pack(side="left", padx=6, pady=5)

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    # ── Рендер рядків ─────────────────────────────────────────────────────────

    def _render_rows(self, portfolio: list[Stock], prices: dict[str, float]):
        # Очищаємо
        for w in self._scroll.winfo_children():
            w.destroy()
        self._price_labels.clear()

        allocs = allocation(prices)

        for s in portfolio:
            p = prices.get(s.ticker, s.price)
            pnl_pct   = (p - s.avg) / s.avg * 100
            sign      = "+" if pnl_pct >= 0 else ""
            pnl_color = C["green"] if pnl_pct >= 0 else C["red"]
            alloc_pct = allocs.get(s.ticker, 0.0)

            row = ctk.CTkFrame(self._scroll, fg_color=C["bg_card"], corner_radius=7)
            row.pack(fill="x", pady=2)

            TickerTag(row, s.ticker).pack(side="left", padx=(8, 0), pady=6)

            ctk.CTkLabel(
                row, text=s.name[:17], text_color=C["text_2"],
                font=F["tiny"], width=122, anchor="w",
            ).pack(side="left", padx=6)

            price_lbl = ctk.CTkLabel(
                row, text=f"${p:.2f}", text_color=C["text_1"],
                font=F["mono_sm"], width=76, anchor="w",
            )
            price_lbl.pack(side="left", padx=4)
            self._price_labels[s.ticker] = price_lbl

            ctk.CTkLabel(
                row, text=f"{sign}{pnl_pct:.1f}%",
                text_color=pnl_color, font=("SF Mono", 11, "bold"),
                width=64, anchor="w",
            ).pack(side="left", padx=4)

            ctk.CTkLabel(
                row, text=f"{alloc_pct:.1f}%", text_color=C["text_2"],
                font=F["tiny"], width=64, anchor="w",
            ).pack(side="left", padx=4)

            ctk.CTkLabel(
                row, text=f"{s.qty} шт", text_color=C["text_3"],
                font=F["tiny"], width=48, anchor="w",
            ).pack(side="left", padx=4)

    # ── Публічні методи ───────────────────────────────────────────────────────

    def rebuild(self, portfolio: list[Stock], prices: dict[str, float]):
        """Повна перебудова після зміни складу портфелю."""
        self._portfolio = portfolio
        # Оновлюємо subtitle
        for w in self.winfo_children():
            if isinstance(w, ctk.CTkFrame):
                for child in w.winfo_children():
                    if isinstance(child, ctk.CTkLabel) and "активів" in (child.cget("text") or ""):
                        child.configure(text=f"{len(portfolio)} активів")
        self._render_rows(portfolio, prices)

    def update_prices(self, prices: dict[str, float], old_prices: dict[str, float]):
        """Flash-оновлення цін без повної перебудови."""
        for ticker, lbl in self._price_labels.items():
            new_p = prices.get(ticker)
            if new_p is None:
                continue
            old_p = old_prices.get(ticker, new_p)
            color = C["green"] if new_p >= old_p else C["red"]
            lbl.configure(text=f"${new_p:.2f}", text_color=color)
            lbl.after(1000, lambda l=lbl: l.configure(text_color=C["text_1"]))