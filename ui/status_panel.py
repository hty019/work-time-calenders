"""캘린더 우측 월 현황 status 패널."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QLabel, QProgressBar, QPushButton, QHBoxLayout,
)

from core.attendance import WorkStatus
from core.calendar_model import format_hm
from core.stats import MonthSummary, ProgressLevel, progress_state
from ui import theme

_SECONDS_PER_MINUTE = 60
_MINUTES_PER_HOUR = 60
_SECONDS_PER_HOUR = 3600
_EXPECTED_FONT_PX = 20
_CAPTION_FONT_PX = 11
_PROGRESS_BAR_HEIGHT_PX = 6  # 얇은 바 스타일 유지
_PROGRESS_BAR_RADIUS_PX = 3

_PROGRESS_COLORS = {
    ProgressLevel.NORMAL: theme.BG_PROGRESS,
    ProgressLevel.OVER: theme.BG_PROGRESS_OVER,
    ProgressLevel.CRITICAL: theme.BG_PROGRESS_CRIT,
    ProgressLevel.EXCEEDED: theme.BG_PROGRESS_MAX,
}


def _expected_style(warn: bool) -> str:
    color = theme.FG_RANGE_WARN if warn else theme.FG_PLANNED
    return f"color:{color}; font-size:{_EXPECTED_FONT_PX}px; font-weight:bold;"


def _progress_style(level: ProgressLevel) -> str:
    """텍스트 없는 얇은 바 형태를 유지하면서 게이지 색상만 단계별로 변경."""
    return f"""
    QProgressBar {{
        background-color: {theme.BG_ELEVATED};
        border: none;
        border-radius: {_PROGRESS_BAR_RADIUS_PX}px;
        max-height: {_PROGRESS_BAR_HEIGHT_PX}px;
    }}
    QProgressBar::chunk {{
        background-color: {_PROGRESS_COLORS[level]};
        border-radius: {_PROGRESS_BAR_RADIUS_PX}px;
    }}
    """


def _fmt_seconds(seconds: int) -> str:
    minutes = max(seconds, 0) // _SECONDS_PER_MINUTE
    return format_hm(minutes)


def _fmt_hours(minutes: int) -> str:
    """법정 기준·최대 가능용: 분은 버리고 'Nh' 만 표시."""
    return f"{minutes // _MINUTES_PER_HOUR}h"


def progress_caption(
    pct: int, level: ProgressLevel, actual_seconds: int, required_minutes: int
) -> str:
    """진행률 바 상단 캡션. 법정 이내면 진행도 %, 초과면 +초과시간(h)."""
    if level is ProgressLevel.NORMAL:
        return f"근로 시간 진행도: {pct}%"
    over_hours = (
        actual_seconds // _SECONDS_PER_HOUR
        - required_minutes // _MINUTES_PER_HOUR
    )
    return f"초과 근로 진행: +{over_hours}h"


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
        self._required = QLabel()  # 법정 요구 근로시간(평일 공휴일 차감 반영)
        self._max = QLabel()       # 최대 근로 가능시간(주 52h 기준)
        self._planned = QLabel()
        self._recog_planned = QLabel()  # 월 (가)계획 합계(휴게 차감)
        self._actual = QLabel()
        self._progress_caption = QLabel()  # 진행률 바 상단 상태 텍스트
        self._progress_caption.setStyleSheet(
            f"color:{theme.FG_MUTED}; font-size:{_CAPTION_FONT_PX}px;"
        )
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setStyleSheet(_progress_style(ProgressLevel.NORMAL))
        self._expected_title = QLabel("오늘 예상 퇴근")
        self._expected_title.setStyleSheet(f"color:{theme.FG_MUTED};")
        self._expected = QLabel()
        self._expected.setStyleSheet(_expected_style(warn=False))

        for w in (self._title, self._required, self._max, self._planned,
                  self._recog_planned, self._actual, self._progress_caption,
                  self._progress, self._expected_title, self._expected):
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
        self._required.setText(
            f"법정 기준   {_fmt_hours(summary.required_minutes)}"
        )
        self._max.setText(
            f"최대 가능   {_fmt_hours(summary.max_minutes)}"
        )
        self._planned.setText(
            f"실 계획   {format_hm(summary.planned_minutes)}"
        )
        self._recog_planned.setText(
            f"(가)계획   {format_hm(summary.recog_planned_minutes)}"
        )
        self._actual.setText(
            f"월 누적   {_fmt_seconds(summary.actual_seconds)}"
        )
        # 진행률: 법정 기준 이내 녹색 → 초과 시 최대 가능 기준 주황 → +20h 빨강
        pct, level = progress_state(
            summary.actual_seconds,
            summary.required_minutes,
            summary.max_minutes,
        )
        self._progress.setValue(pct)
        self._progress.setStyleSheet(_progress_style(level))
        self._progress_caption.setText(
            progress_caption(
                pct, level, summary.actual_seconds, summary.required_minutes
            )
        )
        if summary.expected_clock_out is None:
            self._expected.setText("-")
            self._expected.setStyleSheet(_expected_style(warn=False))
        else:
            hhmm = summary.expected_clock_out.strftime("%H:%M")
            remain = summary.remaining_seconds or 0
            suffix = (
                f" ({_fmt_seconds(remain)} 남음)" if remain > 0 else " (초과)"
            )
            warn = summary.expected_exceeds_range
            warn_text = "\n⚠ (가)계획 종료 초과" if warn else ""
            self._expected.setText(f"{hhmm}{suffix}{warn_text}")
            self._expected.setStyleSheet(_expected_style(warn=warn))
        self._render_buttons(status)
