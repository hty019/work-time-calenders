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
_MEMO_ICON = "📝"  # 메모가 있는 날짜 표시


def _is_weekend(date: str | None) -> bool:
    if date is None:
        return False
    return datetime.date.fromisoformat(date).weekday() >= _SATURDAY


class _WeekdayHeader(QLabel):
    """클릭하면 해당 요일 인덱스(월=0..일=6)로 콜백하는 요일 헤더.

    호버 시 둥근 칩(chip) 배경으로 클릭 가능한 영역을 드러낸다.
    """

    def __init__(
        self,
        text: str,
        weekday: int,
        fg: str,
        on_click: Callable[[int], None],
        on_hover: Callable[[int | None], None],
    ) -> None:
        super().__init__(text)
        self._weekday = weekday
        self._on_click = on_click
        self._on_hover = on_hover
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        # ID 셀렉터로 이 라벨에만 적용. 텍스트 색은 유지해 주말 구분 보존.
        self.setObjectName("weekdayHeader")
        self.setStyleSheet(f"""
        #weekdayHeader {{
            color: {fg};
            font-weight: bold;
            padding: {theme.WEEKDAY_HEADER_PAD_PX}px 0;
            border-radius: 6px;
            background: transparent;
        }}
        #weekdayHeader:hover {{
            background-color: {theme.BG_HOVER};
        }}
        """)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._on_click(self._weekday)

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().enterEvent(event)
        self._on_hover(self._weekday)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().leaveEvent(event)
        self._on_hover(None)


class _DayCellWidget(QFrame):
    def __init__(
        self,
        cell: DayCell,
        on_click: Callable[[str], None],
        is_selected: bool = False,
    ) -> None:
        super().__init__()
        self._date = cell.date
        self._on_click = on_click
        self.setMinimumSize(theme.CELL_MIN_WIDTH, theme.CELL_MIN_HEIGHT)
        # 배경은 주말(연한 갈색)/기본, 오늘은 밝은 파랑 테두리로 강조.
        # 호버 시 주황 테두리 — 평상시에도 투명 2px 테두리를 깔아 두어
        # 호버 순간 콘텐츠가 밀리지 않게 한다.
        is_weekend = _is_weekend(cell.date)
        bg = theme.BG_WEEKEND if is_weekend else theme.BG_ELEVATED
        # 주말은 호버 시에도 본래 배경(연갈색)을 유지하고 테두리만 강조
        hover_bg = bg if is_weekend else theme.BG_HOVER
        # 선택 셀(보라) > 오늘 셀(파랑) > 기본(투명)
        if is_selected and not cell.is_today:
            base_border = theme.BORDER_SELECTED
        elif cell.is_today:
            base_border = theme.BORDER_TODAY
        else:
            base_border = "transparent"
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
            background-color: {hover_bg};
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
        # 상단 날짜 높이만큼 하단에 대칭 여백을 두어 셀 전체 기준 가운데로 보정.
        # 메모가 있으면 그 여백 자리에 우측 하단 아이콘을 표시한다.
        if cell.has_memo:
            memo_icon = QLabel(_MEMO_ICON)
            memo_icon.setAlignment(Qt.AlignRight | Qt.AlignBottom)
            memo_icon.setFixedHeight(theme.CELL_DATE_ROW_PX)
            memo_icon.setStyleSheet(
                f"font-size:{theme.CELL_PLAN_FONT_PX}px;"
            )
            layout.addWidget(memo_icon)
        else:
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

        # 요일 호버 시 해당 열 전체(헤더~마지막 주)를 감싸는 테두리 오버레이.
        # 마우스 이벤트를 통과시켜 아래 셀들의 클릭·호버를 방해하지 않는다.
        self._column_overlay = QFrame(self)
        self._column_overlay.setObjectName("columnOverlay")
        self._column_overlay.setStyleSheet(f"""
        #columnOverlay {{
            border: 2px solid {theme.BORDER_HOVER};
            border-radius: 8px;
            background: transparent;
        }}
        """)
        self._column_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._column_overlay.hide()

    def _handle_weekday_hover(self, col: int | None) -> None:
        if col is None:
            self._column_overlay.hide()
            return
        # 열의 헤더(0행)부터 마지막 행까지의 합집합 영역을 계산
        top = self._layout.cellRect(0, col)
        bottom = self._layout.cellRect(self._layout.rowCount() - 1, col)
        rect = top.united(bottom).adjusted(-2, -2, 2, 2)
        self._column_overlay.setGeometry(rect)
        self._column_overlay.raise_()
        self._column_overlay.show()

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def render_grid(
        self,
        grid: list[list[DayCell]],
        selected_date: str | None = None,
    ) -> None:
        self._clear()
        self._column_overlay.hide()  # 재렌더 시 이전 호버 흔적 제거
        for col, name in enumerate(_WEEKDAYS):
            fg = theme.FG_HOLIDAY if col >= _SAT_COL else theme.FG_MUTED
            head = _WeekdayHeader(
                name, col, fg, self._on_weekday_click,
                self._handle_weekday_hover,
            )
            self._layout.addWidget(head, 0, col)
        for r, week in enumerate(grid, start=1):
            for c, cell in enumerate(week):
                if cell.day == 0:
                    self._layout.addWidget(QWidget(), r, c)
                    continue
                self._layout.addWidget(
                    _DayCellWidget(
                        cell,
                        self._on_day_click,
                        is_selected=(cell.date == selected_date),
                    ),
                    r, c,
                )
