"""
ui/news_panel.py
AI news feed with sentiment, metrics breakdown, and source links.
"""

import customtkinter as ctk
from ui.theme import C, F, SENTIMENT_STYLE, IMPACT_COLOR, REC_COLOR
from ui.widgets import SectionPanel, Badge, TickerTag
from data.stub_data import NewsItem
import webbrowser

_current_news: list[NewsItem] = []

FILTERS    = ["All", "Bullish", "Neutral", "Bearish"]
FILTER_MAP = {"Bullish": "positive", "Neutral": "neutral", "Bearish": "negative"}


class NewsFeedPanel(SectionPanel):
    def __init__(self, master, **kwargs):
        super().__init__(master, title="AI Agent · News & Recommendations", **kwargs)
        self._active = "All"
        self._overview = ctk.CTkFrame(self, fg_color="transparent")
        self._overview.pack(fill="x", padx=14, pady=(10, 4))
        self._build_filters()
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.render("All")

    # ── Agent overview ───────────────────────────────────────────────────────

    def _render_overview(self, items: list[NewsItem]):
        for widget in self._overview.winfo_children():
            widget.destroy()

        if not items:
            self._build_empty_overview()
            return

        scores = [self._score_value(item.score) for item in items]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        bullish = sum(1 for item in items if item.sentiment == "positive")
        bearish = sum(1 for item in items if item.sentiment == "negative")
        neutral = len(items) - bullish - bearish

        if avg_score >= 1.5:
            mood, mood_color, mood_bg = "Bullish", C["green"], C["green_bg"]
        elif avg_score <= -1.5:
            mood, mood_color, mood_bg = "Bearish", C["red"], C["red_bg"]
        else:
            mood, mood_color, mood_bg = "Neutral", C["amber"], C["amber_bg"]

        brief = ctk.CTkFrame(self._overview, fg_color=mood_bg, corner_radius=9)
        brief.pack(fill="x", pady=(0, 8))

        left = ctk.CTkFrame(brief, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        ctk.CTkLabel(
            left,
            text=f"Agent brief: {mood}",
            text_color=mood_color,
            font=("SF Pro Text", 14, "bold"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,
            text=f"{len(items)} ticker signals · {bullish} bullish · {neutral} neutral · {bearish} bearish",
            text_color=C["text_2"],
            font=("SF Pro Text", 11),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(
            brief,
            text=f"{avg_score:+.1f}",
            text_color=mood_color,
            font=("SF Mono", 22, "bold"),
        ).pack(side="right", padx=14, pady=10)

        scores_grid = ctk.CTkFrame(self._overview, fg_color="transparent")
        scores_grid.pack(fill="x")

        for idx, item in enumerate(sorted(items, key=lambda n: self._score_value(n.score), reverse=True)):
            score = self._score_value(item.score)
            color = C["green"] if score >= 1.5 else C["red"] if score <= -1.5 else C["amber"]
            card = ctk.CTkFrame(scores_grid, fg_color=C["bg_card"], corner_radius=8)
            card.grid(row=0, column=idx, padx=3, sticky="nsew")
            scores_grid.grid_columnconfigure(idx, weight=1)

            ctk.CTkLabel(
                card,
                text=item.ticker,
                text_color=C["text_2"],
                font=("SF Mono", 11, "bold"),
            ).pack(pady=(8, 0))
            ctk.CTkLabel(
                card,
                text=item.score,
                text_color=color,
                font=("SF Mono", 17, "bold"),
            ).pack()
            ctk.CTkLabel(
                card,
                text=item.rec_label,
                text_color=color,
                font=("SF Pro Text", 10),
            ).pack(pady=(0, 8))

    def _build_empty_overview(self):
        box = ctk.CTkFrame(self._overview, fg_color=C["bg_card"], corner_radius=9)
        box.pack(fill="x")
        ctk.CTkLabel(
            box,
            text="Agent brief will appear after scraping and AI analysis",
            text_color=C["text_3"],
            font=F["small"],
        ).pack(padx=12, pady=12)

    def _score_value(self, score: str) -> float:
        try:
            return float(str(score).replace("+", "").replace("−", "-"))
        except ValueError:
            return 0.0

    # ── Filters ───────────────────────────────────────────────────────────────

    def _build_filters(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(6, 6))
        self._filter_btns: dict[str, ctk.CTkButton] = {}

        for label in FILTERS:
            is_active = label == "All"
            btn = ctk.CTkButton(
                bar, text=label, width=72, height=26, font=F["tiny"],
                fg_color=C["accent"] if is_active else C["bg_card"],
                hover_color=C["accent_dim"],
                text_color="#FFFFFF" if is_active else C["text_3"],
                corner_radius=7, border_width=0,
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

    def render(self, filter_label: str = "All"):
        self._set_active_filter(filter_label)
        self._render_overview(_current_news)
        for w in self._scroll.winfo_children():
            w.destroy()

        sentiment_key = FILTER_MAP.get(filter_label)
        items = [
            n for n in _current_news
            if sentiment_key is None or n.sentiment == sentiment_key
        ]

        if not items:
            ctk.CTkLabel(
                self._scroll,
                text="No data yet — press Actualize to run AI analysis",
                text_color=C["text_3"], font=F["small"],
            ).pack(pady=30)
            return

        for item in items:
            self._build_card(item)

    def update_news(self, news: list[NewsItem]):
        global _current_news
        _current_news = news
        self.render(self._active)

    # ── Card ──────────────────────────────────────────────────────────────────

    def _build_card(self, item: NewsItem):
        card = ctk.CTkFrame(
            self._scroll, fg_color=C["bg_card"],
            corner_radius=10, border_width=1, border_color=C["border"],
        )
        card.pack(fill="x", pady=5)

        # Left accent bar
        _, fg_color, _ = SENTIMENT_STYLE[item.sentiment]
        accent_bar = ctk.CTkFrame(card, fg_color=fg_color, width=3, corner_radius=0)
        accent_bar.pack(side="left", fill="y")
        accent_bar.pack_propagate(False)

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

        # Row 2: badges
        row2 = ctk.CTkFrame(content, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 6))
        label, fg, bg = SENTIMENT_STYLE[item.sentiment]
        Badge(row2, label, fg, bg).pack(side="left", padx=(0, 5))
        signal_type = (getattr(item, "metrics", {}) or {}).get("signal_type")
        if signal_type:
            Badge(row2, str(signal_type), C["accent"], C["bg_tag"]).pack(side="left", padx=(0, 5))
        s_fg, s_bg = IMPACT_COLOR[item.impact]
        Badge(row2, f"Score {item.score}", s_fg, s_bg).pack(side="left", padx=(0, 5))
        r_fg, r_bg = REC_COLOR[item.rec]
        Badge(row2, item.rec_label, r_fg, r_bg).pack(side="left")

        # Row 3: summary text
        text_lbl = ctk.CTkLabel(
            content, text=item.text,
            text_color=C["text_2"], font=F["body"],
            wraplength=420, justify="left", anchor="w",
        )
        text_lbl.pack(fill="x", anchor="w", pady=(0, 8))

        reason_lbl = None
        if self._has_explanation(item):
            reason_row = ctk.CTkFrame(content, fg_color=C["bg_main"], corner_radius=6)
            reason_row.pack(fill="x", pady=(0, 6))
            reason_lbl = ctk.CTkLabel(
                reason_row,
                text=self._impact_reason(item),
                text_color=C["text_2"],
                font=F["tiny"],
                justify="left",
                anchor="w",
                wraplength=420,
            )
            reason_lbl.pack(fill="x", padx=10, pady=6)

        # Row 5: compact evidence metrics, max 4 items
        m = getattr(item, "metrics", {})
        if m and self._has_explanation(item):
            metrics_frame = ctk.CTkFrame(content, fg_color=C["bg_main"], corner_radius=6)
            metrics_frame.pack(fill="x", pady=(0, 6))

            metrics_text = "  ·  ".join(self._display_metrics(m))
            ctk.CTkLabel(
                metrics_frame, text=metrics_text,
                text_color=C["text_3"], font=F["tiny"],
                anchor="w",
            ).pack(anchor="w", padx=8, pady=4)

        # Row 6: sources
        sources = getattr(item, "sources", [])
        if sources:
            src_frame = ctk.CTkFrame(content, fg_color="transparent")
            src_frame.pack(fill="x")

            ctk.CTkLabel(
                src_frame, text="Sources:",
                text_color=C["text_3"], font=F["tiny"],
            ).pack(side="left", padx=(0, 6))

            for src in sources[:3]:
                title = (src.get("title") or "")[:40]
                link  = src.get("link", "")
                if not title:
                    continue
                lbl = ctk.CTkLabel(
                    src_frame, text=f"· {title}",
                    text_color=C["accent"], font=F["tiny"],
                    cursor="hand2",
                )
                lbl.pack(side="left", padx=(0, 8))
                if link:
                    lbl.bind("<Button-1>", lambda e, url=link: webbrowser.open(url))

        # update wraplength after render
        def _update_wrap(lbl=text_lbl, reason=reason_lbl):
            w = lbl.winfo_width()
            if w > 50:
                lbl.configure(wraplength=max(200, w - 10))
                if reason is not None:
                    reason.configure(wraplength=max(200, w - 10))
        card.after(100, _update_wrap)

    def _display_metrics(self, metrics: dict) -> list[str]:
        if metrics.get("signal_type") == "Market signal":
            items = ["Signal Market"]

            momentum = metrics.get("momentum_pct")
            if momentum is not None:
                items.append(f"P&L {float(momentum):+.1f}%")

            target_gap = metrics.get("target_gap_pct")
            if target_gap is not None:
                items.append(f"Target gap {float(target_gap):+.1f}%")

            beta = metrics.get("beta")
            if beta is not None:
                items.append(f"Beta {float(beta):.2f}")

            return items[:4]

        items = [
            f"Articles {metrics.get('relevant_articles', 0)}/{metrics.get('total_articles', 0)}"
        ]

        risk = metrics.get("avg_risk")
        if risk is not None:
            items.append(f"Risk {float(risk):.2f}")

        weight = float(metrics.get("signal_weight", 0) or 0)
        if weight > 0:
            items.append(f"News weight {weight:.2f}")

        momentum_used = float(metrics.get("momentum_used", 0) or 0)
        if abs(momentum_used) >= 0.05:
            items.append(f"Momentum nudge {momentum_used:+.1f}")

        return items[:4]

    def _has_explanation(self, item: NewsItem) -> bool:
        metrics = getattr(item, "metrics", {}) or {}
        return getattr(item, "article_count", 0) > 0 or bool(metrics.get("signal_type"))

    def _impact_reason(self, item: NewsItem) -> str:
        score = self._score_value(item.score)
        metrics = getattr(item, "metrics", {}) or {}

        if metrics.get("signal_type") == "Market signal":
            mechanism = "Why: fallback market/valuation signal used because direct news was not strong enough"
        elif item.sentiment == "positive":
            mechanism = "Why: positive catalyst supports growth or valuation"
        elif item.sentiment == "negative":
            mechanism = "Why: negative catalyst raises risk or weakens valuation support"
        else:
            mechanism = "Why: mixed signal, limited valuation impact"

        details = [mechanism]
        details.append(f"final score {score:+.1f}")

        return " · ".join(details)
