"""
ui/sidebar_panel.py
Sidebar panel: Watchlist + Calendar events.
Supports live price updates via update_watchlist().
"""
import customtkinter as ctk
from ui.theme import C, F
from ui.widgets import SectionPanel
from data.stub_data import WATCHLIST, CALENDAR


class SidebarPanel(SectionPanel):
    def __init__(self, master, **kwargs):
        super().__init__(master, title="Watchlist  ·  Calendar", **kwargs)
        self._watch_col = None
        self._build()

    def _build(self):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="x", padx=14, pady=(8, 12))

        # Watchlist column
        self._watch_col = ctk.CTkFrame(outer, fg_color="transparent")
        self._watch_col.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self._build_watchlist(self._watch_col)

        # Divider
        ctk.CTkFrame(outer, fg_color=C["border"], width=1).pack(
            side="left", fill="y", padx=4
        )

        # Calendar column
        cal_col = ctk.CTkFrame(outer, fg_color="transparent")
        cal_col.pack(side="left", fill="both", expand=True, padx=(16, 0))
        self._build_calendar(cal_col)

    # ── Watchlist ─────────────────────────────────────────────────────────────

    def _build_watchlist(self, parent):
        ctk.CTkLabel(
            parent, text="WATCHLIST",
            text_color=C["text_3"], font=F["tiny"],
        ).pack(anchor="w", pady=(0, 8))

        for w in WATCHLIST:
            self._build_watch_card(parent, w.ticker, w.price, w.chg)

    def _build_watch_card(self, parent, ticker: str, price: float, chg: float):
        card = ctk.CTkFrame(parent, fg_color=C["bg_card"], corner_radius=8)
        card.pack(fill="x", pady=3)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            inner, text=ticker,
            text_color=C["accent"], font=("SF Mono", 11, "bold"),
            width=44, anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            inner, text=f"${price:.2f}",
            text_color=C["text_1"], font=F["mono_sm"],
        ).pack(side="left", padx=(4, 0))

        chg_color = C["green"] if chg >= 0 else C["red"]
        chg_bg    = C["green_bg"] if chg >= 0 else C["red_bg"]
        sign      = "+" if chg >= 0 else ""

        badge = ctk.CTkFrame(inner, fg_color=chg_bg, corner_radius=5)
        badge.pack(side="right")
        ctk.CTkLabel(
            badge, text=f"{sign}{chg:.1f}%",
            text_color=chg_color, font=("SF Mono", 10, "bold"),
        ).pack(padx=8, pady=3)

    def update_watchlist(self, data: dict[str, dict]):
        """Rebuild watchlist with live prices. data = {ticker: {price, chg}}"""
        for widget in self._watch_col.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self._watch_col, text="WATCHLIST",
            text_color=C["text_3"], font=F["tiny"],
        ).pack(anchor="w", pady=(0, 8))

        for ticker, info in data.items():
            self._build_watch_card(
                self._watch_col,
                ticker,
                info["price"],
                info["chg"],
            )

    # ── Calendar ──────────────────────────────────────────────────────────────

    def _build_calendar(self, parent):
        ctk.CTkLabel(
            parent, text="UPCOMING EVENTS",
            text_color=C["text_3"], font=F["tiny"],
        ).pack(anchor="w", pady=(0, 8))

        for ev in CALENDAR:
            row = ctk.CTkFrame(parent, fg_color=C["bg_card"], corner_radius=8)
            row.pack(fill="x", pady=3)

            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=10, pady=7)

            dot = ctk.CTkFrame(
                inner, fg_color=ev.color,
                width=8, height=8, corner_radius=4,
            )
            dot.pack(side="left", padx=(0, 8))
            dot.pack_propagate(False)

            info = ctk.CTkFrame(inner, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(
                info, text=ev.label,
                text_color=C["text_2"], font=F["small"], anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                info, text=ev.date,
                text_color=C["text_3"], font=("SF Pro Text", 11), anchor="w",
            ).pack(anchor="w")