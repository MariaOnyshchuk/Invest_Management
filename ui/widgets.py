"""
ui/widgets.py
Невеликі повторно-використовувані компоненти:
  - Badge (кольоровий ярлик)
  - SectionPanel (панель з заголовком)
  - MetricCard (картка з числом)
  - Divider (горизонтальна лінія)
"""

import customtkinter as ctk
from ui.theme import C, F


FORMULA_INFO = {
    "beta": {
        "title": "Beta",
        "definition": (
            "Beta показує, наскільки актив або портфель чутливий до руху ринку. "
            "β = 1 означає рух приблизно як ринок, β > 1 означає вищу амплітуду."
        ),
        "formula": "βp = Σ wi × βi",
        "tip": "У портфелі beta рахується як зважена beta позицій за їхніми частками.",
    },
    "capm": {
        "title": "CAPM",
        "definition": (
            "CAPM оцінює очікувану дохідність, яку інвестор має вимагати за ринковий ризик."
        ),
        "formula": "E[r] = rf + β × (Rm - rf)",
        "tip": "У цій панелі CAPM є річним required return, тому alpha коректна лише як орієнтовний сигнал.",
    },
    "alpha": {
        "title": "Alpha",
        "definition": (
            "Alpha показує надлишкову дохідність відносно того, що було б справедливо за CAPM."
        ),
        "formula": "α = r actual - E[r] CAPM",
        "tip": "Позитивна alpha підтримує позицію, але для точної оцінки потрібна дата входу і порівнянний горизонт.",
    },
    "npv": {
        "title": "Target Gap",
        "definition": (
            "Target gap показує різницю між analyst target price і поточною ринковою ціною."
        ),
        "formula": "Gap = Analyst target - Current price",
        "tip": "Додатний gap означає потенційний upside, відʼємний gap — ризик переоцінки. Це не DDM-модель.",
    },
    "target": {
        "title": "Analyst Target",
        "definition": (
            "Analyst target береться з фундаментальних даних Yahoo Finance, якщо він доступний."
        ),
        "formula": "Fair value = targetMeanPrice або targetMedianPrice",
        "tip": "Якщо target недоступний, модель повертає поточну ціну і показує нейтральний gap.",
    },
}


def show_formula_modal(master, key: str):
    data = FORMULA_INFO.get(key)
    if not data:
        return

    win = ctk.CTkToplevel(master)
    win.title(str(data["title"]))
    win.geometry("460x320")
    win.configure(fg_color=C["bg_panel"])
    win.grab_set()

    ctk.CTkLabel(
        win,
        text=str(data["title"]),
        text_color=C["text_1"],
        font=("SF Pro Display", 18, "bold"),
    ).pack(anchor="w", padx=24, pady=(22, 6))

    ctk.CTkLabel(
        win,
        text=str(data["definition"]),
        text_color=C["text_2"],
        font=F["body"],
        justify="left",
        wraplength=400,
    ).pack(anchor="w", padx=24, pady=(0, 14))

    formula_box = ctk.CTkFrame(win, fg_color=C["bg_card"], corner_radius=8)
    formula_box.pack(fill="x", padx=24, pady=(0, 14))
    ctk.CTkLabel(
        formula_box,
        text=str(data["formula"]),
        text_color=C["accent"],
        font=("SF Mono", 15, "bold"),
    ).pack(anchor="w", padx=14, pady=12)

    ctk.CTkLabel(
        win,
        text=str(data["tip"]),
        text_color=C["text_3"],
        font=F["small"],
        justify="left",
        wraplength=400,
    ).pack(anchor="w", padx=24, pady=(0, 16))

    ctk.CTkButton(
        win,
        text="Close",
        width=110,
        height=32,
        fg_color=C["accent"],
        hover_color=C["accent_dim"],
        command=win.destroy,
    ).pack(anchor="e", padx=24)


class Badge(ctk.CTkFrame):
    """Маленький кольоровий ярлик з текстом."""

    def __init__(self, master, text: str, fg: str, bg: str, **kwargs):
        super().__init__(master, fg_color=bg, corner_radius=5, **kwargs)
        ctk.CTkLabel(
            self, text=text, text_color=fg,
            font=F["tiny"], fg_color="transparent",
        ).pack(padx=7, pady=2)


class TickerTag(ctk.CTkFrame):
    """Синій моно-тег для тікера."""

    def __init__(self, master, ticker: str, **kwargs):
        super().__init__(master, fg_color=C["bg_tag"], corner_radius=5, **kwargs)
        ctk.CTkLabel(
            self, text=ticker, text_color=C["accent"],
            font=("SF Mono", 10, "bold"), fg_color="transparent",
        ).pack(padx=7, pady=2)


class SectionPanel(ctk.CTkFrame):
    """Панель з заголовком і підзаголовком (справа)."""

    def __init__(self, master, title: str, subtitle: str = "", **kwargs):
        super().__init__(
            master,
            fg_color=C["bg_panel"],
            corner_radius=12,
            border_width=1,
            border_color=C["border"],
            **kwargs,
        )
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            head, text=title, text_color=C["text_1"], font=F["title"],
        ).pack(side="left")

        if subtitle:
            ctk.CTkLabel(
                head, text=subtitle, text_color=C["text_3"], font=F["tiny"],
            ).pack(side="right", pady=2)

        # Розділювач
        ctk.CTkFrame(self, fg_color=C["border"], height=1).pack(fill="x", padx=16)

    def body(self) -> ctk.CTkFrame:
        """Повертає фрейм для вмісту всередині панелі."""
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True)
        return f


class MetricCard(ctk.CTkFrame):
    """Картка з підписом і великим числом."""

    def __init__(self, master, label: str, value: str, value_color: str | None = None, **kwargs):
        super().__init__(
            master,
            fg_color=C["bg_card"],
            corner_radius=10,
            **kwargs,
        )
        ctk.CTkLabel(
            self, text=label, text_color=C["text_3"],
            font=F["tiny"], anchor="w",
        ).pack(anchor="w", padx=12, pady=(10, 2))

        self._val_label = ctk.CTkLabel(
            self,
            text=value,
            text_color=value_color or C["text_1"],
            font=F["mono_med"],
            anchor="w",
        )
        self._val_label.pack(anchor="w", padx=12, pady=(0, 10))

    def update_value(self, value: str, color: str | None = None):
        self._val_label.configure(text=value)
        if color:
            self._val_label.configure(text_color=color)


class Divider(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=C["border"], height=1, **kwargs)
        self.pack(fill="x", padx=16, pady=4)
