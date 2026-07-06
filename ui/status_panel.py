"""캘린더 우측 월 현황 status 패널."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QLabel, QProgressBar, QPushButton, QHBoxLayout,
)

from core.attendance import WorkStatus
from core.calendar_model import format_hm
from core.stats import MonthSummary, ProgressLevel, progress_state
from core.vacation import YearLeaveSummary, minutes_to_days_str
from ui import theme

_SECONDS_PER_MINUTE = 60
_MINUTES_PER_HOUR = 60
_SECONDS_PER_HOUR = 3600
_EXPECTED_FONT_PX = 14  # '금일 퇴근 예정 시간: HH:MM (남음)' 한 줄이 패널 폭에 맞도록
_CAPTION_FONT_PX = 11
_SUB_FONT_PX = 12
_PROGRESS_BAR_HEIGHT_PX = 6  # 얇은 바 스타일 유지
_PROGRESS_BAR_RADIUS_PX = 3

_PROGRESS_COLORS = {
    ProgressLevel.NORMAL: theme.BG_PROGRESS,
    ProgressLevel.OVER: theme.BG_PROGRESS_OVER,
    ProgressLevel.CRITICAL: theme.BG_PROGRESS_CRIT,
    ProgressLevel.EXCEEDED: theme.BG_PROGRESS_MAX,
}

# 예상 퇴근 영역 상태 → 본문 색상
_EXPECTED_COLORS = {
    "pending": theme.FG_PLANNED,   # 예상 퇴근 대기 (연파랑)
    "warn": theme.FG_RANGE_WARN,   # (가)계획 종료 초과 (노랑)
    "done": theme.FG_DONE_TODAY,   # 퇴근 완료 → 금일 근로 시간 (녹색)
    "overdue": theme.FG_OVERDUE,   # 미퇴근 + 계획 퇴근 초과 (주황)
}


def _expected_style(state: str) -> str:
    color = _EXPECTED_COLORS[state]
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


def clock_in_line(clock_in_hm: str | None) -> str:
    """진행률 바 하단의 금일 출근 시각 라인. 기록 없으면 '-'."""
    return f"금일 출근 시간: {clock_in_hm or '-'}"


def expected_display(
    status: WorkStatus,
    expected_hhmm: str | None,
    remaining_seconds: int | None,
    today_work_seconds: int | None,
    exceeds_range: bool,
    recog_end_hm: str | None,
    recog_end_passed: bool,
) -> tuple[str, str | None, str]:
    """퇴근 예정 영역의 (본문, 하단 보조, 상태) 산출.

    본문은 '금일 퇴근 예정 시간: HH:MM (Xh Ym 남음)' 형식, 퇴근 완료·예상
    퇴근 달성 시 '금일 근로 시간: Xh Ym' 으로 전환한다.
    '계획 퇴근'은 (가)계획 종료 시각(recog_end_hm)을 뜻한다.
    상태: pending(대기)·warn((가)계획 초과)·done(퇴근 완료, 녹색)·
    overdue(미퇴근 + (가)계획 퇴근 초과, 주황).
    """
    work_text = _fmt_seconds(today_work_seconds or 0)
    sub = f"계획 퇴근 시간: ~{recog_end_hm}" if recog_end_hm else None
    if status is WorkStatus.WORKING and recog_end_hm and recog_end_passed:
        # 퇴근 미기록 상태로 (가)계획 퇴근 시각을 넘김
        return (
            f"금일 근로 시간: {work_text}\n⚠ 계획 수정 필요",
            sub,
            "overdue",
        )
    reached = (
        expected_hhmm is not None and (remaining_seconds or 0) <= 0
    )
    if status is WorkStatus.CLOCKED_OUT and today_work_seconds is not None:
        return f"금일 근로 시간: {work_text}", sub, "done"
    if status is WorkStatus.WORKING and reached:
        # 예상 퇴근 시각 달성: 녹색 금일 근로 시간으로 전환
        return f"금일 근로 시간: {work_text}", sub, "done"
    if expected_hhmm is None:
        return "금일 퇴근 예정 시간: -", None, "pending"
    remain_text = _fmt_seconds(remaining_seconds or 0)
    warn_text = "\n⚠ (가)계획 종료 초과" if exceeds_range else ""
    return (
        f"금일 퇴근 예정 시간: {expected_hhmm} ({remain_text} 남음){warn_text}",
        None,
        "warn" if exceeds_range else "pending",
    )


def leave_line(leave: YearLeaveSummary) -> str:
    """연차 현황 라인: 잔여 / 총(일). 총 연차 미설정이면 '-'."""
    if leave.total_minutes is None:
        return "연차   -"
    remaining = minutes_to_days_str(leave.remaining_minutes)
    total = minutes_to_days_str(leave.total_minutes)
    return f"연차   {remaining} / {total}"


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
        self._leave = QLabel()  # 연차 잔여/총 현황
        self._progress_caption = QLabel()  # 진행률 바 상단 상태 텍스트
        self._progress_caption.setStyleSheet(
            f"color:{theme.FG_MUTED}; font-size:{_CAPTION_FONT_PX}px;"
        )
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setStyleSheet(_progress_style(ProgressLevel.NORMAL))
        self._clock_in = QLabel()  # 금일 출근 시각
        self._expected = QLabel()
        self._expected.setWordWrap(True)
        self._expected.setStyleSheet(_expected_style("pending"))
        self._expected_sub = QLabel()  # 회색 계획 퇴근 안내
        self._expected_sub.setStyleSheet(
            f"color:{theme.FG_MUTED}; font-size:{_SUB_FONT_PX}px;"
        )
        self._expected_sub.setVisible(False)

        for w in (self._title, self._required, self._max, self._planned,
                  self._recog_planned, self._actual, self._leave,
                  self._progress_caption, self._progress,
                  self._clock_in, self._expected, self._expected_sub):
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

    def update_summary(
        self,
        summary: MonthSummary,
        status: WorkStatus,
        leave: YearLeaveSummary,
    ) -> None:
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
        self._leave.setText(leave_line(leave))
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
        expected_hhmm = (
            summary.expected_clock_out.strftime("%H:%M")
            if summary.expected_clock_out is not None
            else None
        )
        self._clock_in.setText(clock_in_line(summary.today_clock_in_hm))
        text, sub, state = expected_display(
            status,
            expected_hhmm,
            summary.remaining_seconds,
            summary.today_work_seconds,
            summary.expected_exceeds_range,
            summary.today_recog_end_hm,
            summary.recog_end_passed,
        )
        self._expected.setText(text)
        self._expected.setStyleSheet(_expected_style(state))
        self._expected_sub.setText(sub or "")
        self._expected_sub.setVisible(bool(sub))
        self._render_buttons(status)
