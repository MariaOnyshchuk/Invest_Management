"""
ui/risk_panel.py
Блок ризик-метрик: Beta, Volatility, Sharpe, Max Drawdown
та секторна концентрація.
"""

import customtkinter as ctk
from ui.theme import C, F
from ui.widgets import SectionPanel
from data.stub_data import RISK
from utils.calc import sector_weights


class RiskPanel(SectionPanel):
    def __init__(self, master, prices: dict[str, float], **kwargs):
        super().__init__(master, title="Risk Metrics", **kwargs)
        self._build(prices)

    def _build(self, prices: dict[str, float]):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(8, 4))

        metrics = [
            ("Beta",         f"{RISK.beta:.2f}",        C["amber"]),
            ("Волатильність",f"{RISK.volatility:.1f}%",  C["amber"]),
            ("Sharpe Ratio", f"{RISK.sharpe:.2f}",       C["green"]),
            ("Max Drawdown", f"{RISK.max_drawdown:.1f}%",C["red"]),
        ]

        for i, (label, value, color) in enumerate(metrics):
            col = i % 2
            row = i // 2
            card = ctk.CTkFrame(body, fg_color=C["bg_card"], corner_radius=8)
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            body.grid_columnconfigure(col, weight=1)

            ctk.CTkLabel(card, text=label, text_color=C["text_3"],
                          font=F["tiny"]).pack(anchor="w", padx=10, pady=(8, 2))
            ctk.CTkLabel(card, text=value, text_color=color,
                          font=("SF Mono", 14, "bold")).pack(anchor="w", padx=10, pady=(0, 8))

        # Sector concentration
        sep = ctk.CTkFrame(self, fg_color=C["border"], height=1)
        sep.pack(fill="x", padx=14, pady=(4, 0))

        ctk.CTkLabel(
            self, text="Концентрація секторів",
            text_color=C["text_3"], font=F["tiny"],
        ).pack(anchor="w", padx=16, pady=(6, 4))

        sectors = sector_weights(prices)
        for name, pct in sorted(sectors.items(), key=lambda x: -x[1]):
            row_f = ctk.CTkFrame(self, fg_color="transparent")
            row_f.pack(fill="x", padx=16, pady=2)

            ctk.CTkLabel(
                row_f, text=name, text_color=C["text_2"],
                font=F["tiny"], width=64, anchor="w",
            ).pack(side="left")

            bar_bg = ctk.CTkFrame(row_f, fg_color=C["bg_card"],
                                   height=5, corner_radius=3)
            bar_bg.pack(side="left", fill="x", expand=True, padx=6)

            # Inner fill (approximate via nested frame)
            bar_fill = ctk.CTkFrame(
                bar_bg, fg_color=C["accent"],
                height=5, corner_radius=3,
                width=int(pct * 1.2),   # scale to rough px
            )
            bar_fill.place(x=0, y=0, relheight=1)

            ctk.CTkLabel(
                row_f, text=f"{pct:.0f}%", text_color=C["text_3"],
                font=F["tiny"], width=32, anchor="e",
            ).pack(side="left")