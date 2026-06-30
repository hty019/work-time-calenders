"""tkinter 달력 그리드 렌더링."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from widget.calendar_model import DayCell, format_hms

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
_TODAY_BG = "#2d6cdf"
_HOLIDAY_FG = "#d33"
_NORMAL_FG = "#222"


def render_grid(
    parent: tk.Widget,
    grid: list[list[DayCell]],
    on_day_click: Callable[[str], None],
) -> None:
    for child in parent.winfo_children():
        child.destroy()

    for col, name in enumerate(_WEEKDAYS):
        fg = _HOLIDAY_FG if name in ("토", "일") else _NORMAL_FG
        tk.Label(parent, text=name, fg=fg, width=6).grid(row=0, column=col, padx=1, pady=1)

    for r, week in enumerate(grid, start=1):
        for c, cell in enumerate(week):
            if cell.day == 0:
                tk.Label(parent, text="", width=6, height=2).grid(row=r, column=c)
                continue
            is_holiday = cell.holiday_name is not None or c >= 5
            fg = _HOLIDAY_FG if is_holiday else _NORMAL_FG
            bg = _TODAY_BG if cell.is_today else None
            day_fg = "white" if cell.is_today else fg
            if cell.is_incomplete:
                sub = "미퇴근"
            else:
                sub = format_hms(cell.work_seconds) if cell.work_seconds is not None else ""
            text = f"{cell.day}\n{sub}"
            btn = tk.Label(
                parent, text=text, width=6, height=2, fg=day_fg, bg=bg,
                relief="flat", cursor="hand2", justify="center",
            )
            btn.grid(row=r, column=c, padx=1, pady=1)
            btn.bind("<Button-1>", lambda _e, d=cell.date: on_day_click(d))
