"""
ui/bottom_bar.py
Bottom bar: last update time, real progress bar, buttons.
Progress reflects actual agent work via on_progress callback.
"""

import threading
import customtkinter as ctk
from datetime import datetime
from ui.theme import C, F
from data.agent import generate_recommendations


class BottomBar(ctk.CTkFrame):
    def __init__(self, master, on_refresh, get_portfolio=None, get_prices=None, **kwargs):
        super().__init__(
            master,
            fg_color=C["bg_panel"],
            corner_radius=12,
            border_width=1,
            border_color=C["border"],
            height=62,
            **kwargs,
        )
        self.pack_propagate(False)
        self._on_refresh  = on_refresh
        self._get_portfolio = get_portfolio
        self._get_prices = get_prices
        self._refreshing  = False
        self._build()

    def _build(self):
        # Progress bar — top of the bar, hidden until refresh
        self._progress = ctk.CTkProgressBar(
            self,
            height=3,
            fg_color=C["bg_card"],
            progress_color=C["accent"],
            corner_radius=0,
        )
        self._progress.set(0)

        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        self._inner.pack(fill="both", expand=True, padx=18, pady=10)

        # Left: last update + status label
        left = ctk.CTkFrame(self._inner, fg_color="transparent")
        left.pack(side="left")

        ctk.CTkLabel(
            left, text="Last updated:",
            text_color=C["text_3"], font=F["small"],
        ).pack(side="left", padx=(0, 6))

        self._upd_label = ctk.CTkLabel(
            left, text="—",
            text_color=C["text_2"], font=F["small"],
        )
        self._upd_label.pack(side="left")

        self._status_label = ctk.CTkLabel(
            left, text="",
            text_color=C["text_3"], font=F["tiny"],
        )
        self._status_label.pack(side="left", padx=(12, 0))

        # Right: buttons
        right = ctk.CTkFrame(self._inner, fg_color="transparent")
        right.pack(side="right")

        ctk.CTkButton(
            right, text="↓ Export", width=100, height=38,
            fg_color=C["bg_card"], hover_color=C["bg_input"],
            text_color=C["text_2"], font=F["body"],
            border_width=1, border_color=C["border"], corner_radius=9,
            command=self._export_stub,
        ).pack(side="left", padx=(0, 8))

        self._refresh_btn = ctk.CTkButton(
            right, text="⟳  Actualize", width=180, height=38,
            fg_color=C["accent"], hover_color=C["accent_dim"],
            text_color="#FFFFFF", font=("SF Pro Text", 13, "bold"),
            corner_radius=9,
            command=self._start_refresh,
        )
        self._refresh_btn.pack(side="left")

    # ── Refresh ───────────────────────────────────────────────────────────────

    def _start_refresh(self):
        if self._refreshing:
            return
        self._refreshing = True
        self._refresh_btn.configure(
            text="⟳  Analyzing...", state="disabled", fg_color=C["accent_dim"]
        )
        self._progress.set(0)
        self._progress.pack(fill="x", side="top", before=self._inner)
        self._set_status("Collecting news...")

        threading.Thread(target=self._run_agent, daemon=True).start()

    def _run_agent(self):
        """Runs in background thread. Passes on_progress callback to agent."""
        portfolio = self._get_portfolio() if self._get_portfolio else None
        prices = self._get_prices() if self._get_prices else None
        news = generate_recommendations(
            on_progress=self._on_progress,
            portfolio=portfolio,
            prices=prices,
        )
        self.after(0, lambda: self._finish_refresh(news))

    def _on_progress(self, current: int, total: int, status: str = ""):
        """Called from agent thread — schedules UI update on main thread."""
        def _update():
            pct = current / total if total > 0 else 0
            self._progress.set(pct)
            self._refresh_btn.configure(
                text=f"⟳  {current}/{total} articles"
            )
            if status:
                self._set_status(status)
        self.after(0, _update)

    def _set_status(self, text: str):
        self._status_label.configure(text=text)

    def _finish_refresh(self, news=None):
        self._refreshing = False
        self._upd_label.configure(text=datetime.now().strftime("%H:%M:%S"))
        self._refresh_btn.configure(
            text="⟳  Actualize", state="normal", fg_color=C["accent"]
        )
        self._progress.pack_forget()
        self._progress.set(0)
        self._set_status("")
        self._on_refresh(news)

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_stub(self):
        win = ctk.CTkToplevel(self)
        win.title("Export")
        win.geometry("340x180")
        win.configure(fg_color=C["bg_panel"])
        win.grab_set()
        ctk.CTkLabel(
            win, text="Export",
            text_color=C["text_1"], font=F["title"],
        ).pack(pady=(28, 6))
        ctk.CTkLabel(
            win,
            text="Will be available in the next version.\nCSV / PDF / Excel support.",
            text_color=C["text_2"], font=F["body"], justify="center",
        ).pack(pady=6)
        ctk.CTkButton(
            win, text="Close", fg_color=C["accent"], command=win.destroy
        ).pack(pady=14)
