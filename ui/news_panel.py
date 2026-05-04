"""
ui/news_panel.py
AI-стрічка новин із sentiment, impact score та рекомендацією.
Виправлено: wraplength динамічний, top-row не переповнюється, текст читається.
"""

import customtkinter as ctk
from ui.theme import C, F, SENTIMENT_STYLE, IMPACT_COLOR, REC_COLOR
from ui.widgets import SectionPanel, Badge, TickerTag
from data.stub_data import NewsItem
_current_news = []

FILTERS = ["Всі", "Bullish", "Neutral", "Bearish"]
FILTER_MAP = {"Bullish": "positive", "Neutral": "neutral", "Bearish": "negative"}


class NewsFeedPanel(SectionPanel):
    def __init__(self, master, **kwargs):
        super().__init__(master, title="AI Агент · Новини & Рекомендації", **kwargs)
        self._active = "Всі"
        self._build_filters()
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.render("Всі")

    # ── Filter pills ──────────────────────────────────────────────────────────

    def _build_filters(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(6, 6))
        self._filter_btns: dict[str, ctk.CTkButton] = {}

        for label in FILTERS:
            is_active = label == "Всі"
            btn = ctk.CTkButton(
                bar,
                text=label,
                width=72,
                height=26,
                font=F["tiny"],
                fg_color=C["accent"] if is_active else C["bg_card"],
                hover_color=C["accent_dim"],
                text_color="#FFFFFF" if is_active else C["text_3"],
                corner_radius=7,
                border_width=0,
                command=lambda l=label: self.render(l),
            )
            btn.pack(side="left", padx=3)
            self._filter_btns[label] = btn

    def _set_active_filter(self, label: str):
        for lbl, btn in self._filter_btns.items():
            active = lbl == label
            btn.configure(
                fg_color=C["accent"] if active else C["bg_card"],
                text_color="#FFFFFF" if active else C["text_3"],
            )
        self._active = label

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, filter_label: str = "Всі"):
        self._set_active_filter(filter_label)
        for w in self._scroll.winfo_children():
            w.destroy()

        sentiment_key = FILTER_MAP.get(filter_label)
        items = [n for n in _current_news if sentiment_key is None or n.sentiment == sentiment_key]

        for item in items:
            self._build_card(item)

    def update_news(self, news: list[NewsItem]):
            global _current_news
            _current_news = news
            self.render(self._active)

    def _build_card(self, item: NewsItem):
        card = ctk.CTkFrame(
            self._scroll,
            fg_color=C["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=C["border"],
        )
        card.pack(fill="x", pady=5)

        # ── Left accent bar (sentiment color) ─────────────────────────────────
        _, fg_color, _ = SENTIMENT_STYLE[item.sentiment]
        accent_bar = ctk.CTkFrame(card, fg_color=fg_color, width=3, corner_radius=0)
        accent_bar.pack(side="left", fill="y")
        accent_bar.pack_propagate(False)

        # ── Content ───────────────────────────────────────────────────────────
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        # Row 1: ticker + time
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 6))

        TickerTag(row1, item.ticker).pack(side="left")

        ctk.CTkLabel(
            row1, text=item.time,
            text_color=C["text_3"], font=F["tiny"],
        ).pack(side="right")

        # Row 2: badges (sentiment | score | recommendation)
        row2 = ctk.CTkFrame(content, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 8))

        label, fg, bg = SENTIMENT_STYLE[item.sentiment]
        Badge(row2, label, fg, bg).pack(side="left", padx=(0, 5))

        s_fg, s_bg = IMPACT_COLOR[item.impact]
        Badge(row2, f"Score {item.score}", s_fg, s_bg).pack(side="left", padx=(0, 5))

        r_fg, r_bg = REC_COLOR[item.rec]
        Badge(row2, item.rec_label, r_fg, r_bg).pack(side="left")

        # Row 3: news text — wraplength прив'язаний до події після рендеру
        text_lbl = ctk.CTkLabel(
            content,
            text=item.text,
            text_color=C["text_2"],
            font=F["body"],
            wraplength=420,
            justify="left",
            anchor="w",
        )
        text_lbl.pack(fill="x", anchor="w")

        # Оновлюємо wraplength після того як панель відрендерилась
        def _update_wrap(lbl=text_lbl):
            w = lbl.winfo_width()
            if w > 50:
                lbl.configure(wraplength=max(200, w - 10))
        card.after(100, _update_wrap)

        