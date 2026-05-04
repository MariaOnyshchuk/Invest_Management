"""
ui/chart_panel.py
Панель з matplotlib-графіком динаміки портфелю vs S&P 500.
Підтримує перемикання 1D / 1W / 1M / 3M / 1Y.
"""

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker

from ui.theme import C, F
from utils.calc import generate_chart_data

RANGES = ["1D", "1W", "1M", "3M", "1Y"]


class ChartPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=C["bg_panel"],
            corner_radius=12,
            border_width=1,
            border_color=C["border"],
            **kwargs,
        )
        self._active_range = "1D"
        self._build_header()
        self._build_chart()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            head, text="Динаміка портфелю",
            text_color=C["text_1"], font=F["title"],
        ).pack(side="left")

        pills_frame = ctk.CTkFrame(head, fg_color="transparent")
        pills_frame.pack(side="right")
        self._pill_btns: dict[str, ctk.CTkButton] = {}

        for r in RANGES:
            btn = ctk.CTkButton(
                pills_frame, text=r, width=34, height=22,
                font=F["tiny"],
                fg_color=C["accent"] if r == "1D" else C["bg_card"],
                hover_color=C["accent_dim"],
                text_color="#FFFFFF" if r == "1D" else C["text_3"],
                corner_radius=6,
                command=lambda rng=r: self._switch_range(rng),
            )
            btn.pack(side="left", padx=2)
            self._pill_btns[r] = btn

        # Separator
        ctk.CTkFrame(self, fg_color=C["border"], height=1).pack(fill="x", padx=16)

    # ── Chart ─────────────────────────────────────────────────────────────────

    def _build_chart(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=14, pady=10)

        self._fig = Figure(figsize=(6, 3.8), dpi=100)
        self._fig.patch.set_facecolor(C["bg_panel"])
        self._ax = self._fig.add_subplot(111)

        self._mpl_canvas = FigureCanvasTkAgg(self._fig, master=wrap)
        self._mpl_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Legend
        leg = ctk.CTkFrame(wrap, fg_color="transparent")
        leg.pack(fill="x", pady=(4, 0))
        self._legend_entry(leg, C["accent"], "Портфель", dashed=False)
        self._legend_entry(leg, C["amber"],  "S&P 500",  dashed=True)

        self.refresh("1D")

    def _legend_entry(self, parent, color: str, label: str, dashed: bool):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(side="left", padx=8)

        if dashed:
            # малюємо пунктир через два відрізки
            dash1 = ctk.CTkFrame(f, fg_color=color, width=7, height=2, corner_radius=1)
            dash1.pack(side="left", padx=(0, 2))
            dash2 = ctk.CTkFrame(f, fg_color=color, width=7, height=2, corner_radius=1)
            dash2.pack(side="left", padx=(0, 5))
        else:
            line = ctk.CTkFrame(f, fg_color=color, width=18, height=2, corner_radius=1)
            line.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(
            f, text=label, text_color=C["text_2"], font=F["tiny"],
        ).pack(side="left")

    # ── Range switch ──────────────────────────────────────────────────────────

    def _switch_range(self, rng: str):
        for r, btn in self._pill_btns.items():
            active = r == rng
            btn.configure(
                fg_color=C["accent"] if active else C["bg_card"],
                text_color="#FFFFFF" if active else C["text_3"],
            )
        self._active_range = rng
        self.refresh(rng)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def refresh(self, rng: str | None = None):
        rng = rng or self._active_range
        labels, port, bench = generate_chart_data(rng)

        ax = self._ax
        ax.clear()
        ax.set_facecolor(C["bg_panel"])
        ax.spines[:].set_color(C["border"])
        ax.tick_params(colors=C["text_3"], labelsize=9)
        ax.xaxis.label.set_color(C["text_3"])
        ax.yaxis.label.set_color(C["text_3"])
        for spine in ax.spines.values():
            spine.set_linewidth(0.5)
        ax.grid(axis="y", color=C["border"], linewidth=0.4, linestyle="--", alpha=0.6)
        ax.grid(axis="x", visible=False)

        xs = list(range(len(labels)))

        # Portfolio fill + line
        ax.fill_between(xs, port, alpha=0.08, color=C["accent"])
        ax.plot(xs, port, color=C["accent"], linewidth=1.8, label="Портфель")

        # Benchmark dashed
        ax.plot(xs, bench, color=C["amber"], linewidth=1.2,
                linestyle="--", dashes=(5, 3), alpha=0.75, label="S&P 500")

        # X-axis labels — показуємо лише ~6
        step = max(1, len(labels) // 6)
        ax.set_xticks(xs[::step])
        ax.set_xticklabels(labels[::step], rotation=0, fontsize=9)

        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
        self._fig.tight_layout(pad=0.5)
        self._mpl_canvas.draw()