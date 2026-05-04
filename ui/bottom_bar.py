"""
ui/bottom_bar.py
Нижній бар: час оновлення, прогрес-бар, кнопки.
"""

import customtkinter as ctk
from datetime import datetime
from ui.theme import C, F
import threading
from data.agent import generate_recommendations



class BottomBar(ctk.CTkFrame):
    def __init__(self, master, on_refresh, **kwargs):
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
        self._on_refresh = on_refresh
        self._refreshing = False
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=10)

        # Left: last update
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="Останнє оновлення:",
                      text_color=C["text_3"], font=F["small"]).pack(side="left", padx=(0, 6))
        self._upd_label = ctk.CTkLabel(left, text="—",
                                        text_color=C["text_2"], font=F["small"])
        self._upd_label.pack(side="left")

        # Right: progress + buttons
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")

        self._progress = ctk.CTkProgressBar(
            self,
            height=3,
            fg_color=C["bg_card"],
            progress_color=C["accent"],
            corner_radius=0,
        )
        self._progress.set(0)

        ctk.CTkButton(
            right, text="↓ Експорт", width=100, height=38,
            fg_color=C["bg_card"], hover_color=C["bg_input"],
            text_color=C["text_2"], font=F["body"],
            border_width=1, border_color=C["border"], corner_radius=9,
            command=self._export_stub,
        ).pack(side="left", padx=(0, 8))

        self._refresh_btn = ctk.CTkButton(
            right, text="⟳  Актуалізувати", width=180, height=38,
            fg_color=C["accent"], hover_color=C["accent_dim"],
            text_color="#FFFFFF", font=("SF Pro Text", 13, "bold"),
            corner_radius=9,
            command=self._start_refresh,
        )
        self._refresh_btn.pack(side="left")

    # ── Refresh logic ─────────────────────────────────────────────────────────
    def _start_refresh(self):
        if self._refreshing:
            return
        self._refreshing = True
        self._refresh_btn.configure(text="⟳  Завантаження...", 
                                    state="disabled", fg_color=C["accent_dim"])
        self._progress.pack(fill="x", side="top")
        self._progress.set(0)
        self._animate(0)
        # запускаємо агента в окремому потоці
        threading.Thread(target=self._run_agent, daemon=True).start()

    def _run_agent(self):
        news = generate_recommendations()
        # повертаємось в головний потік UI
        self.after(0, lambda: self._finish_refresh(news))

    def _finish_refresh(self, news=None):
        self._refreshing = False
        self._upd_label.configure(text=datetime.now().strftime("%H:%M:%S"))
        self._refresh_btn.configure(text="⟳  Актуалізувати", 
                                    state="normal", fg_color=C["accent"])
        self._progress.pack_forget()
        self._progress.set(0)
        self._on_refresh(news)  # передаємо новини вгору

    def _animate(self, step: int):
        total = 30
        if step <= total:
            self._progress.set(step / total)
            self.after(80, lambda: self._animate(step + 1))
        else:
            self._finish_refresh()

    def _on_manual_refresh(self, news=None):
        self._chart.refresh()
        if news:
            self._news_panel.update_news(news)

    # def _finish_refresh(self):
    #     self._refreshing = False
    #     self._upd_label.configure(text=datetime.now().strftime("%H:%M:%S"))
    #     self._refresh_btn.configure(text="⟳  Актуалізувати", state="normal",
    #                                  fg_color=C["accent"])
    #     self._progress.pack_forget()
    #     self._progress.set(0)
    #     self._on_refresh()

    # ── Export stub ───────────────────────────────────────────────────────────

    def _export_stub(self):
        win = ctk.CTkToplevel(self)
        win.title("Експорт")
        win.geometry("340x180")
        win.configure(fg_color=C["bg_panel"])
        win.grab_set()
        ctk.CTkLabel(win, text="Функція експорту",
                      text_color=C["text_1"], font=F["title"]).pack(pady=(28, 6))
        ctk.CTkLabel(win, text="Буде реалізована в наступній версії.\nПідтримка CSV / PDF / Excel.",
                      text_color=C["text_2"], font=F["body"], justify="center").pack(pady=6)
        ctk.CTkButton(win, text="Закрити", fg_color=C["accent"],
                       command=win.destroy).pack(pady=14)