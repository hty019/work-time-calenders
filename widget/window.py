"""테두리 없는 always-on-top 위젯 창."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import config
from widget import theme
from widget.calendar_model import DayCell
from widget.calendar_view import render_grid

_CLOSE_TEXT = "✕"
_CLOCK_OUT_TEXT = "퇴근"
_CANCEL_TEXT = "취소"


class WidgetWindow:
    def __init__(
        self,
        on_clock_out: Callable[[], None],
        on_cancel_clock_out: Callable[[], None],
        on_edit_day: Callable[[str], None],
    ) -> None:
        self._on_clock_out = on_clock_out
        self._on_cancel_clock_out = on_cancel_clock_out
        self._on_edit_day = on_edit_day
        self._root = tk.Tk()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", theme.WINDOW_ALPHA)
        self._root.configure(bg=theme.BG_BASE)
        pos = config.get_window_pos()
        if pos:
            self._root.geometry(f"+{pos[0]}+{pos[1]}")

        header_frame = tk.Frame(self._root, bg=theme.BG_BASE)
        header_frame.pack(fill="x", padx=10, pady=(10, 6))

        self._header = tk.Label(
            header_frame, text="", font=theme.FONT_HEADER, anchor="w",
            fg=theme.FG_DATE, bg=theme.BG_BASE,
        )
        self._header.pack(side="left", fill="x", expand=True)

        self._make_close_button(header_frame).pack(side="right")

        self._cal_frame = tk.Frame(self._root, bg=theme.BG_BASE)
        self._cal_frame.pack(padx=10, pady=2)
        self._today_time_label: tk.Label | None = None

        # 하단 버튼 영역: 상태에 따라 [퇴근] 또는 [취소][퇴근] 으로 다시 그린다.
        self._footer = tk.Frame(self._root, bg=theme.BG_BASE)
        self._footer.pack(fill="x", padx=10, pady=(6, 10))

        self._bind_drag()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.bind_all("<Command-q>", lambda _e: self._on_close())

    @property
    def root(self) -> tk.Tk:
        return self._root

    def _make_close_button(self, parent: tk.Widget) -> tk.Label:
        """우상단 닫기 버튼 (라벨 기반, 색상 제어 자유)."""
        btn = tk.Label(
            parent, text=_CLOSE_TEXT, font=theme.FONT_WEEKDAY,
            fg=theme.FG_MUTED, bg=theme.BG_BASE, cursor="hand2", padx=4,
        )
        btn.bind("<Button-1>", lambda _e: self._on_close())
        btn.bind("<Enter>", lambda _e: btn.configure(fg=theme.FG_HOLIDAY))
        btn.bind("<Leave>", lambda _e: btn.configure(fg=theme.FG_MUTED))
        return btn

    def _make_button(
        self, parent: tk.Widget, text: str,
        on_click: Callable[[], None], fg: str,
    ) -> tk.Label:
        """하단 액션 버튼 (라벨 기반, 띄운 표면 스타일)."""
        btn = tk.Label(
            parent, text=text, font=theme.FONT_BUTTON,
            fg=fg, bg=theme.BG_ELEVATED, cursor="hand2", pady=6,
        )
        btn.bind("<Button-1>", lambda _e: on_click())
        btn.bind("<Enter>", lambda _e: btn.configure(bg=theme.BG_HOVER))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=theme.BG_ELEVATED))
        return btn

    def _render_footer(self, is_clocked_out: bool) -> None:
        """퇴근 상태면 [취소][퇴근], 진행 중이면 [퇴근] 만 표시한다."""
        for child in self._footer.winfo_children():
            child.destroy()
        if is_clocked_out:
            cancel = self._make_button(
                self._footer, _CANCEL_TEXT,
                self._on_cancel_clock_out, theme.FG_MUTED,
            )
            clock = self._make_button(
                self._footer, _CLOCK_OUT_TEXT,
                self._on_clock_out, theme.FG_DATE,
            )
            cancel.pack(side="left", fill="x", expand=True, padx=(0, 3))
            clock.pack(side="left", fill="x", expand=True, padx=(3, 0))
        else:
            self._make_button(
                self._footer, _CLOCK_OUT_TEXT,
                self._on_clock_out, theme.FG_DATE,
            ).pack(fill="x")

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

    def render(
        self, header_text: str, grid: list[list[DayCell]],
        is_clocked_out: bool,
    ) -> None:
        self._header.config(text=header_text)
        self._today_time_label = render_grid(
            self._cal_frame, grid, self._on_edit_day
        )
        self._render_footer(is_clocked_out)

    def update_live(
        self, header_text: str, today_time_text: str | None
    ) -> None:
        """전체 재렌더 없이 헤더와 오늘 셀 근무시간만 갱신한다.

        today_time_text 가 None 이면(진행 중 아님) 오늘 셀은 건드리지 않는다.
        """
        self._header.config(text=header_text)
        if today_time_text is not None and self._today_time_label is not None:
            self._today_time_label.config(text=today_time_text)

    def run(self) -> None:
        self._root.mainloop()
