"""
ui/search_bar.py
Пошуковий рядок у хедері.

Поведінка:
  - Введення тексту → debounce 400 мс → search_ticker() у фоновому потоці
  - Dropdown з результатами (макс 8) з'являється під рядком
  - Вибір результату → відкривається AddPositionModal
  - Escape / клік поза dropdown → закриває список
"""

import threading
import customtkinter as ctk
from ui.theme import C, F
from data.market_data import search_ticker
from ui.add_position_modal import AddPositionModal

DEBOUNCE_MS = 400
MAX_RESULTS = 8


class SearchBar(ctk.CTkFrame):
    def __init__(self, master, on_stock_added, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_stock_added = on_stock_added
        self._debounce_id    = None
        self._dropdown: ctk.CTkToplevel | None = None
        self._results: list[dict] = []
        self._searching = False

        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # Search icon label
        ctk.CTkLabel(
            self, text="⌕",
            text_color=C["text_3"], font=("SF Pro Text", 18),
        ).pack(side="left", padx=(0, 4))

        # Entry
        self._var = ctk.StringVar()
        self._entry = ctk.CTkEntry(
            self,
            textvariable=self._var,
            width=240,
            height=34,
            fg_color=C["bg_input"],
            border_color=C["border"],
            border_width=1,
            text_color=C["text_1"],
            font=F["body"],
            corner_radius=8,
            placeholder_text="Пошук тікера або компанії…",
            placeholder_text_color=C["text_3"],
        )
        self._entry.pack(side="left")

        # Spinner (прихований за замовчуванням)
        self._spinner = ctk.CTkLabel(
            self, text="", text_color=C["text_3"], font=F["tiny"], width=20,
        )
        self._spinner.pack(side="left", padx=4)

        # Bind events
        self._var.trace_add("write", self._on_type)
        self._entry.bind("<Escape>", lambda e: self._close_dropdown())
        self._entry.bind("<FocusOut>", self._on_focus_out)

    # ── Debounce + search ─────────────────────────────────────────────────────

    def _on_type(self, *_):
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        query = self._var.get().strip()
        if not query:
            self._close_dropdown()
            return
        self._debounce_id = self.after(DEBOUNCE_MS, lambda: self._do_search(query))

    def _do_search(self, query: str):
        if self._searching:
            return
        self._searching = True
        self._spinner.configure(text="◌")
        threading.Thread(
            target=self._search_worker, args=(query,), daemon=True
        ).start()

    def _search_worker(self, query: str):
        results = search_ticker(query)
        self.after(0, lambda: self._show_results(results))

    # ── Dropdown ──────────────────────────────────────────────────────────────

    def _show_results(self, results: list[dict]):
        self._searching = False
        self._spinner.configure(text="")
        self._results = results
        self._close_dropdown()

        if not results:
            return

        # Отримуємо координати entry у глобальних координатах вікна
        self._entry.update_idletasks()
        x = self._entry.winfo_rootx()
        y = self._entry.winfo_rooty() + self._entry.winfo_height() + 4
        w = self._entry.winfo_width()

        self._dropdown = ctk.CTkToplevel(self)
        self._dropdown.wm_overrideredirect(True)      # без заголовка
        dropdown_height = min(len(results) * 48 + 24, 420)

        self._dropdown.wm_geometry(
            f"{max(w, 320)}x{dropdown_height}+{x}+{y}"
        )
        self._dropdown.configure(fg_color=C["bg_panel"])
        self._dropdown.lift()
        self._dropdown.attributes("-topmost", True)

        # Рамка
        frame = ctk.CTkFrame(
            self._dropdown,
            fg_color=C["bg_panel"],
            corner_radius=10,
            border_width=1,
            border_color=C["border"],
        )
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        for i, r in enumerate(results):
            self._build_result_row(frame, r, i)

    def _build_result_row(self, parent, result: dict, idx: int):
        row = ctk.CTkFrame(parent, fg_color="transparent", cursor="hand2")
        row.pack(fill="x", padx=6, pady=(6 if idx == 0 else 2, 0))

        inner = ctk.CTkFrame(row, fg_color=C["bg_card"], corner_radius=7)
        inner.pack(fill="x")

        # Ticker tag
        tag = ctk.CTkFrame(inner, fg_color=C["bg_input"], corner_radius=5)
        tag.pack(side="left", padx=(8, 10), pady=8)
        ctk.CTkLabel(
            tag, text=result["ticker"],
            text_color=C["accent"], font=("SF Mono", 11, "bold"),
        ).pack(padx=7, pady=3)

        # Name
        ctk.CTkLabel(
            inner, text=result["name"][:30],
            text_color=C["text_1"], font=F["small"], anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Exchange + type badge
        badge_text = result.get("exchange", "") or result.get("type", "")
        if badge_text:
            badge = ctk.CTkFrame(inner, fg_color=C["bg_input"], corner_radius=4)
            badge.pack(side="right", padx=(0, 8))
            ctk.CTkLabel(
                badge, text=badge_text,
                text_color=C["text_3"], font=F["tiny"],
            ).pack(padx=5, pady=2)

        # Hover effect + click
        def on_enter(e, f=inner):
            f.configure(fg_color=C["bg_input"])
        def on_leave(e, f=inner):
            f.configure(fg_color=C["bg_card"])
        def on_click(e, r=result):
            self._select(r)

        for widget in [row, inner, tag]:
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

        # Bind all child labels too
        for child in inner.winfo_children():
            child.bind("<Button-1>", on_click)
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)

    def _select(self, result: dict):
        self._close_dropdown()
        self._var.set("")
        AddPositionModal(
            master=self.winfo_toplevel(),
            ticker=result["ticker"],
            name=result["name"],
            on_confirm=self._on_stock_added,
        )

    def _close_dropdown(self):
        if self._dropdown and self._dropdown.winfo_exists():
            self._dropdown.destroy()
        self._dropdown = None

    def _on_focus_out(self, event):
        # Невелика затримка — щоб клік по dropdown встиг спрацювати
        self.after(150, self._close_dropdown)