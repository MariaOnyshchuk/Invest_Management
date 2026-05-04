"""
ui/theme.py
Кольорова палітра, шрифти та спільні константи оформлення.
"""

import customtkinter as ctk

# ── Режим ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Кольори ───────────────────────────────────────────────────────────────────
C = {
    "bg_main":    "#0B0E17",
    "bg_panel":   "#111520",
    "bg_card":    "#181D2E",
    "bg_input":   "#1E2440",
    "bg_tag":     "#1A2038",
    "accent":     "#4F7FFF",
    "accent_dim": "#2A4A99",
    "green":      "#2DD4A0",
    "green_bg":   "#0D2018",
    "red":        "#FF5B5B",
    "red_bg":     "#200D0D",
    "amber":      "#F5A623",
    "amber_bg":   "#2A1F06",
    "blue_score": "#5BAEFF",
    "blue_bg":    "#0D2035",
    "text_1":     "#F0F2FF",
    "text_2":     "#8B92B8",
    "text_3":     "#4A506A",
    "border":     "#252B45",
}

# ── Шрифти ────────────────────────────────────────────────────────────────────
F = {
    "head":      ("SF Pro Display", 20, "bold"),
    "title":     ("SF Pro Display", 13, "bold"),
    "body":      ("SF Pro Text",    13),
    "small":     ("SF Pro Text",    13),
    "tiny":      ("SF Pro Text",    13),
    "mono":      ("SF Mono",        13),
    "mono_sm":   ("SF Mono",        13),
    "mono_big":  ("SF Mono",        20, "bold"),
    "mono_med":  ("SF Mono",        15, "bold"),
}

# ── Sentiment → (icon, fg, bg) ────────────────────────────────────────────────
SENTIMENT_STYLE = {
    "positive": ("Bullish",  C["green"], C["green_bg"]),
    "neutral":  ("Neutral",  C["amber"], C["amber_bg"]),
    "negative": ("Bearish",  C["red"],   C["red_bg"]),
}

# ── Impact → badge color ──────────────────────────────────────────────────────
IMPACT_COLOR = {
    "high":   (C["blue_score"], C["blue_bg"]),
    "medium": ("#F0C040",       "#1F1A06"),
    "low":    ("#6AAA7A",       "#1A1F1A"),
}

# ── Rec → badge color ─────────────────────────────────────────────────────────
REC_COLOR = {
    "buy":    (C["green"], C["green_bg"]),
    "hold":   ("#7A85C5", "#1A1A2A"),
    "watch":  (C["amber"], C["amber_bg"]),
    "reduce": (C["red"],  C["red_bg"]),
}