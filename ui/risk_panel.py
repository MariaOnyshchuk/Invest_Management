"""
ui/risk_panel.py
Блок ризик-метрик: Beta, Volatility, Sharpe, Max Drawdown
та коротка agent-аналітика.
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

        used_fallback = False
        try:
            risk = fetch_portfolio_risk_metrics(self._portfolio)
        except Exception as e:
            print(f"[risk_panel] risk metrics fallback: {e}")
            risk = RISK
            used_fallback = True

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(8, 4))

        metrics = [
            ("Beta",         f"{risk.beta:.2f}",        C["amber"]),
            ("Волатильність",f"{risk.volatility:.1f}%",  C["amber"]),
            ("Sharpe Ratio", f"{risk.sharpe:.2f}",       C["green"] if risk.sharpe >= 1 else C["amber"]),
            ("Max Drawdown", f"{risk.max_drawdown:.1f}%",C["red"]),
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

        source_text = (
            "Source: fallback demo risk metrics"
            if used_fallback else
            "Source: Yahoo Finance, 1Y daily returns vs SPY"
        )
        source_color = C["amber"] if used_fallback else C["text_3"]
        ctk.CTkLabel(
            self,
            text=source_text,
            text_color=source_color,
            font=F["tiny"],
            anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 4))

        # Agent analytics
        sep = ctk.CTkFrame(self, fg_color=C["border"], height=1)
        sep.pack(fill="x", padx=14, pady=(4, 0))

        analysis = generate_risk_metrics_analysis(risk, sector_weights(self._prices, self._portfolio))
        severity = str(analysis["severity"])
        sev_style = {
            "low": (C["green"], C["green_bg"], "Low risk"),
            "medium": (C["amber"], C["amber_bg"], "Moderate"),
            "high": (C["red"], C["red_bg"], "Elevated"),
        }.get(severity, (C["text_2"], C["bg_card"], "Risk"))

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(8, 2))

        ctk.CTkLabel(
            head, text="Agent аналітика risk metrics",
            text_color=C["text_1"], font=F["title"],
        ).pack(side="left")

        Badge(head, text=sev_style[2], fg=sev_style[0], bg=sev_style[1]).pack(side="right")

        card = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=8)
        card.pack(fill="x", padx=14, pady=(6, 12))

        ctk.CTkLabel(
            card,
            text=str(analysis["title"]),
            text_color=C["text_1"],
            font=("SF Pro Text", 13, "bold"),
            anchor="w",
        ).pack(anchor="w", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            card,
            text=str(analysis["summary"]),
            text_color=C["text_2"],
            font=F["small"],
            anchor="w",
            justify="left",
            wraplength=260,
        ).pack(fill="x", padx=10, pady=(0, 6))

        for bullet in analysis["bullets"]:
            ctk.CTkLabel(
                card,
                text=f"• {bullet}",
                text_color=C["text_3"],
                font=F["tiny"],
                anchor="w",
                justify="left",
                wraplength=260,
            ).pack(fill="x", padx=10, pady=(0, 6))

    def rebuild(self, prices: dict[str, float], portfolio: list[Stock] | None = None):
        if portfolio is not None:
            self._portfolio = portfolio
        self._prices = prices
        for widget in self.winfo_children()[2:]:
            widget.destroy()
        self._build()
