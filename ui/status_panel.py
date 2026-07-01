"""캘린더 우측 월 현황 status 패널."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QLabel, QProgressBar, QPushButton, QHBoxLayout,
)

from core.attendance import WorkStatus
from core.calendar_model import format_hm
from core.stats import MonthSummary
from ui import theme

_SECONDS_PER_MINUTE = 60


def _fmt_seconds(seconds: int) -> str:
    minutes = max(seconds, 0) // _SECONDS_PER_MINUTE
    return format_hm(minutes)


class StatusPanel(QWidget):
    def __init__(
        self,
        on_clock_out: Callable[[], None],
        on_cancel_clock_out: Callable[[], None],
    ) -> None:
        super().__init__()
        self.setFixedWidth(theme.STATUS_PANEL_WIDTH)
        self._on_clock_out = on_clock_out
        self._on_cancel_clock_out = on_cancel_clock_out

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._title = QLabel("STATUS")
        self._title.setStyleSheet(f"color:{theme.FG_MUTED}; font-weight:bold;")
        self._planned = QLabel()
        self._actual = QLabel()
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setRange(0, 100)
        self._expected_title = QLabel("오늘 예상 퇴근")
        self._expected_title.setStyleSheet(f"color:{theme.FG_MUTED};")
        self._expected = QLabel()
        self._expected.setStyleSheet(
            f"color:{theme.FG_PLANNED}; font-size:20px; font-weight:bold;"
        )

        for w in (self._title, self._planned, self._actual, self._progress,
                  self._expected_title, self._expected):
            layout.addWidget(w)

        layout.addStretch(1)
        self._buttons = QHBoxLayout()
        layout.addLayout(self._buttons)

    def _clear_buttons(self) -> None:
        while self._buttons.count():
            item = self._buttons.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_buttons(self, status: WorkStatus) -> None:
        self._clear_buttons()
        if status == WorkStatus.CLOCKED_OUT:
            cancel = QPushButton("취소")
            cancel.clicked.connect(lambda: self._on_cancel_clock_out())
            reclock = QPushButton("재퇴근")
            reclock.clicked.connect(lambda: self._on_clock_out())
            self._buttons.addWidget(cancel)
            self._buttons.addWidget(reclock)
        else:
            clock = QPushButton("퇴근")
            clock.clicked.connect(lambda: self._on_clock_out())
            self._buttons.addWidget(clock)

    def update_summary(self, summary: MonthSummary, status: WorkStatus) -> None:
        self._planned.setText(
            f"월 계획   {format_hm(summary.planned_minutes)}"
        )
        self._actual.setText(
            f"월 누적   {_fmt_seconds(summary.actual_seconds)}"
        )
        if summary.progress_ratio is None:
            self._progress.setValue(0)
            self._progress.setFormat("계획 없음")
        else:
            pct = int(summary.progress_ratio * 100)
            self._progress.setValue(min(pct, 100))
            self._progress.setFormat(f"{pct}%")
        if summary.expected_clock_out is None:
            self._expected.setText("-")
        else:
            hhmm = summary.expected_clock_out.strftime("%H:%M")
            remain = summary.remaining_seconds or 0
            suffix = (
                f" ({_fmt_seconds(remain)} 남음)" if remain > 0 else " (초과)"
            )
            self._expected.setText(f"{hhmm}{suffix}")
        self._render_buttons(status)
