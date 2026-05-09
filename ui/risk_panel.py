"""
ui/risk_panel.py
Блок ризик-метрик з інтегрованою концентрацією секторів.
"""

import customtkinter as ctk
from ui.theme import C, F
from ui.widgets import Badge, SectionPanel
from data.stub_data import RISK, Stock
from data.market_data import fetch_portfolio_risk_metrics
from utils.calc import sector_weights
from data.agent import generate_risk_metrics_analysis

class RiskPanel(SectionPanel):
    def __init__(self, master, prices: dict[str, float], portfolio: list[Stock], **kwargs):
        self._portfolio = portfolio
        self._prices = prices
        super().__init__(master, title="Risk Metrics", **kwargs)
        self._build()

    def _build(self):
        if not self._portfolio:
            ctk.CTkLabel(
                self,
                text="Risk metrics зʼявляться після додавання позицій.",
                text_color=C["text_3"],
                font=F["small"],
                wraplength=260,
                justify="center",
            ).pack(fill="x", padx=18, pady=28)
            return

        # 1. Fetch Data
        try:
            risk = fetch_portfolio_risk_metrics(self._portfolio)
            used_fallback = False
        except Exception as e:
            print(f"[risk_panel] risk metrics fallback: {e}")
            risk = RISK
            used_fallback = True

        # 2. Grid Metrics (Beta, Vol, etc.)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(8, 4))

        metrics = [
            ("Beta",         f"{risk.beta:.2f}",        C["amber"]),
            ("Волатильність",f"{risk.volatility:.1f}%",  C["amber"]),
            ("Sharpe Ratio", f"{risk.sharpe:.2f}",       C["green"] if risk.sharpe >= 1 else C["amber"]),
            ("Max Drawdown", f"{risk.max_drawdown:.1f}%",C["red"]),
        ]

        for i, (label, value, color) in enumerate(metrics):
            col, row = i % 2, i // 2
            card = ctk.CTkFrame(body, fg_color=C["bg_card"], corner_radius=8)
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            body.grid_columnconfigure(col, weight=1)

            ctk.CTkLabel(card, text=label, text_color=C["text_3"], font=F["tiny"]).pack(anchor="w", padx=10, pady=(8, 2))
            ctk.CTkLabel(card, text=value, text_color=color, font=("SF Mono", 14, "bold")).pack(anchor="w", padx=10, pady=(0, 8))

        # 3. Sector Concentration (The New Part)
        self._build_sector_section()

        # 4. Agent analytics
        sep = ctk.CTkFrame(self, fg_color=C["border"], height=1)
        sep.pack(fill="x", padx=14, pady=(12, 0))

        analysis = generate_risk_metrics_analysis(risk, sector_weights(self._prices, self._portfolio))
        severity = str(analysis["severity"])
        sev_style = {
            "low": (C["green"], C["green_bg"], "Low risk"),
            "medium": (C["amber"], C["amber_bg"], "Moderate"),
            "high": (C["red"], C["red_bg"], "Elevated"),
        }.get(severity, (C["text_2"], C["bg_card"], "Risk"))

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(8, 2))

        ctk.CTkLabel(head, text="Agent аналітика", text_color=C["text_1"], font=F["title"]).pack(side="left")
        Badge(head, text=sev_style[2], fg=sev_style[0], bg=sev_style[1]).pack(side="right")

        ai_card = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=8)
        ai_card.pack(fill="x", padx=14, pady=(6, 12))

        ctk.CTkLabel(ai_card, text=str(analysis["title"]), text_color=C["text_1"], font=("SF Pro Text", 13, "bold"), anchor="w").pack(anchor="w", padx=10, pady=(8, 2))
        ctk.CTkLabel(ai_card, text=str(analysis["summary"]), text_color=C["text_2"], font=F["small"], anchor="w", justify="left", wraplength=260).pack(fill="x", padx=10, pady=(0, 6))

        for bullet in analysis["bullets"]:
            ctk.CTkLabel(ai_card, text=f"• {bullet}", text_color=C["text_3"], font=F["tiny"], anchor="w", justify="left", wraplength=260).pack(fill="x", padx=10, pady=(0, 4))

    def _build_sector_section(self):
        """Internal helper to render the sector bars."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(container, text="КОНЦЕНТРАЦІЯ СЕКТОРІВ", text_color=C["text_3"], font=F["tiny"]).pack(anchor="w", pady=(0, 6))

        sectors = sector_weights(self._prices, self._portfolio)
        # Sort by weight descending
        for name, pct in sorted(sectors.items(), key=lambda x: -x[1]):
            row = ctk.CTkFrame(container, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(row, text=name, text_color=C["text_2"], font=F["tiny"], width=64, anchor="w").pack(side="left")

            bar_bg = ctk.CTkFrame(row, fg_color=C["bg_card"], height=5, corner_radius=3)
            bar_bg.pack(side="left", fill="x", expand=True, padx=6)

            bar_fill = ctk.CTkFrame(bar_bg, fg_color=C["accent"], height=5, corner_radius=3)
            bar_fill.place(x=0, y=0, relheight=1, relwidth=min(pct / 100, 1))

            ctk.CTkLabel(row, text=f"{pct:.0f}%", text_color=C["text_3"], font=F["tiny"], width=32, anchor="e").pack(side="left")

    def rebuild(self, prices: dict[str, float], portfolio: list[Stock] | None = None):
        if portfolio is not None:
            self._portfolio = portfolio
        self._prices = prices
        for widget in self.winfo_children()[2:]:
            widget.destroy()
        self._build()