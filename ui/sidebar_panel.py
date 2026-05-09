"""
ui/sidebar_panel.py
Sidebar panel: Watchlist + Calendar events.
Supports live price updates via update_watchlist().
"""
import customtkinter as ctk
from ui.theme import C, F
from ui.widgets import SectionPanel
from data.stub_data import WATCHLIST, CALENDAR, Stock
from data.market_data import fetch_portfolio_calendar
from utils.calc import sector_weights


class SidebarPanel(SectionPanel):
    def __init__(self, master, prices: dict[str, float], portfolio: list[Stock], **kwargs):
        super().__init__(master, title="Watchlist  ·  Calendar", **kwargs)
        self._watch_col = None
        self._cal_col = None
        self._sector_col = None
        self._prices = prices
        self._portfolio = portfolio
        self._calendar_key = tuple(s.ticker for s in portfolio)
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
        self._cal_col = ctk.CTkFrame(outer, fg_color="transparent")
        self._cal_col.pack(side="left", fill="both", expand=True, padx=(16, 0))
        self._build_calendar(self._cal_col)

        # Sector concentration moved here from Risk Metrics
        ctk.CTkFrame(self, fg_color=C["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 8)
        )

        self._sector_col = ctk.CTkFrame(self, fg_color="transparent")
        self._sector_col.pack(fill="x", padx=16, pady=(0, 12))
        self._build_sector_concentration(self._sector_col, self._prices)

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

        try:
            events = fetch_portfolio_calendar(self._portfolio) or CALENDAR
        except Exception as e:
            print(f"[sidebar_panel] calendar fallback: {e}")
            events = CALENDAR

        for ev in events:
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

    # ── Sector concentration ──────────────────────────────────────────────────

    def _build_sector_concentration(self, parent, prices: dict[str, float]):
        ctk.CTkLabel(
            parent, text="КОНЦЕНТРАЦІЯ СЕКТОРІВ",
            text_color=C["text_3"], font=F["tiny"],
        ).pack(anchor="w", pady=(0, 6))

        sectors = sector_weights(prices, self._portfolio)
        for name, pct in sorted(sectors.items(), key=lambda x: -x[1]):
            row_f = ctk.CTkFrame(parent, fg_color="transparent")
            row_f.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row_f, text=name, text_color=C["text_2"],
                font=F["tiny"], width=64, anchor="w",
            ).pack(side="left")

            bar_bg = ctk.CTkFrame(
                row_f,
                fg_color=C["bg_card"],
                height=5,
                corner_radius=3,
            )
            bar_bg.pack(side="left", fill="x", expand=True, padx=6)

            bar_fill = ctk.CTkFrame(
                bar_bg,
                fg_color=C["accent"],
                height=5,
                corner_radius=3,
            )
            bar_fill.place(x=0, y=0, relheight=1, relwidth=min(pct / 100, 1))

            ctk.CTkLabel(
                row_f, text=f"{pct:.0f}%", text_color=C["text_3"],
                font=F["tiny"], width=32, anchor="e",
            ).pack(side="left")

    def update_sector_concentration(self, prices: dict[str, float], portfolio: list[Stock] | None = None):
        self._prices = prices
        if portfolio is not None:
            new_key = tuple(s.ticker for s in portfolio)
            self._portfolio = portfolio
            if new_key != self._calendar_key:
                self._calendar_key = new_key
                self.update_calendar()
        if not self._sector_col:
            return
        for widget in self._sector_col.winfo_children():
            widget.destroy()
        self._build_sector_concentration(self._sector_col, prices)

    def update_calendar(self):
        if not self._cal_col:
            return
        for widget in self._cal_col.winfo_children():
            widget.destroy()
        self._build_calendar(self._cal_col)
