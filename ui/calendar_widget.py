"""월 달력 그리드 Qt 위젯."""
from __future__ import annotations

import datetime
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QFrame

from core.calendar_model import DayCell, format_hms, format_hm
from core.vacation import FULL_DAY_MINUTES
from ui import theme

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
_SAT_COL = 5
_SATURDAY = 5  # date.weekday(): 월=0 ~ 일=6


def _is_weekend(date: str | None) -> bool:
    if date is None:
        return False
    return datetime.date.fromisoformat(date).weekday() >= _SATURDAY


class _WeekdayHeader(QLabel):
    """클릭하면 해당 요일 인덱스(월=0..일=6)로 콜백하는 요일 헤더."""

    def __init__(
        self, text: str, weekday: int, on_click: Callable[[int], None]
    ) -> None:
        super().__init__(text)
        self._weekday = weekday
        self._on_click = on_click
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._on_click(self._weekday)


class _DayCellWidget(QFrame):
    def __init__(self, cell: DayCell, on_click: Callable[[str], None]) -> None:
        super().__init__()
        self._date = cell.date
        self._on_click = on_click
        self.setMinimumSize(theme.CELL_MIN_WIDTH, theme.CELL_MIN_HEIGHT)
        # 배경은 주말(연한 갈색)/기본, 오늘은 밝은 파랑 테두리로 강조.
        # 호버 시 주황 테두리 — 평상시에도 투명 2px 테두리를 깔아 두어
        # 호버 순간 콘텐츠가 밀리지 않게 한다.
        bg = theme.BG_WEEKEND if _is_weekend(cell.date) else theme.BG_ELEVATED
        base_border = (
            theme.BORDER_TODAY if cell.is_today else "transparent"
        )
        # ID 셀렉터로 셀 프레임에만 적용 (자식 QLabel 이 QFrame 을 상속해
        # 셀렉터 없는 border 규칙이 라벨까지 번지는 것을 방지)
        self.setObjectName("dayCell")
        self.setStyleSheet(f"""
        #dayCell {{
            background-color: {bg};
            border-radius: 6px;
            border: 2px solid {base_border};
        }}
        #dayCell:hover {{
            border: 2px solid {theme.BORDER_HOVER};
            background-color: {theme.BG_HOVER};
        }}
        """)
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

        is_full_day_vacation = cell.vacation_minutes >= FULL_DAY_MINUTES

        if is_full_day_vacation:
            # 1day 휴가일: 출퇴근·근로 기록이 있어도 숨기고 휴가만 크게 표시
            layout.addWidget(self._vacation_label(cell, emphasized=True))
        elif cell.is_clocked_out:
            # 퇴근 완료: 계획 대신 출근/퇴근 시각·(휴가)·구분선·인정시간 표시
            inout = QLabel(
                f"출근 {cell.clock_in_hm}\n퇴근 {cell.clock_out_hm}"
            )
            inout.setAlignment(Qt.AlignCenter)
            inout.setStyleSheet(
                f"color:{theme.FG_TIME}; font-size:{theme.CELL_WORK_FONT_PX}px;"
            )
            layout.addWidget(inout)

            if cell.vacation_minutes > 0:
                layout.addWidget(self._vacation_label(cell))

            divider = QLabel("─────")
            divider.setAlignment(Qt.AlignCenter)
            divider.setStyleSheet(
                f"color:{theme.FG_MUTED}; font-size:{theme.CELL_PLAN_FONT_PX}px;"
            )
            layout.addWidget(divider)

            # 근로 인정시간(근로+휴가)을 연두색 볼드로 강조
            recognized = (cell.work_seconds or 0) + cell.vacation_minutes * 60
            work = QLabel(format_hms(recognized))
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
                plan = QLabel(f"실 계획 {format_hm(cell.planned_minutes)}")
                plan.setAlignment(Qt.AlignCenter)
                plan.setStyleSheet(
                    f"color:{theme.FG_PLANNED}; "
                    f"font-size:{theme.CELL_PLAN_FONT_PX}px;"
                )
                layout.addWidget(plan)

            if cell.vacation_minutes > 0:
                layout.addWidget(self._vacation_label(cell))

        # (가)계획 범위 표시 — 퇴근 완료 후 범위 내 정상 처리된 날과
        # 1day 휴가일은 숨기고, 범위를 벗어난 날은 경고를 유지한다.
        show_recog = (
            cell.recog_hm
            and not is_full_day_vacation
            and (not cell.is_clocked_out or cell.out_of_range)
        )
        if show_recog:
            recog_fg = (
                theme.FG_RANGE_WARN if cell.out_of_range else theme.FG_MUTED
            )
            prefix = "⚠ (가)계획" if cell.out_of_range else "(가)계획"
            recog = QLabel(f"{prefix} {cell.recog_hm}")
            recog.setAlignment(Qt.AlignCenter)
            recog.setStyleSheet(
                f"color:{recog_fg}; font-size:{theme.CELL_PLAN_FONT_PX}px;"
            )
            layout.addWidget(recog)

        layout.addStretch(1)  # 아래쪽 여백 → 콘텐츠를 수직 가운데로
        # 상단 날짜 높이만큼 하단에 대칭 여백을 두어 셀 전체 기준 가운데로 보정
        layout.addSpacing(theme.CELL_DATE_ROW_PX)

    @staticmethod
    def _vacation_label(cell: DayCell, emphasized: bool = False) -> QLabel:
        """'휴가 Nh' 라벨. emphasized 면 큰 폰트 볼드(휴가만 있는 날)."""
        vac = QLabel(f"휴가 {cell.vacation_minutes // 60}h")
        vac.setAlignment(Qt.AlignCenter)
        size = (
            theme.CELL_ACTUAL_DONE_FONT_PX if emphasized
            else theme.CELL_PLAN_FONT_PX
        )
        weight = " font-weight:bold;" if emphasized else ""
        vac.setStyleSheet(
            f"color:{theme.FG_VACATION}; font-size:{size}px;{weight}"
        )
        return vac

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
    def __init__(
        self,
        on_day_click: Callable[[str], None],
        on_weekday_click: Callable[[int], None],
    ) -> None:
        super().__init__()
        self._on_day_click = on_day_click
        self._on_weekday_click = on_weekday_click
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
            head = _WeekdayHeader(name, col, self._on_weekday_click)
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
