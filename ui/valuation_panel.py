"""
ui/valuation_panel.py
Компактний NPV / valuation блок для рішень buy / hold / reduce.
"""

import customtkinter as ctk

from data.stub_data import Stock
from ui.theme import C, F
from ui.widgets import Badge, SectionPanel, show_formula_modal
from utils.calc import valuation_rows


class ValuationPanel(SectionPanel):
    def __init__(self, master, portfolio: list[Stock], prices: dict[str, float], **kwargs):
        self._portfolio = portfolio
        self._prices = prices
        super().__init__(master, title="Target Gap · Valuation", subtitle="Analyst target · CAPM", **kwargs)
        self._build_formula_buttons()
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="x", padx=12, pady=(10, 12))
        self._render()

    def _build_formula_buttons(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(8, 0))
        for label, key in [("Gap", "npv"), ("Target", "target"), ("CAPM", "capm")]:
            ctk.CTkButton(
                bar,
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

    def _render(self):
        for widget in self._body.winfo_children():
            widget.destroy()

        rows = valuation_rows(self._portfolio, self._prices)
        for idx, row_data in enumerate(rows):
            card = ctk.CTkFrame(self._body, fg_color=C["bg_card"], corner_radius=8)
            card.grid(row=idx // 2, column=idx % 2, padx=4, pady=4, sticky="nsew")
            self._body.grid_columnconfigure(idx % 2, weight=1)

            self._build_card(card, row_data)

    def _build_card(self, card: ctk.CTkFrame, row_data: dict[str, float | str]):
        decision = str(row_data["decision"])
        style = {
            "buy": (C["green"], C["green_bg"]),
            "hold": (C["amber"], C["amber_bg"]),
            "reduce": (C["red"], C["red_bg"]),
        }.get(decision, (C["text_2"], C["bg_input"]))

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            head,
            text=str(row_data["ticker"]),
            text_color=C["text_1"],
            font=("SF Mono", 12, "bold"),
        ).pack(side="left")

        Badge(
            head,
            text=str(row_data["decision_label"]),
            fg=style[0],
            bg=style[1],
        ).pack(side="right")

        self._metric_row(
            card,
            "Fair value",
            f"${float(row_data['fair_value']):.2f}",
            C["text_1"],
        )
        self._metric_row(
            card,
            "Current",
            f"${float(row_data['price']):.2f}",
            C["text_2"],
        )

        npv = float(row_data["npv"])
        sign = "+" if npv >= 0 else ""
        npv_color = C["green"] if npv >= 0 else C["red"]
        self._metric_row(card, "NPV gap", f"{sign}${npv:.2f}", npv_color)

        gap = float(row_data["gap_pct"])
        gap_sign = "+" if gap >= 0 else ""
        self._metric_row(card, "Gap %", f"{gap_sign}{gap:.1f}%", npv_color)

        ctk.CTkLabel(
            card,
            text=f"Required r: {float(row_data['required_return']):.1f}% · {row_data.get('valuation_source', 'Valuation')}",
            text_color=C["text_3"],
            font=("SF Pro Text", 11),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(2, 8))

    def _metric_row(self, parent: ctk.CTkFrame, label: str, value: str, color: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=1)

        ctk.CTkLabel(
            row,
            text=label,
            text_color=C["text_3"],
            font=("SF Pro Text", 11),
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            row,
            text=value,
            text_color=color,
            font=F["mono_sm"],
            anchor="e",
        ).pack(side="right")

    def rebuild(self, portfolio: list[Stock], prices: dict[str, float]):
        self._portfolio = portfolio
        self._prices = prices
        self._render()

    def update_prices(self, prices: dict[str, float]):
        self._prices = prices
        self._render()
