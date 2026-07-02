"""월 달력 그리드 Qt 위젯."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QFrame

from core.calendar_model import DayCell, format_hms, format_hm
from ui import theme

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
_SAT_COL = 5


class _DayCellWidget(QFrame):
    def __init__(self, cell: DayCell, on_click: Callable[[str], None]) -> None:
        super().__init__()
        self._date = cell.date
        self._on_click = on_click
        self.setMinimumSize(theme.CELL_MIN_WIDTH, theme.CELL_MIN_HEIGHT)
        is_today = cell.is_today
        bg = theme.BG_TODAY if is_today else theme.BG_ELEVATED
        self.setStyleSheet(
            f"background-color:{bg}; border-radius:6px;"
        )
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)

        # 날짜는 기존과 같이 좌측 상단에 고정
        date_fg = theme.FG_HOLIDAY if cell.holiday_name else theme.FG_DATE
        date_label = QLabel(str(cell.day))
        date_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        date_label.setStyleSheet(
            f"color:{date_fg}; font-size:16px; font-weight:bold;"
        )
        layout.addWidget(date_label)

        layout.addStretch(1)  # 날짜 아래 여백 → 이하 콘텐츠를 수직 가운데로

        if cell.holiday_name:
            name = QLabel(cell.holiday_name)
            name.setAlignment(Qt.AlignCenter)
            name.setStyleSheet(f"color:{theme.FG_HOLIDAY}; font-size:10px;")
            layout.addWidget(name)

        if cell.is_clocked_out:
            # 퇴근 완료: 계획 대신 출근/퇴근 시각·구분선·실 근로시간 표시
            inout = QLabel(
                f"출근 {cell.clock_in_hm}\n퇴근 {cell.clock_out_hm}"
            )
            inout.setAlignment(Qt.AlignCenter)
            inout.setStyleSheet(
                f"color:{theme.FG_TIME}; font-size:{theme.CELL_WORK_FONT_PX}px;"
            )
            layout.addWidget(inout)

            divider = QLabel("─────")
            divider.setAlignment(Qt.AlignCenter)
            divider.setStyleSheet(
                f"color:{theme.FG_MUTED}; font-size:{theme.CELL_PLAN_FONT_PX}px;"
            )
            layout.addWidget(divider)

            # 실 근로시간을 연두색 볼드로 강조
            work = QLabel(format_hms(cell.work_seconds))
            work.setAlignment(Qt.AlignCenter)
            work.setStyleSheet(
                f"color:{theme.FG_ACTUAL_DONE}; "
                f"font-size:{theme.CELL_ACTUAL_DONE_FONT_PX}px; "
                f"font-weight:bold;"
            )
            layout.addWidget(work)
        else:
            work_text, work_fg = self._work_line(cell)
            if work_text:
                work = QLabel(work_text)
                work.setAlignment(Qt.AlignCenter)
                work.setStyleSheet(
                    f"color:{work_fg}; font-size:{theme.CELL_WORK_FONT_PX}px;"
                )
                layout.addWidget(work)

            if cell.planned_minutes > 0:
                plan = QLabel(f"계획 {format_hm(cell.planned_minutes)}")
                plan.setAlignment(Qt.AlignCenter)
                plan.setStyleSheet(
                    f"color:{theme.FG_PLANNED}; "
                    f"font-size:{theme.CELL_PLAN_FONT_PX}px;"
                )
                layout.addWidget(plan)

        layout.addStretch(1)  # 아래쪽 여백 → 콘텐츠를 수직 가운데로
        # 상단 날짜 높이만큼 하단에 대칭 여백을 두어 셀 전체 기준 가운데로 보정
        layout.addSpacing(theme.CELL_DATE_ROW_PX)

    def _work_line(self, cell: DayCell) -> tuple[str, str]:
        if cell.is_incomplete:
            return "미퇴근", theme.FG_INCOMPLETE
        if cell.work_seconds is None:
            return "", theme.FG_TIME
        return format_hms(cell.work_seconds), theme.FG_TIME

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._date is not None:
            self._on_click(self._date)


class CalendarWidget(QWidget):
    def __init__(self, on_day_click: Callable[[str], None]) -> None:
        super().__init__()
        self._on_day_click = on_day_click
        self._layout = QGridLayout(self)
        self._layout.setSpacing(4)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def render_grid(self, grid: list[list[DayCell]]) -> None:
        self._clear()
        for col, name in enumerate(_WEEKDAYS):
            fg = theme.FG_HOLIDAY if col >= _SAT_COL else theme.FG_MUTED
            head = QLabel(name)
            head.setAlignment(Qt.AlignCenter)
            head.setStyleSheet(f"color:{fg}; font-weight:bold;")
            self._layout.addWidget(head, 0, col)
        for r, week in enumerate(grid, start=1):
            for c, cell in enumerate(week):
                if cell.day == 0:
                    self._layout.addWidget(QWidget(), r, c)
                    continue
                self._layout.addWidget(
                    _DayCellWidget(cell, self._on_day_click), r, c
                )
