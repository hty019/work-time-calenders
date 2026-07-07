"""전체화면 메인 윈도우: 캘린더 + status 패널 + 툴바."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QToolBar, QLabel,
    QSizePolicy, QToolButton,
)
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut,
)

from core.attendance import WorkStatus
from core.calendar_model import DayCell
from core.day_detail import DayDetail
from core.stats import MonthSummary
from core.vacation import YearLeaveSummary
from ui import theme
from ui.calendar_widget import CalendarWidget
from ui.status_panel import StatusPanel

_VACATION_DEFAULT_LABEL = "휴가 관리"


@dataclass
class MainWindowCallbacks:
    on_clock_out: Callable[[], None]
    on_cancel_clock_out: Callable[[], None]
    on_select_day: Callable[[str, str], None]  # (날짜, 선택 모드)
    on_edit_day: Callable[[str], None]
    on_edit_weekday: Callable[[int], None]
    on_clear_selection: Callable[[], None]
    on_prev_month: Callable[[], None]
    on_next_month: Callable[[], None]
    on_switch_mode: Callable[[], None]
    on_manage_vacation: Callable[[], None]
    on_edit_selected: Callable[[], None]
    on_go_today: Callable[[], None]
    on_register_api_key: Callable[[], None]
    on_show_help: Callable[[], None]
    on_open_ai: Callable[[], None]


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
        # 아이콘 슬롯을 점 크기에 맞춰 버튼 좌우 여백이 균일하도록 함
        toolbar.setIconSize(
            QSize(theme.TOOLBAR_DOT_ICON_PX, theme.TOOLBAR_DOT_ICON_PX)
        )
        self.addToolBar(toolbar)
        prev = QAction("◀", self)
        prev.triggered.connect(lambda: self._cb.on_prev_month())
        self._month_label = QLabel("  ")
        nxt = QAction("▶", self)
        nxt.triggered.connect(lambda: self._cb.on_next_month())
        # ESC 로 다중 선택 해제
        QShortcut(
            QKeySequence(Qt.Key_Escape), self,
            activated=lambda: self._cb.on_clear_selection(),
        )
        # Cmd+E = 선택 일자 수정 ([수정] 버튼과 동일)
        QShortcut(
            QKeySequence("Ctrl+E"), self,
            activated=lambda: self._cb.on_edit_selected(),
        )
        # Space = 오늘로 복귀 ([오늘] 버튼과 동일)
        QShortcut(
            QKeySequence(Qt.Key_Space), self,
            activated=lambda: self._cb.on_go_today(),
        )
        self._vacation_action = QAction(_VACATION_DEFAULT_LABEL, self)
        self._vacation_action.triggered.connect(
            lambda: self._cb.on_manage_vacation()
        )
        switch = QAction("위젯 모드", self)
        switch.triggered.connect(lambda: self._cb.on_switch_mode())
        help_action = QAction("도움말", self)
        help_action.triggered.connect(lambda: self._cb.on_show_help())
        ai_action = QAction("AI", self)
        ai_action.triggered.connect(lambda: self._cb.on_open_ai())
        # 공휴일 API 키 등록·교체 버튼 — 등록 상태를 색 점으로 표시
        self._api_key_action = QAction("공휴일 API 키", self)
        self._api_key_action.triggered.connect(
            lambda: self._cb.on_register_api_key()
        )
        # 좌측: 월 이동 / 우측: 공휴일 API 키·휴가 관리·위젯 모드
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addAction(prev)
        toolbar.addWidget(self._month_label)
        toolbar.addAction(nxt)
        toolbar.addWidget(spacer)
        toolbar.addAction(ai_action)
        toolbar.addSeparator()
        toolbar.addAction(help_action)
        toolbar.addSeparator()
        toolbar.addAction(self._api_key_action)
        toolbar.addSeparator()
        toolbar.addAction(self._vacation_action)
        toolbar.addSeparator()
        toolbar.addAction(switch)
        # 메뉴 버튼 호버 시 손가락 커서
        for button in toolbar.findChildren(QToolButton):
            button.setCursor(Qt.PointingHandCursor)

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
        multi_dates: set[str] | None = None,
    ) -> None:
        """multi_dates 가 None 이 아니면(2일 이상) 다중 선택 상태."""
        self._month_label.setText(f"  {year}년 {month}월  ")
        self._calendar.render_grid(
            grid,
            selected_date=detail.date if detail else None,
            multi_selected=multi_dates,
        )
        self._status.update_summary(
            summary, status, leave, detail,
            multi_count=len(multi_dates) if multi_dates else 1,
        )
