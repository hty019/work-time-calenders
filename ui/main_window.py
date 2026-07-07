"""전체화면 메인 윈도우: 캘린더 + status 패널 + 툴바."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QToolBar, QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap

from core.attendance import WorkStatus
from core.calendar_model import DayCell
from core.day_detail import DayDetail
from core.stats import MonthSummary
from core.vacation import YearLeaveSummary
from ui import theme
from ui.calendar_widget import CalendarWidget
from ui.status_panel import StatusPanel

_STATUS_DOT = "●"
_VACATION_DEFAULT_LABEL = "휴가 관리"
_STATUS_COLORS = {
    WorkStatus.WORKING: theme.FG_WORKING,
    WorkStatus.CLOCKED_OUT: theme.FG_MUTED,
    WorkStatus.NOT_CLOCKED_IN: theme.FG_INCOMPLETE,
}


@dataclass
class MainWindowCallbacks:
    on_clock_out: Callable[[], None]
    on_cancel_clock_out: Callable[[], None]
    on_select_day: Callable[[str], None]
    on_edit_day: Callable[[str], None]
    on_edit_weekday: Callable[[int], None]
    on_prev_month: Callable[[], None]
    on_next_month: Callable[[], None]
    on_switch_mode: Callable[[], None]
    on_manage_vacation: Callable[[], None]
    on_edit_selected: Callable[[], None]
    on_go_today: Callable[[], None]
    on_register_api_key: Callable[[], None]


def _dot_icon(color: str) -> QIcon:
    """툴바용 단색 원형 점 아이콘."""
    size = theme.TOOLBAR_DOT_ICON_PX
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self, callbacks: MainWindowCallbacks) -> None:
        super().__init__()
        self._cb = callbacks
        self.setWindowTitle("근무시간")
        self.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)

        toolbar = QToolBar()
        # 아이콘이 있는 액션(공휴일 API 키)도 텍스트를 함께 표시
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        prev = QAction("◀", self)
        prev.triggered.connect(lambda: self._cb.on_prev_month())
        self._month_label = QLabel("  ")
        nxt = QAction("▶", self)
        nxt.triggered.connect(lambda: self._cb.on_next_month())
        self._status_label = QLabel("")
        self._vacation_action = QAction(_VACATION_DEFAULT_LABEL, self)
        self._vacation_action.triggered.connect(
            lambda: self._cb.on_manage_vacation()
        )
        switch = QAction("위젯 모드", self)
        switch.triggered.connect(lambda: self._cb.on_switch_mode())
        # 공휴일 API 키 등록·교체 버튼 — 등록 상태를 색 점으로 표시
        self._api_key_action = QAction("공휴일 API 키", self)
        self._api_key_action.triggered.connect(
            lambda: self._cb.on_register_api_key()
        )
        toolbar.addAction(prev)
        toolbar.addWidget(self._month_label)
        toolbar.addAction(nxt)
        toolbar.addSeparator()
        toolbar.addWidget(self._status_label)
        toolbar.addSeparator()
        toolbar.addAction(self._vacation_action)
        toolbar.addSeparator()
        toolbar.addAction(self._api_key_action)
        toolbar.addAction(switch)

        central = QWidget()
        layout = QHBoxLayout(central)
        self._calendar = CalendarWidget(
            self._cb.on_select_day,
            self._cb.on_edit_weekday,
            self._cb.on_edit_day,
        )
        self._status = StatusPanel(
            self._cb.on_clock_out,
            self._cb.on_cancel_clock_out,
            self._cb.on_edit_selected,
            self._cb.on_go_today,
        )
        layout.addWidget(self._calendar, stretch=1)
        layout.addWidget(self._status)
        self.setCentralWidget(central)

    def set_api_key_registered(self, registered: bool) -> None:
        """등록 상태를 색 점(등록=연두, 미등록=노랑)으로 표시한다."""
        color = theme.FG_WORKING if registered else theme.FG_INCOMPLETE
        self._api_key_action.setIcon(_dot_icon(color))

    def render(
        self,
        year: int,
        month: int,
        status: WorkStatus,
        grid: list[list[DayCell]],
        summary: MonthSummary,
        leave: YearLeaveSummary,
        detail: DayDetail | None = None,
    ) -> None:
        self._month_label.setText(f"  {year}년 {month}월  ")
        self._status_label.setText(f"{_STATUS_DOT} {status.value}")
        self._status_label.setStyleSheet(f"color:{_STATUS_COLORS[status]};")
        self._calendar.render_grid(
            grid, selected_date=detail.date if detail else None
        )
        self._status.update_summary(summary, status, leave, detail)
