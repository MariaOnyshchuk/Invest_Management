"""
ui/risk_panel.py
Блок ризик-метрик: Beta, Volatility, Sharpe, Max Drawdown
та коротка agent-аналітика.
"""

import customtkinter as ctk
from ui.theme import C, F
from ui.widgets import Badge, SectionPanel
from data.stub_data import RISK
from utils.calc import sector_weights
from data.agent import generate_risk_metrics_analysis


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

        # Agent analytics
        sep = ctk.CTkFrame(self, fg_color=C["border"], height=1)
        sep.pack(fill="x", padx=14, pady=(4, 0))

        analysis = generate_risk_metrics_analysis(RISK, sector_weights(prices))
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
            text_color=C["text_3"], font=F["tiny"],
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
