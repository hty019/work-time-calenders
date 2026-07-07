"""캘린더 우측 월 현황 status 패널."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QLabel, QProgressBar, QPushButton, QHBoxLayout,
    QTextEdit,
)

from core.attendance import WorkStatus
from core.calendar_model import format_hm
from core.day_detail import DayDetail, KIND_PAST, KIND_TODAY
from core.stats import MonthSummary, ProgressLevel, progress_state
from core.vacation import (
    FULL_DAY_MINUTES,
    YearLeaveSummary,
    minutes_to_days_str,
)
from ui import theme

_SECONDS_PER_MINUTE = 60
_MINUTES_PER_HOUR = 60
_SECONDS_PER_HOUR = 3600
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

# 상태 라인 상태키 → (색상, 굵게)
_STATE_STYLES = {
    "off": (theme.FG_MUTED, False),        # 미출근
    "done": (theme.FG_MUTED, False),       # 퇴근 완료 (판정 불가)
    "done_normal": (theme.FG_DONE_TODAY, False),  # 정상 퇴근 (녹색)
    "early": (theme.FG_OVERDUE, False),    # 조기 퇴근 (주황)
    "normal": (theme.FG_DONE_TODAY, False),  # 정상 근무중 (녹색)
    "reached": (theme.FG_DONE_TODAY, True),  # 예상 퇴근 달성 (녹색 bold)
    "warn": (theme.FG_RANGE_WARN, False),    # 범위 초과 예상 (노랑)
    "over": (theme.FG_RANGE_WARN, True),     # 계획 퇴근 실제 초과 (노랑 bold)
}


def state_rich_text(text: str, key: str) -> str:
    """상태 라인 HTML: '상태: ' 접두는 흰색 고정, 문구만 상태 색상."""
    color, bold = _STATE_STYLES[key]
    weight = "bold" if bold else "normal"
    prefix, _, body = text.partition(": ")
    return (
        f'<span style="color:{theme.FG_DATE};">{prefix}: </span>'
        f'<span style="color:{color}; font-weight:{weight};">{body}</span>'
    )


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


def expected_line(
    expected_hhmm: str | None, basis_minutes: int | None
) -> str:
    """퇴근 예정 시각 라인. 산정 기준 순근무 시간을 괄호로 병기한다.

    경고 표시는 상태 라인(state_display)이 담당한다.
    """
    if expected_hhmm is None:
        return "퇴근 예정 시간: -"
    base = f"퇴근 예정 시간: {expected_hhmm}"
    if basis_minutes is not None:
        base += f" ({format_hm(basis_minutes)} 근무 기준)"
    return base


def state_display(
    status: WorkStatus,
    recog_end_passed: bool,
    exceeds_range: bool,
    reached: bool,
    clocked_out_early: bool | None = None,
) -> tuple[str, str]:
    """상태 라인의 (문구, 상태키) 산출. 상태키는 색상·굵기 매핑용.

    우선순위: 미출근/퇴근(조기·정상·판정 불가) > 계획 퇴근 실제
    초과(over) > 범위 초과 예상(warn) > 예상 퇴근 달성(reached) >
    정상 근무중.
    """
    if status is WorkStatus.NOT_CLOCKED_IN:
        return "상태: 미출근", "off"
    if status is WorkStatus.CLOCKED_OUT:
        if clocked_out_early is True:
            return "상태: 조기 퇴근", "early"
        if clocked_out_early is False:
            return "상태: 정상 퇴근", "done_normal"
        return "상태: 퇴근 완료", "done"  # 예상 퇴근 없음 → 판정 불가
    if recog_end_passed:
        return "상태: ⚠ 계획 시간 범위 초과!!", "over"
    if exceeds_range:
        return "상태: ⚠ 계획 범위 초과 예상", "warn"
    if reached:
        return "상태: 금일 근무 달성 · 퇴근 가능", "reached"
    return "상태: 정상 근무중", "normal"


def stay_line(stay_seconds: int | None) -> str:
    """출근 후 체류 시간(휴게 포함 경과) 라인. 기록 없으면 '-'."""
    if stay_seconds is None:
        return "체류 시간: -"
    return f"체류 시간: {_fmt_seconds(stay_seconds)}"


def remaining_line(remaining_seconds: int | None) -> str:
    """퇴근 예정까지 남은 시간 라인. 예정 없으면 '-', 지났으면 0."""
    if remaining_seconds is None:
        return "남은 시간: -"
    return f"남은 시간: {_fmt_seconds(remaining_seconds)}"


def plan_range_line(detail: DayDetail) -> str:
    """(가)계획 범위 라인. 미설정이면 '-'."""
    plan_range = (
        f"{detail.recog_start_hm}~{detail.recog_end_hm}"
        if detail.recog_start_hm is not None
        else "-"
    )
    return f"계획 시간: {plan_range}"


def past_lines(detail: DayDetail) -> list[str]:
    """과거 일자 표시 라인: 출근/퇴근 시각, (가)계획 범위."""
    return [
        f"출근 시간: {detail.clock_in_hm or '-'}",
        f"퇴근 시간: {detail.clock_out_hm or '-'}",
        plan_range_line(detail),
    ]


def work_line(detail: DayDetail) -> str | None:
    """과거 일자 근무 시간 라인. 퇴근 완료가 아니면 None(숨김)."""
    if detail.clock_out_hm is None or detail.work_seconds is None:
        return None
    return f"근무 시간: {_fmt_seconds(detail.work_seconds)}"


def future_lines(detail: DayDetail) -> list[str]:
    """미래 일자 표시 라인: 실 계획(분), (가)계획 범위."""
    recog_range = (
        f"{detail.recog_start_hm} ~ {detail.recog_end_hm}"
        if detail.recog_start_hm is not None
        else "-"
    )
    return [
        f"실 계획: {format_hm(detail.planned_minutes)}",
        f"(가)계획 시간: {recog_range}",
    ]


def vacation_line(detail: DayDetail) -> str | None:
    """휴가 라인. 휴가가 없으면 None(숨김)."""
    if detail.vacation_minutes <= 0:
        return None
    hours = detail.vacation_minutes // _MINUTES_PER_HOUR
    if detail.vacation_minutes >= FULL_DAY_MINUTES:
        return f"휴가: {hours}h (1day)"
    if detail.vacation_start_hm is not None:
        return (
            f"휴가: {hours}h "
            f"({detail.vacation_start_hm} ~ {detail.vacation_end_hm})"
        )
    return f"휴가: {hours}h"


def past_state_display(detail: DayDetail) -> tuple[str, str]:
    """과거 일자 상태 라인 (문구, 상태키).

    미출근 > 퇴근 미기록(경고) > 조기/정상 퇴근 > 판정 불가 순.
    """
    if not detail.has_record:
        return "상태: 미출근", "off"
    if detail.clock_out_hm is None:
        return "상태: ⚠ 퇴근 미기록", "over"
    if detail.clocked_out_early is True:
        return "상태: 조기 퇴근", "early"
    if detail.clocked_out_early is False:
        return "상태: 정상 퇴근", "done_normal"
    return "상태: 퇴근 완료", "done"


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
        on_edit: Callable[[], None],
        on_today: Callable[[], None],
    ) -> None:
        super().__init__()
        self.setFixedWidth(theme.STATUS_PANEL_WIDTH)
        self._on_clock_out = on_clock_out
        self._on_cancel_clock_out = on_cancel_clock_out
        self._on_edit = on_edit
        self._on_today = on_today

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
        # 진행률 바 하단 금일 현황 4줄 (동일 폰트·색상)
        self._clock_in = QLabel()   # 금일 출근 시각
        self._expected = QLabel()   # 퇴근 예정 시각 (+경고)
        self._expected.setWordWrap(True)
        self._stay = QLabel()       # 체류 시간(휴게 포함 경과)
        self._remaining = QLabel()  # 퇴근 예정까지 남은 시간
        self._state = QLabel()      # 상태 라인 (색상·굵기로 경고 표시)
        self._vacation = QLabel()   # 휴가 라인 (없으면 숨김, 연보라)
        self._vacation.setStyleSheet(f"color:{theme.FG_VACATION};")
        self._vacation.setVisible(False)
        # 당일 메모 박스: 테두리 사각형, 넘치면 스크롤(스크롤바 숨김)
        self._memo_box = QTextEdit()
        self._memo_box.setReadOnly(True)
        self._memo_box.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._memo_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._memo_box.setMaximumHeight(theme.STATUS_MEMO_MAX_HEIGHT)
        self._memo_box.setStyleSheet(theme.memo_box_style())
        self._memo_box.setVisible(False)
        self._expected_sub = QLabel()  # 회색 계획 퇴근 안내
        self._expected_sub.setStyleSheet(
            f"color:{theme.FG_MUTED}; font-size:{_SUB_FONT_PX}px;"
        )
        self._expected_sub.setVisible(False)

        # 순서: 출근 → 퇴근 예정 → 계획 퇴근 안내 → 체류 → 남은 → 휴가
        #       → 상태. 메모는 stretch 아래 = 버튼 바로 위에 고정
        for w in (self._title, self._required, self._max, self._planned,
                  self._recog_planned, self._actual, self._leave,
                  self._progress_caption, self._progress,
                  self._clock_in, self._expected, self._expected_sub,
                  self._stay, self._remaining, self._vacation,
                  self._state):
            layout.addWidget(w)

        layout.addStretch(1)
        layout.addWidget(self._memo_box)
        self._buttons = QHBoxLayout()
        layout.addLayout(self._buttons)

    def _clear_buttons(self) -> None:
        while self._buttons.count():
            item = self._buttons.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_buttons(
        self, status: WorkStatus, kind: str, multi_count: int = 1
    ) -> None:
        """오늘: [수정][퇴근/퇴근 취소] · 과거/미래: [수정][오늘].

        다중 선택(2일 이상) 시 수정 버튼 라벨은 '(N) 수정'.
        """
        self._clear_buttons()
        label = "수정" if multi_count <= 1 else f"({multi_count}) 수정"
        edit = QPushButton(label)
        edit.clicked.connect(lambda: self._on_edit())
        self._buttons.addWidget(edit)
        if kind == KIND_TODAY:
            if status == WorkStatus.CLOCKED_OUT:
                cancel = QPushButton("퇴근 취소")
                cancel.clicked.connect(lambda: self._on_cancel_clock_out())
                self._buttons.addWidget(cancel)
            else:
                clock = QPushButton("퇴근")
                clock.clicked.connect(lambda: self._on_clock_out())
                self._buttons.addWidget(clock)
        else:
            today_btn = QPushButton("오늘")
            today_btn.clicked.connect(lambda: self._on_today())
            self._buttons.addWidget(today_btn)

    def update_summary(
        self,
        summary: MonthSummary,
        status: WorkStatus,
        leave: YearLeaveSummary,
        detail: DayDetail | None = None,
        multi_count: int = 1,
    ) -> None:
        """월 요약 + 선택 날짜(detail) 상세를 렌더링한다.

        detail 이 None 이면 오늘 기준으로 동작한다.
        multi_count 는 다중 선택된 일 수 (수정 버튼 라벨에 반영).
        """
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
        kind = detail.kind if detail is not None else KIND_TODAY
        if kind == KIND_TODAY:
            self._render_today_detail(summary, status, detail)
        elif kind == KIND_PAST:
            self._render_past_detail(detail)
        else:
            self._render_future_detail(detail)
        vac_text = vacation_line(detail) if detail is not None else None
        self._vacation.setText(vac_text or "")
        self._vacation.setVisible(bool(vac_text))
        memo = detail.memo if detail is not None else None
        if (memo or "") != self._memo_box.toPlainText():
            self._memo_box.setPlainText(memo or "")
        self._memo_box.setVisible(bool(memo))
        self._render_buttons(status, kind, multi_count)

    def _render_today_detail(
        self,
        summary: MonthSummary,
        status: WorkStatus,
        detail: DayDetail | None,
    ) -> None:
        expected_hhmm = (
            summary.expected_clock_out.strftime("%H:%M")
            if summary.expected_clock_out is not None
            else None
        )
        self._clock_in.setText(clock_in_line(summary.today_clock_in_hm))
        self._expected.setText(
            expected_line(expected_hhmm, summary.expected_basis_minutes)
        )
        self._stay.setText(stay_line(summary.today_stay_seconds))
        self._stay.setVisible(True)
        self._remaining.setText(remaining_line(summary.remaining_seconds))
        self._remaining.setVisible(True)
        recog_end_passed = (
            summary.today_recog_end_hm is not None and summary.recog_end_passed
        )
        reached = (
            summary.remaining_seconds is not None
            and summary.remaining_seconds <= 0
        )
        state_text, state_key = state_display(
            status,
            recog_end_passed,
            summary.expected_exceeds_range,
            reached,
            summary.today_clocked_out_early,
        )
        self._state.setText(state_rich_text(state_text, state_key))
        self._state.setVisible(True)
        # 다른 날짜와 동일한 '계획 시간: HH:MM~HH:MM' 형식으로 표시
        sub = plan_range_line(detail) if detail is not None else None
        self._expected_sub.setText(sub or "")
        self._expected_sub.setVisible(bool(sub))

    def _render_past_detail(self, detail: DayDetail) -> None:
        in_line, out_line, plan_line = past_lines(detail)
        self._clock_in.setText(in_line)
        self._expected.setText(out_line)
        self._expected_sub.setVisible(False)
        # 퇴근 완료일은 퇴근 시간과 계획 시간 사이에 근무 시간을 끼워 넣는다.
        # 라벨은 기본 색, 값만 녹색(셀 근로 인정시간 강조와 동일) 처리
        work = work_line(detail)
        self._stay.setText(
            state_rich_text(work, "normal") if work is not None else plan_line
        )
        self._stay.setVisible(True)
        self._remaining.setText(plan_line)
        self._remaining.setVisible(work is not None)
        state_text, state_key = past_state_display(detail)
        self._state.setText(state_rich_text(state_text, state_key))
        self._state.setVisible(True)

    def _render_future_detail(self, detail: DayDetail) -> None:
        plan_line, recog_line = future_lines(detail)
        self._clock_in.setText(plan_line)
        self._expected.setText(recog_line)
        self._expected_sub.setVisible(False)
        self._stay.setVisible(False)
        self._remaining.setVisible(False)
        self._state.setVisible(False)
