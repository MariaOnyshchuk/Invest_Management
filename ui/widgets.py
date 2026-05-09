"""
ui/widgets.py
"""
import io
import customtkinter as ctk
from PIL import Image as PILImage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ui.theme import C, F

FORMULA_INFO = {
    "beta": {
        "title": "Beta",
        "definition": (
            "Beta показує, наскільки актив або портфель чутливий до руху ринку. "
            "β = 1 означає рух приблизно як ринок, β > 1 означає вищу амплітуду."
        ),
        "latex": r"$\beta_p = \sum_{i} w_i \cdot \beta_i$",
        "tip": "У портфелі beta рахується як зважена beta позицій за їхніми частками.",
    },
    "capm": {
        "title": "CAPM",
        "definition": (
            "CAPM оцінює очікувану дохідність, яку інвестор має вимагати за ринковий ризик."
        ),
        "latex": r"$E[r] = r_f + \beta \cdot (R_m - r_f)$",
        "tip": "r_f з ^TNX, R_m — фактична 1Y дохідність SPY; усе в річних відсотках.",
    },
    "alpha": {
        "title": "Alpha",
        "definition": (
            "Alpha показує надлишкову дохідність відносно того, що було б справедливо за CAPM."
        ),
        "latex": r"$\alpha = r_{\text{actual}} - E[r]_{\text{CAPM}}$",
        "tip": "Фактична дохідність — 1Y trailing по історичних цінах портфеля (як і для beta/vol у Risk).",
    },
    "npv": {
        "title": "Target Gap",
        "definition": (
            "Target gap показує різницю між analyst target price і поточною ринковою ціною."
        ),
        "latex": r"$\text{Gap} = P_{\text{target}} - P_{\text{current}}$",
        "tip": "Додатний gap означає потенційний upside, відʼємний gap — ризик переоцінки. Це не DDM-модель.",
    },
    "target": {
        "title": "Analyst Target",
        "definition": (
            "Analyst target береться з фундаментальних даних Yahoo Finance, якщо він доступний."
        ),
        "latex": r"$P_{\text{fair}} = \text{targetMeanPrice}$",
        "tip": "Якщо target недоступний, модель повертає поточну ціну і показує нейтральний gap.",
    },
}


def _render_latex(latex: str, accent_color: str, bg_color: str) -> ctk.CTkImage:
    """Render a LaTeX string to a CTkImage using matplotlib."""
    fig, ax = plt.subplots(figsize=(5, 0.7))
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.axis("off")
    ax.text(
        0.5, 0.5, latex,
        fontsize=18,
        color=accent_color,
        ha="center", va="center",
        transform=ax.transAxes,
    )
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=bg_color, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    pil_img = PILImage.open(buf)
    # Scale to fit modal width (~412px) while keeping crisp rendering
    w, h = pil_img.size
    scale = min(412 / w, 1.0)
    display_size = (int(w * scale), int(h * scale))
    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=display_size)


def show_formula_modal(master, key: str):
    data = FORMULA_INFO.get(key)
    if not data:
        return

    win = ctk.CTkToplevel(master)
    win.title(str(data["title"]))
    win.geometry("460x340")
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

    # Formula box with rendered LaTeX image
    formula_box = ctk.CTkFrame(win, fg_color=C["bg_card"], corner_radius=8)
    formula_box.pack(fill="x", padx=24, pady=(0, 14))

    try:
        img = _render_latex(data["latex"], C["accent"], C["bg_card"])
        ctk.CTkLabel(formula_box, image=img, text="").pack(pady=14)
    except Exception:
        # Fallback to plain text if matplotlib fails
        ctk.CTkLabel(
            formula_box,
            text=data["latex"],
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
