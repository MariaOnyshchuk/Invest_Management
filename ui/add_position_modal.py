"""
ui/add_position_modal.py
Модальне вікно для додавання нової позиції до портфелю.
Відкривається після вибору тікера з пошуку.

Флоу:
  1. Показує знайдену компанію (тікер, назва, поточна ціна)
  2. Поля: Кількість акцій (qty) + Середня ціна купівлі (avg)
  3. Кнопка "Додати до портфелю" → викликає on_confirm(Stock)
"""

import threading
import customtkinter as ctk
from ui.theme import C, F
from data.stub_data import Stock
from data.market_data import fetch_ticker_info


class AddPositionModal(ctk.CTkToplevel):
    def __init__(self, master, ticker: str, name: str, on_confirm):
        super().__init__(master)
        self.title("Додати позицію")
        self.geometry("420x520")
        self.resizable(False, False)
        self.configure(fg_color=C["bg_panel"])
        self.grab_set()
        self.lift()
        self.focus_force()

        self._ticker     = ticker.upper()
        self._name       = name
        self._on_confirm = on_confirm
        self._info: dict | None = None

        self._build_loading()
        # Завантажуємо реальну ціну у фоні
        threading.Thread(target=self._load_info, daemon=True).start()

    # ── Loading state ─────────────────────────────────────────────────────────

    def _build_loading(self):
        self._loading_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._loading_frame.pack(fill="both", expand=True, padx=28, pady=28)

        ctk.CTkLabel(
            self._loading_frame,
            text=f"Завантаження даних\nдля {self._ticker}…",
            text_color=C["text_2"], font=F["body"],
            justify="center",
        ).pack(expand=True)

        self._spinner = ctk.CTkProgressBar(
            self._loading_frame, mode="indeterminate",
            fg_color=C["bg_card"], progress_color=C["accent"],
        )
        self._spinner.pack(fill="x", pady=(0, 16))
        self._spinner.start()

    def _load_info(self):
        info = fetch_ticker_info(self._ticker)
        self.after(0, lambda: self._on_info_loaded(info))

    def _on_info_loaded(self, info: dict | None):
        self._info = info
        self._spinner.stop()
        self._loading_frame.destroy()
        if info:
            self._build_form(info)
        else:
            self._build_error()

    # ── Error state ───────────────────────────────────────────────────────────

    def _build_error(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=28, pady=28)
        ctk.CTkLabel(
            f, text=f"Не вдалося завантажити\nдані для {self._ticker}",
            text_color=C["red"], font=F["body"], justify="center",
        ).pack(expand=True)
        ctk.CTkButton(
            f, text="Закрити", fg_color=C["bg_card"],
            text_color=C["text_2"], command=self.destroy,
        ).pack()

    # ── Main form ─────────────────────────────────────────────────────────────

    def _build_form(self, info: dict):
        pad = 24

        # ── Header: тікер + назва ─────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=0)
        hdr.pack(fill="x")

        inner_hdr = ctk.CTkFrame(hdr, fg_color="transparent")
        inner_hdr.pack(fill="x", padx=pad, pady=14)

        # Ticker tag
        tag = ctk.CTkFrame(inner_hdr, fg_color=C["bg_input"], corner_radius=6)
        tag.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            tag, text=info["ticker"],
            text_color=C["accent"], font=("SF Mono", 14, "bold"),
        ).pack(padx=10, pady=5)

        name_col = ctk.CTkFrame(inner_hdr, fg_color="transparent")
        name_col.pack(side="left")
        ctk.CTkLabel(
            name_col, text=info["name"],
            text_color=C["text_1"], font=F["title"], anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            name_col, text=f"{info['sector']}  ·  {info['exchange'] if 'exchange' in info else ''}",
            text_color=C["text_3"], font=F["tiny"], anchor="w",
        ).pack(anchor="w")

        # Current price (right)
        price_col = ctk.CTkFrame(inner_hdr, fg_color="transparent")
        price_col.pack(side="right")
        ctk.CTkLabel(
            price_col, text="Поточна ціна",
            text_color=C["text_3"], font=F["tiny"],
        ).pack(anchor="e")
        ctk.CTkLabel(
            price_col, text=f"${info['price']:,.2f}",
            text_color=C["green"], font=("SF Mono", 18, "bold"),
        ).pack(anchor="e")

        # ── Form fields ───────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=pad, pady=16)

        # Qty
        ctk.CTkLabel(
            body, text="Кількість акцій",
            text_color=C["text_2"], font=F["small"], anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._qty_var = ctk.StringVar(value="1")
        qty_entry = ctk.CTkEntry(
            body,
            textvariable=self._qty_var,
            fg_color=C["bg_input"], border_color=C["border"],
            text_color=C["text_1"], font=F["mono"],
            height=40, corner_radius=8,
            placeholder_text="напр. 10",
        )
        qty_entry.pack(fill="x", pady=(0, 14))
        qty_entry.focus()

        # Avg price
        ctk.CTkLabel(
            body, text="Середня ціна купівлі ($)",
            text_color=C["text_2"], font=F["small"], anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._avg_var = ctk.StringVar(value=str(info["price"]))
        avg_entry = ctk.CTkEntry(
            body,
            textvariable=self._avg_var,
            fg_color=C["bg_input"], border_color=C["border"],
            text_color=C["text_1"], font=F["mono"],
            height=40, corner_radius=8,
            placeholder_text="напр. 150.00",
        )
        avg_entry.pack(fill="x", pady=(0, 4))

        # Hint
        ctk.CTkLabel(
            body,
            text=f"Поточна ціна заповнена автоматично як орієнтир",
            text_color=C["text_3"], font=F["tiny"],
        ).pack(anchor="w", pady=(0, 16))

        # Error label
        self._err_label = ctk.CTkLabel(
            body, text="", text_color=C["red"], font=F["tiny"],
        )
        self._err_label.pack(anchor="w")

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=0)
        btn_row.pack(fill="x", side="bottom")

        inner_btn = ctk.CTkFrame(btn_row, fg_color="transparent")
        inner_btn.pack(fill="x", padx=pad, pady=12)

        ctk.CTkButton(
            inner_btn, text="Скасувати",
            fg_color=C["bg_input"], hover_color=C["bg_card"],
            text_color=C["text_2"], font=F["body"],
            border_width=1, border_color=C["border"],
            corner_radius=8, height=38,
            command=self.destroy,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            inner_btn, text="✓  Додати до портфелю",
            fg_color=C["accent"], hover_color=C["accent_dim"],
            text_color="#FFFFFF", font=("SF Pro Text", 13, "bold"),
            corner_radius=8, height=38,
            command=self._confirm,
        ).pack(side="left", fill="x", expand=True)

    # ── Validation + confirm ──────────────────────────────────────────────────

    def _confirm(self):
        qty_str = self._qty_var.get().strip()
        avg_str = self._avg_var.get().strip()

        try:
            qty = int(qty_str)
            if qty <= 0:
                raise ValueError
        except ValueError:
            self._err_label.configure(text="⚠ Кількість має бути цілим числом > 0")
            return

        try:
            avg = float(avg_str.replace(",", "."))
            if avg <= 0:
                raise ValueError
        except ValueError:
            self._err_label.configure(text="⚠ Середня ціна має бути числом > 0")
            return

        info = self._info
        stock = Stock(
            ticker=info["ticker"],
            name=info["name"][:22],
            qty=qty,
            avg=avg,
            price=info["price"],
            sector=info.get("sector", "Other"),
        )
        self.destroy()
        self._on_confirm(stock)