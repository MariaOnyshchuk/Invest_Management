"""
ui/positions_panel.py
Таблиця позицій портфелю з динамічними цінами.
Підтримує rebuild() — перебудову після додавання нової позиції.
"""

import customtkinter as ctk
from ui.theme import C, F
from ui.widgets import SectionPanel, TickerTag, show_formula_modal
from data.stub_data import Stock
from utils.calc import allocation, portfolio_capm_summary

COLS = [
    ("Тікер",  72),
    ("Назва",  130),
    ("Ціна",   80),
    ("P&L %",  68),
    ("Алок.",  68),
    ("Кіл-ть", 52),
    ("",       34),
]


class PositionsPanel(SectionPanel):
    def __init__(self, master, portfolio: list[Stock], on_remove=None, **kwargs):
        self._portfolio = portfolio
        self._on_remove = on_remove
        super().__init__(master, title="Позиції", subtitle=f"{len(portfolio)} активів", **kwargs)
        self._price_labels: dict[str, ctk.CTkLabel] = {}
        self._summary_labels: dict[str, ctk.CTkLabel] = {}
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
            self, fg_color="transparent", corner_radius=0, height=260,
        )
        self._scroll.pack(fill="x", padx=12, pady=(0, 10))

        info_bar = ctk.CTkFrame(self, fg_color="transparent")
        info_bar.pack(fill="x", padx=12, pady=(0, 6))
        for label, key in [("Beta", "beta"), ("CAPM", "capm"), ("Alpha", "alpha")]:
            ctk.CTkButton(
                info_bar,
                text=label,
                width=58,
                height=24,
                fg_color=C["bg_card"],
                hover_color=C["bg_input"],
                text_color=C["text_2"],
                font=("SF Pro Text", 11),
                corner_radius=6,
                command=lambda k=key: show_formula_modal(self, k),
            ).pack(side="left", padx=(0, 5))

        self._summary = ctk.CTkFrame(self, fg_color="transparent")
        self._summary.pack(fill="x", padx=12, pady=(0, 12))
        for key, label in [
            ("beta", "beta портфеля"),
            ("capm", "E[r] CAPM"),
            ("alpha", "alpha портфеля"),
        ]:
            card = ctk.CTkFrame(self._summary, fg_color=C["bg_card"], corner_radius=7, height=66)
            card.pack(side="left", fill="x", expand=True, padx=2)
            card.pack_propagate(False)
            ctk.CTkLabel(
                card, text=label, text_color=C["text_3"],
                font=("SF Pro Text", 11), anchor="w",
            ).pack(anchor="w", padx=8, pady=(8, 1))
            value = ctk.CTkLabel(
                card, text="—", text_color=C["text_1"],
                font=F["mono_sm"], anchor="w",
            )
            value.pack(anchor="w", padx=8, pady=(0, 8))
            self._summary_labels[key] = value

    # ── Рендер рядків ─────────────────────────────────────────────────────────

    def _render_rows(self, portfolio: list[Stock], prices: dict[str, float]):
        # Очищаємо
        for w in self._scroll.winfo_children():
            w.destroy()
        self._price_labels.clear()

        allocs = allocation(prices, portfolio)

        if not portfolio:
            ctk.CTkLabel(
                self._scroll,
                text="Портфель порожній. Додайте актив через пошук у хедері.",
                text_color=C["text_3"],
                font=F["small"],
                wraplength=460,
                justify="center",
            ).pack(pady=28)
            self._render_summary(portfolio, prices)
            return

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

            remove_btn = ctk.CTkButton(
                row,
                text="×",
                width=26,
                height=24,
                fg_color="transparent",
                hover_color=C["red_bg"],
                text_color=C["text_3"],
                font=("SF Pro Text", 15, "bold"),
                corner_radius=6,
                command=lambda ticker=s.ticker: self._request_remove(ticker),
            )
            remove_btn.pack(side="right", padx=(0, 6))

        self._render_summary(portfolio, prices)

    def _render_summary(self, portfolio: list[Stock], prices: dict[str, float]):
        if not portfolio:
            for key in ("beta", "capm", "alpha"):
                self._summary_labels[key].configure(text="—", text_color=C["text_3"])
            return

        summary = portfolio_capm_summary(portfolio, prices)
        alpha = summary["alpha"]
        alpha_color = C["green"] if alpha >= 0 else C["red"]
        alpha_sign = "+" if alpha >= 0 else ""

        self._summary_labels["beta"].configure(
            text=f"{summary['beta']:.2f}", text_color=C["text_1"],
        )
        self._summary_labels["capm"].configure(
            text=f"{summary['capm']:.1f}%", text_color=C["text_1"],
        )
        self._summary_labels["alpha"].configure(
            text=f"{alpha_sign}{alpha:.1f}%", text_color=alpha_color,
        )

    def _request_remove(self, ticker: str):
        if self._on_remove:
            self._on_remove(ticker)

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
        """Оновлення цін із перерахунком P&L, allocation, CAPM та alpha."""
        self._render_rows(self._portfolio, prices)
        for ticker, lbl in self._price_labels.items():
            new_p = prices.get(ticker)
            if new_p is None:
                continue
            old_p = old_prices.get(ticker, new_p)
            color = C["green"] if new_p >= old_p else C["red"]
            lbl.configure(text=f"${new_p:.2f}", text_color=color)
            lbl.after(1000, lambda l=lbl: l.configure(text_color=C["text_1"]))
