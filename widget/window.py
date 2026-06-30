"""테두리 없는 always-on-top 위젯 창."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import config
from widget.calendar_model import DayCell
from widget.calendar_view import render_grid


class WidgetWindow:
    def __init__(
        self,
        on_clock_out: Callable[[], None],
        on_edit_day: Callable[[str], None],
    ) -> None:
        self._on_clock_out = on_clock_out
        self._on_edit_day = on_edit_day
        self._root = tk.Tk()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        pos = config.get_window_pos()
        if pos:
            self._root.geometry(f"+{pos[0]}+{pos[1]}")

        header_frame = tk.Frame(self._root)
        header_frame.pack(fill="x", padx=8, pady=(8, 4))

        self._header = tk.Label(
            header_frame, text="", font=("Helvetica", 12, "bold"), anchor="w"
        )
        self._header.pack(side="left", fill="x", expand=True)

        tk.Button(
            header_frame,
            text="✕",
            command=self._on_close,
            font=("Helvetica", 10),
            relief="flat",
            padx=4,
        ).pack(side="right")

        self._cal_frame = tk.Frame(self._root)
        self._cal_frame.pack(padx=8, pady=4)

        tk.Button(self._root, text="퇴근", command=self._on_clock_out).pack(
            pady=(4, 8)
        )

        self._bind_drag()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.bind_all("<Command-q>", lambda _e: self._on_close())

    @property
    def root(self) -> tk.Tk:
        return self._root

    def _bind_drag(self) -> None:
        self._drag = {"x": 0, "y": 0}

        def start(e):
            self._drag["x"], self._drag["y"] = e.x, e.y

        def move(e):
            x = self._root.winfo_x() + (e.x - self._drag["x"])
            y = self._root.winfo_y() + (e.y - self._drag["y"])
            self._root.geometry(f"+{x}+{y}")

        def release(_e):
            config.save_window_pos(self._root.winfo_x(), self._root.winfo_y())

        self._header.bind("<Button-1>", start)
        self._header.bind("<B1-Motion>", move)
        self._header.bind("<ButtonRelease-1>", release)

    def _on_close(self) -> None:
        config.save_window_pos(self._root.winfo_x(), self._root.winfo_y())
        self._root.destroy()

    def render(self, header_text: str, grid: list[list[DayCell]]) -> None:
        self._header.config(text=header_text)
        render_grid(self._cal_frame, grid, self._on_edit_day)

    def run(self) -> None:
        self._root.mainloop()
