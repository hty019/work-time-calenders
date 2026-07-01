"""tkinter 달력 그리드 렌더링."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from widget import theme
from widget.calendar_model import DayCell, format_hms

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
_INCOMPLETE_TEXT = "미퇴근"
_SAT_COL = 5  # 토요일 열 인덱스 (이후는 주말)


def render_grid(
    parent: tk.Widget,
    grid: list[list[DayCell]],
    on_day_click: Callable[[str], None],
) -> None:
    for child in parent.winfo_children():
        child.destroy()

    for col, name in enumerate(_WEEKDAYS):
        fg = theme.FG_HOLIDAY if col >= _SAT_COL else theme.FG_MUTED
        tk.Label(
            parent, text=name, fg=fg, bg=theme.BG_BASE,
            font=theme.FONT_WEEKDAY, width=4,
        ).grid(row=0, column=col, padx=1, pady=(0, 2))

    for r, week in enumerate(grid, start=1):
        for c, cell in enumerate(week):
            _render_cell(parent, cell, r, c, on_day_click)


def _render_cell(
    parent: tk.Widget,
    cell: DayCell,
    row: int,
    col: int,
    on_day_click: Callable[[str], None],
) -> None:
    if cell.day == 0:
        tk.Frame(
            parent, bg=theme.BG_BASE,
            width=theme.CELL_WIDTH, height=theme.CELL_HEIGHT,
        ).grid(row=row, column=col, padx=1, pady=1)
        return

    is_weekend = col >= _SAT_COL
    is_holiday = cell.holiday_name is not None or is_weekend
    cell_bg = theme.BG_TODAY if cell.is_today else theme.BG_BASE

    if cell.is_today:
        date_fg = theme.FG_DATE
    elif is_holiday:
        date_fg = theme.FG_HOLIDAY
    else:
        date_fg = theme.FG_DATE

    frame = tk.Frame(
        parent, bg=cell_bg,
        width=theme.CELL_WIDTH, height=theme.CELL_HEIGHT,
        cursor="hand2",
    )
    frame.grid(row=row, column=col, padx=1, pady=1)
    frame.grid_propagate(False)

    date_label = tk.Label(
        frame, text=str(cell.day), fg=date_fg, bg=cell_bg, font=theme.FONT_DATE,
    )
    date_label.pack(pady=(3, 0))

    sub_text, sub_fg = _subtext(cell)
    time_label = tk.Label(
        frame, text=sub_text, fg=sub_fg, bg=cell_bg, font=theme.FONT_TIME,
    )
    time_label.pack()

    widgets = (frame, date_label, time_label)
    for w in widgets:
        w.bind("<Button-1>", lambda _e, d=cell.date: on_day_click(d))
    if not cell.is_today:
        _bind_hover(frame, widgets, cell_bg)


def _subtext(cell: DayCell) -> tuple[str, str]:
    """셀 하단 텍스트와 색상을 결정한다."""
    if cell.is_incomplete:
        return _INCOMPLETE_TEXT, theme.FG_INCOMPLETE
    if cell.work_seconds is None:
        return "", theme.FG_TIME
    time_fg = theme.FG_TIME_TODAY if cell.is_today else theme.FG_TIME
    return format_hms(cell.work_seconds), time_fg


def _bind_hover(
    frame: tk.Widget, widgets: tuple[tk.Widget, ...], base_bg: str
) -> None:
    """마우스 오버 시 셀 배경을 살짝 밝혀 상호작용을 암시한다.

    셀 내부 라벨↔프레임으로 커서가 넘어갈 때마다 부모에 <Leave>가 발생해
    배경이 깜빡이며 뒤틀려 보이던 문제를, 포인터가 여전히 셀 내부에 있는지
    확인해 해결한다.
    """
    def set_bg(color: str) -> None:
        for w in widgets:
            w.configure(bg=color)

    def on_enter(_e):
        set_bg(theme.BG_HOVER)

    def on_leave(_e):
        under = frame.winfo_containing(*frame.winfo_pointerxy())
        if under in widgets:  # 같은 셀 내부 이동이면 hover 유지
            return
        set_bg(base_bg)

    for w in widgets:
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)
