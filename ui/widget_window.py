"""축약 위젯 모드 창 (프레임리스·always-on-top)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

import config
from core.attendance import WorkStatus
from ui import theme

_STATUS_DOT = "●"
_STATUS_COLORS = {
    WorkStatus.WORKING: theme.FG_WORKING,
    WorkStatus.CLOCKED_OUT: theme.FG_MUTED,
    WorkStatus.NOT_CLOCKED_IN: theme.FG_INCOMPLETE,
}
_MARGIN_H = 12   # 좌우 여백(px)
_MARGIN_V = 10   # 상하 여백(px)
_BORDER_RADIUS = 8  # 모서리 둥글기(px)
_SUB_FONT_PX = 12  # 계획 시간 보조 라인 폰트 (STATUS 패널과 동일)


@dataclass
class WidgetCallbacks:
    on_clock_out: Callable[[], None]
    on_cancel_clock_out: Callable[[], None]
    on_switch_mode: Callable[[], None]
    on_close: Callable[[], None]


@dataclass
class TodayInfo:
    """STATUS 패널의 당일 라인들과 동일한 구성 (텍스트는 호출측에서 생성)."""
    clock_in: str
    expected: str
    plan_range: str
    stay: str
    remaining: str
    vacation: str | None  # 휴가 없으면 None → 라인 숨김
    state_html: str       # 상태 라인 (색상 포함 rich text)


class WidgetWindow(QWidget):
    def __init__(self, callbacks: WidgetCallbacks) -> None:
        super().__init__()
        self._cb = callbacks
        self._drag_offset = QPoint()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setStyleSheet(f"background-color:{theme.BG_BASE}; border-radius:{_BORDER_RADIUS}px;")
        pos = config.get_window_pos()
        if pos:
            self.move(pos[0], pos[1])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(_MARGIN_H, _MARGIN_V, _MARGIN_H, _MARGIN_V)

        top = QHBoxLayout()
        self._status = QLabel()
        expand = QPushButton("전체")
        expand.clicked.connect(lambda: self._cb.on_switch_mode())
        close = QPushButton("✕")
        close.clicked.connect(lambda: self._cb.on_close())
        top.addWidget(self._status)
        top.addStretch(1)
        top.addWidget(expand)
        top.addWidget(close)
        layout.addLayout(top)

        self._header = QLabel()
        layout.addWidget(self._header)

        # STATUS 패널과 동일한 당일 라인:
        # 출근 → 퇴근 예정 → 계획 시간 → 체류 → 남은 → 휴가 → 상태
        self._clock_in = QLabel()
        self._expected = QLabel()
        self._plan_range = QLabel()
        self._plan_range.setStyleSheet(
            f"color:{theme.FG_MUTED}; font-size:{_SUB_FONT_PX}px;"
        )
        self._stay = QLabel()
        self._remaining = QLabel()
        self._vacation = QLabel()
        self._vacation.setStyleSheet(f"color:{theme.FG_VACATION};")
        self._vacation.setVisible(False)
        self._state = QLabel()
        for w in (self._clock_in, self._expected, self._plan_range,
                  self._stay, self._remaining, self._vacation, self._state):
            layout.addWidget(w)

        self._clock_btn = QPushButton("퇴근")
        self._clock_btn.clicked.connect(lambda: self._cb.on_clock_out())
        layout.addWidget(self._clock_btn)

    def render(
        self, status: WorkStatus, header_text: str, today: TodayInfo
    ) -> None:
        self._status.setText(f"{_STATUS_DOT} {status.value}")
        self._status.setStyleSheet(f"color:{_STATUS_COLORS[status]};")
        self._header.setText(header_text)
        self._clock_in.setText(today.clock_in)
        self._expected.setText(today.expected)
        self._plan_range.setText(today.plan_range)
        self._stay.setText(today.stay)
        self._remaining.setText(today.remaining)
        self._vacation.setText(today.vacation or "")
        self._vacation.setVisible(bool(today.vacation))
        self._state.setText(today.state_html)
        self.adjustSize()  # 휴가 라인 표시/숨김에 따라 높이 재계산

    # 드래그 이동 + 위치 저장
    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        config.save_window_pos(self.x(), self.y())
