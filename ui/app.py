"""Qt 앱 조립·모드 전환·주기 갱신 컨트롤러."""
from __future__ import annotations

import os
import sys
from typing import Callable, NamedTuple

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import config
from core import timeutil
from core.attendance import AttendanceService
from core.calendar_model import build_month_grid
from core.day_detail import build_day_detail
from core.day_state import (
    DayPlanClipboard,
    DayState,
    apply_clipboard,
    paste_targets,
    restore_day,
    snapshot_day,
)
from core.holidays import HolidayClient, verify_service_key
from core.plan import PlanService, weekday_dates
from core.recognition import (
    RecognitionRange,
    RecognitionService,
    validate_range_against_plan,
)
from core.stats import build_month_summary
from core.storage import Storage
from core.calendar_nav import (
    rectangle_selection,
    resolve_nav_base,
    step_within_month,
)
from core.vacation import Vacation, VacationService, YearLeaveSummary
from ui import theme
from ui.ai_dialog import open_ai_dialog
from ui.api_key_dialog import open_api_key_dialog
from ui.calendar_widget import SELECT_RANGE, SELECT_SINGLE, SELECT_TOGGLE
from ui.day_dialog import open_day_dialog
from ui.help_dialog import open_help_dialog
from ui.main_window import MainWindow, MainWindowCallbacks
from ui.status_panel import (
    clock_in_line,
    expected_line,
    plan_range_line,
    remaining_line,
    state_display,
    state_rich_text,
    stay_line,
    vacation_line,
)
from ui.vacation_dialog import open_vacation_dialog
from ui.bulk_plan_dialog import open_bulk_plan_dialog
from ui.widget_window import WidgetWindow, WidgetCallbacks, TodayInfo

_MINUTE_SECONDS = 60
_SYNC_BUFFER_MS = 100
_WEEKDAY_NAMES = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


class AppController:
    def __init__(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyleSheet(theme.base_stylesheet())

        self._storage = Storage(config.db_path())
        self._service = AttendanceService(self._storage)
        self._plans = PlanService(self._storage)
        self._recog = RecognitionService(self._storage)
        self._vacations = VacationService(self._storage)
        self._holidays = HolidayClient(
            config.get_service_key(), config.holidays_cache_path()
        )

        now = timeutil.now()
        self._view_year, self._view_month = now.year, now.month
        self._selected_date = timeutil.today_str(now)
        # Cmd+클릭 다중 선택 날짜 (선택 순서 유지, 2일 이상일 때만 사용)
        self._multi_dates: list[str] = []
        # Shift 사각형 선택의 고정 꼭짓점과, 그 시점의 기존 선택(합집합 기준).
        # None 이면 다음 Shift 입력 때 현재 선택 일자를 앵커로 잡는다.
        self._range_anchor: str | None = None
        self._range_base: list[str] = []
        # 복사 버퍼(단일 일자) · 마지막 변경 되돌리기 스냅샷(단일 단계)
        self._clipboard: DayPlanClipboard | None = None
        self._undo: list[DayState] | None = None

        callbacks = MainWindowCallbacks(
            on_clock_out=self._handle_clock_out,
            on_cancel_clock_out=self._handle_cancel_clock_out,
            on_select_day=self._handle_select_day,
            on_edit_day=self._handle_edit_day,
            on_edit_weekday=self._handle_edit_weekday,
            on_clear_selection=self._handle_clear_selection,
            on_prev_month=self._handle_prev_month,
            on_next_month=self._handle_next_month,
            on_switch_mode=self._handle_switch_mode,
            on_manage_vacation=self._handle_manage_vacation,
            on_edit_selected=self._handle_edit_selected,
            on_go_today=self._handle_go_today,
            on_navigate=self._handle_navigate,
            on_register_api_key=self._handle_register_api_key,
            on_show_help=lambda: open_help_dialog(self._window),
            on_open_ai=self._handle_open_ai,
            on_undo=self._handle_undo,
            on_copy_day=self._handle_copy_day,
            on_paste_day=self._handle_paste_day,
        )
        self._window = MainWindow(callbacks)
        self._window.set_api_key_registered(
            config.get_service_key() is not None
        )
        self._timer = QTimer(self._window)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)

        self._widget = WidgetWindow(WidgetCallbacks(
            on_switch_mode=lambda: self._show_mode(config.MODE_FULL),
            on_close=self._app.quit,
        ))
        self._mode = config.get_last_mode()
        # 정상 종료 시 진행 중이면 자동 퇴근 저장 (강제 종료는 대상 아님)
        self._app.aboutToQuit.connect(self._handle_app_exit)

    # --- 갱신 -----------------------------------------------------------
    def _refresh(self) -> None:
        now = timeutil.now()
        today = timeutil.today_str(now)
        year, month = self._view_year, self._view_month
        records = {r.work_date: r for r in self._storage.list_month(year, month)}
        holidays = self._holidays.get_holidays(year, month)
        is_current = (year, month) == (now.year, now.month)
        today_seconds = (
            self._service.today_in_progress_seconds() if is_current else None
        )
        grid = build_month_grid(
            year, month, today, records, holidays,
            effective_planned=lambda d: self._plans.effective_minutes(d, holidays),
            today_seconds=today_seconds,
            recognition=self._storage.get_recognition,
            vacation=self._storage.get_vacation,
            memo=self._storage.get_memo,
        )
        summary = build_month_summary(
            self._storage, self._service, self._plans,
            year, month, holidays, now,
        )
        status = self._service.today_status()
        leave = self._vacations.year_summary(now.year)
        detail = build_day_detail(
            self._storage, self._plans, holidays, self._selected_date, today
        )
        multi = (
            set(self._multi_dates) if len(self._multi_dates) >= 2 else None
        )
        self._window.render(
            year, month, status, grid, summary, leave, detail,
            multi_dates=multi,
        )
        self._render_widget(summary, status)

    def _render_widget(self, summary, status) -> None:
        # STATUS 패널의 당일 라인과 동일한 구성 (전체화면에서 다른 달을
        # 보고 있어도 여기서는 항상 오늘 기준 detail 을 사용)
        now = timeutil.now()
        today = timeutil.today_str(now)
        holidays = self._holidays.get_holidays(now.year, now.month)
        detail = build_day_detail(
            self._storage, self._plans, holidays, today, today
        )
        expected_hhmm = (
            summary.expected_clock_out.strftime("%H:%M")
            if summary.expected_clock_out is not None
            else None
        )
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
        today_info = TodayInfo(
            clock_in=clock_in_line(summary.today_clock_in_hm),
            expected=expected_line(
                expected_hhmm, summary.expected_basis_minutes
            ),
            plan_range=plan_range_line(detail),
            stay=stay_line(summary.today_stay_seconds),
            remaining=remaining_line(summary.remaining_seconds),
            vacation=vacation_line(detail),
            state_html=state_rich_text(state_text, state_key),
        )
        self._widget.render(today_info)

    def _ms_until_next_minute(self) -> int:
        now = timeutil.now()
        remaining = _MINUTE_SECONDS - now.second - now.microsecond / 1_000_000
        return int(remaining * 1000) + _SYNC_BUFFER_MS

    def _tick(self) -> None:
        self._refresh()
        self._timer.start(self._ms_until_next_minute())

    # --- 핸들러 ---------------------------------------------------------
    def _snapshot(self, dates: list[str]) -> list[DayState]:
        return [
            snapshot_day(
                self._storage, self._plans, self._recog, self._vacations, d
            )
            for d in dates
        ]

    def _with_undo(
        self, dates: list[str], operation: Callable[[], None]
    ) -> None:
        """작업 전후 스냅샷을 비교해 실제 변경이 있으면 undo 슬롯에 저장."""
        before = self._snapshot(dates)
        operation()
        if self._snapshot(dates) != before:
            self._undo = before

    def _handle_undo(self) -> None:
        """Cmd/Ctrl+Z: 마지막 변경을 그 대상 일자에 한해 원복(단일 단계)."""
        if self._undo is None:
            return
        for state in self._undo:
            restore_day(self._storage, self._recog, self._vacations, state)
        self._undo = None
        self._refresh()

    def _handle_copy_day(self) -> None:
        """Cmd/Ctrl+C: 단일 선택 일자의 실계획·(가)계획을 복사 버퍼에 저장.

        다중 선택 중에는 복사할 수 없다.
        """
        if len(self._multi_dates) >= 2:
            QMessageBox.warning(
                self._window, "복사", "복수 일자는 복사할 수 없습니다."
            )
            return
        date = self._selected_date
        year, month = int(date[:4]), int(date[5:7])
        holidays = self._holidays.get_holidays(year, month)
        self._clipboard = DayPlanClipboard(
            plan_minutes=self._plans.effective_minutes(date, holidays),
            recog=self._recog.get(date),
        )

    def _handle_paste_day(self) -> None:
        """Cmd/Ctrl+V: 복사 버퍼를 대상 일자(단일/다중)에 그대로 붙여넣기."""
        if self._clipboard is None:
            return
        clipboard = self._clipboard
        dates = paste_targets(self._selected_date, self._multi_dates)
        self._with_undo(dates, lambda: apply_clipboard(
            self._storage, self._recog, clipboard, dates
        ))
        self._refresh()

    def _handle_clock_out(self) -> None:
        today = timeutil.today_str(timeutil.now())

        def op() -> None:
            try:
                self._service.record_clock_out()
            except ValueError:
                pass

        self._with_undo([today], op)
        self._refresh()

    def _handle_cancel_clock_out(self) -> None:
        today = timeutil.today_str(timeutil.now())
        self._with_undo([today], lambda: self._service.cancel_clock_out())
        self._refresh()

    def _handle_prev_month(self) -> None:
        self._view_year, self._view_month = _prev_month(
            self._view_year, self._view_month
        )
        self._refresh()

    def _handle_next_month(self) -> None:
        self._view_year, self._view_month = _next_month(
            self._view_year, self._view_month
        )
        self._refresh()

    def _handle_switch_mode(self) -> None:
        self._show_mode(config.MODE_WIDGET)

    def _show_mode(self, mode: str) -> None:
        self._mode = mode
        config.set_last_mode(mode)
        if mode == config.MODE_WIDGET:
            self._window.hide()
            self._widget.show()
        else:
            self._widget.hide()
            self._window.show()
        self._refresh()

    def _handle_select_day(self, date: str, mode: str = SELECT_SINGLE) -> None:
        """셀 클릭 = 선택 (STATUS 는 마지막 선택 일자 표시).

        Cmd+클릭은 다중 선택 토글, Shift+클릭은 사각형 범위 선택.
        """
        if mode == SELECT_RANGE:
            self._select_range_to(date)
        else:
            self._reset_range_anchor()
            if mode == SELECT_TOGGLE:
                self._toggle_multi_date(date)
            else:
                self._multi_dates = []
                self._selected_date = date
        self._refresh()

    def _reset_range_anchor(self) -> None:
        """Shift 이외의 선택 변경 → 다음 Shift 입력에서 앵커를 새로 잡는다."""
        self._range_anchor = None
        self._range_base = []

    def _toggle_multi_date(self, date: str) -> None:
        """Cmd+클릭 토글."""
        dates = list(self._multi_dates)
        if not dates and self._selected_date != date:
            # 단일 선택 상태에서 시작: 기존 선택 일자를 시드로 포함
            dates = [self._selected_date]
        if date in dates:
            dates.remove(date)
        else:
            dates.append(date)
        if dates:
            self._selected_date = dates[-1]
        # 1일 이하로 줄면 단일 선택으로 복귀
        self._multi_dates = dates if len(dates) >= 2 else []

    def _select_range_to(self, date: str) -> None:
        """Shift+클릭: 앵커~클릭 일자를 꼭짓점으로 하는 사각형 범위 선택.

        연속 Shift+클릭은 앵커를 유지한 채 사각형만 다시 그린다.
        """
        anchor, base = _resolve_anchor(
            self._range_anchor, self._range_base,
            self._selected_date, self._multi_dates,
        )
        self._range_anchor, self._range_base = anchor, base
        self._multi_dates = rectangle_selection(
            anchor, base, date, self._view_year, self._view_month
        )
        self._selected_date = date  # STATUS 는 마지막 클릭 일자 표시

    def _handle_clear_selection(self) -> None:
        """ESC: 다중 선택 해제 (마지막 선택 일자는 유지)."""
        if not self._multi_dates:
            return
        self._multi_dates = []
        self._reset_range_anchor()
        self._refresh()

    def _handle_go_today(self) -> None:
        """[오늘]: 선택·캘린더를 오늘/현재 월로 복귀 (다중 선택 해제)."""
        now = timeutil.now()
        self._selected_date = timeutil.today_str(now)
        self._multi_dates = []
        self._reset_range_anchor()
        self._view_year, self._view_month = now.year, now.month
        self._refresh()

    def _handle_navigate(self, delta_days: int, extend: bool) -> None:
        """화살표 키: 선택 일자를 방향 이동(Shift 면 범위 확장)."""
        today = timeutil.today_str(timeutil.now())
        result = _navigate_selection(
            self._selected_date, self._multi_dates,
            self._view_year, self._view_month, today, delta_days, extend,
            anchor=self._range_anchor, base=self._range_base,
        )
        self._range_anchor, self._range_base = result.anchor, result.base
        if (result.selected == self._selected_date
                and result.multi == self._multi_dates):
            return  # 경계 no-op — 불필요한 갱신 방지
        self._selected_date = result.selected
        self._multi_dates = result.multi
        self._refresh()

    def _handle_edit_day(self, date: str) -> None:
        """셀 더블 클릭 = 해당 날짜 선택 후 곧바로 수정 다이얼로그."""
        self._selected_date = date
        self._reset_range_anchor()
        self._handle_edit_selected()

    def _handle_edit_selected(self) -> None:
        """[수정]: 단일 선택은 상세 다이얼로그, 다중 선택은 일괄 수정."""
        if len(self._multi_dates) >= 2:
            self._open_bulk_plan_edit_dialog()
            return
        date = self._selected_date
        rec = self._storage.get(date)
        holidays = self._holidays.get_holidays(self._view_year, self._view_month)
        self._with_undo([date], lambda: open_day_dialog(
            self._window,
            date,
            rec.clock_in if rec else None,
            rec.clock_out if rec else None,
            self._plans.get_override(date),
            config.get_default_daily_minutes(),
            self._handle_save_times,
            self._handle_save_plan,
            recog_range=self._recog.get(date),
            baseline_minutes=self._plans.baseline_minutes(date, holidays),
            on_save_recognition=self._handle_save_recognition,
            vacation=self._vacations.get(date),
            on_save_vacation=self._handle_save_vacation,
            break_minutes=self._storage.get_extra_break(date),
            on_save_break=self._handle_save_break,
            extra_work_minutes=self._storage.get_extra_work(date),
            on_save_extra_work=self._handle_save_extra_work,
            memo=self._storage.get_memo(date),
            on_save_memo=self._storage.set_memo,
            start_in_edit=True,
        ))
        self._refresh()

    def _handle_open_ai(self) -> None:
        """[AI]: 로컬 AI CLI 로 자연어 기록 편집 다이얼로그를 연다."""
        if getattr(sys, "frozen", False):
            # 패키징 앱 — __file__ 은 번들 내부라 작업 폴더로 부적합.
            # workctl 서브커맨드는 cwd 와 무관하므로 홈으로 통일한다.
            workdir = os.path.expanduser("~")
        else:
            workdir = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        open_ai_dialog(self._window, workdir, on_applied=self._refresh)

    def _handle_register_api_key(self) -> None:
        """공휴일 API 인증키 등록 다이얼로그를 연다."""
        open_api_key_dialog(
            self._window,
            on_test=lambda key: verify_service_key(
                key, self._view_year, self._view_month
            ),
            on_save=self._handle_save_service_key,
        )

    def _handle_save_service_key(self, key: str) -> None:
        config.set_service_key(key)
        # 새 키로 클라이언트를 재생성해 즉시 공휴일 조회에 반영
        self._holidays = HolidayClient(
            config.get_service_key(), config.holidays_cache_path()
        )
        self._window.set_api_key_registered(True)
        self._refresh()

    def _validate_bulk_range(self, dates: list[str]):
        """일괄 수정 다이얼로그용 검증 콜백 생성.

        날짜별 유효 계획 대비 인정 범위 폭을 검증하고 첫 위반 날짜를 안내한다.
        """
        def validate(minutes, rng) -> str | None:
            if rng is None:
                return None
            for date in dates:
                holidays = self._holidays.get_holidays(
                    int(date[:4]), int(date[5:7])
                )
                planned = (
                    minutes if minutes is not None
                    else self._plans.baseline_minutes(date, holidays)
                )
                err = validate_range_against_plan(planned, rng)
                if err is not None:
                    return f"{date}: {err}"
            return None

        return validate

    def _handle_edit_weekday(self, weekday: int) -> None:
        year, month = self._view_year, self._view_month
        dates = weekday_dates(year, month, weekday)
        # 과거 일자와 퇴근 완료 날짜는 계획·인정 범위 일괄 변경에서 제외한다
        today = timeutil.today_str(timeutil.now())
        records = {r.work_date: r for r in self._storage.list_month(year, month)}
        excluded = {
            d for d in dates
            if d < today
            or (d in records and records[d].clock_out is not None)
        }
        target_dates = [d for d in dates if d not in excluded]

        def apply(minutes, rng) -> None:
            self._plans.set_weekday_plan(
                year, month, weekday, minutes, exclude_dates=excluded
            )
            self._recog.set_weekday(
                year, month, weekday, rng, exclude_dates=excluded
            )

        name = _WEEKDAY_NAMES[weekday]
        info = (
            f"이번 달 {name} {len(target_dates)}일에 일괄 적용됩니다.<br/>"
            f'<span style="color:{theme.FG_MUTED};">(과거일자 제외)</span>'
        )
        self._with_undo(target_dates, lambda: open_bulk_plan_dialog(
            self._window,
            f"{name} 계획 일괄 수정",
            info,
            config.get_default_daily_minutes(),
            apply,
            self._validate_bulk_range(target_dates),
        ))
        self._refresh()

    def _open_bulk_plan_edit_dialog(self) -> None:
        dates = sorted(self._multi_dates)

        def apply(minutes, rng) -> None:
            for date in dates:
                if minutes is None:
                    self._plans.clear_plan(date)
                else:
                    self._plans.set_plan(date, minutes)
                if rng is None:
                    self._recog.clear(date)
                else:
                    self._recog.set(date, rng)

        def apply_vacation(vacation) -> None:
            for date in dates:
                if vacation is None:
                    self._vacations.clear(date)
                else:
                    self._vacations.set(date, vacation)
                # 휴가 변경은 저장된 근무초에 영향 → 즉시 재계산
                self._service.recompute_work(date)

        applied: list[bool] = []

        def op() -> None:
            applied.append(open_bulk_plan_dialog(
                self._window,
                "선택 일자 계획 일괄 수정",
                f"선택한 {len(dates)}일에 일괄 적용됩니다.",
                config.get_default_daily_minutes(),
                apply,
                self._validate_bulk_range(dates),
                on_apply_vacation=apply_vacation,
            ))

        self._with_undo(dates, op)
        if applied and applied[0]:
            self._multi_dates = []  # 적용 완료 → 단일 선택으로 복귀
            self._reset_range_anchor()
        self._refresh()

    def _handle_manage_vacation(self) -> None:
        year = timeutil.now().year  # 캘린더 표시 월과 무관하게 올해 기준

        def save_total(total_minutes: int) -> YearLeaveSummary:
            self._vacations.set_annual_total(year, total_minutes)
            return self._vacations.year_summary(year)

        open_vacation_dialog(
            self._window, self._vacations.year_summary(year), save_total
        )
        self._refresh()

    def _handle_save_times(self, work_date, clock_in_iso, clock_out_iso) -> None:
        # 출근 시각을 비우면 그날의 출퇴근 기록을 삭제한다
        if not clock_in_iso:
            self._service.clear(work_date)
        else:
            self._service.edit(work_date, clock_in_iso, clock_out_iso)

    def _handle_save_plan(self, work_date, minutes) -> None:
        if minutes is None:
            self._plans.clear_plan(work_date)
        else:
            self._plans.set_plan(work_date, minutes)

    def _handle_save_recognition(
        self, work_date: str, rng: RecognitionRange | None
    ) -> None:
        if rng is None:
            self._recog.clear(work_date)
        else:
            self._recog.set(work_date, rng)

    def _handle_save_vacation(
        self, work_date: str, vacation: Vacation | None
    ) -> None:
        if vacation is None:
            self._vacations.clear(work_date)
        else:
            self._vacations.set(work_date, vacation)
        # 휴가 변경은 저장된 근무초에 영향 → 즉시 재계산
        self._service.recompute_work(work_date)

    def _handle_save_break(self, work_date: str, minutes: int | None) -> None:
        if minutes is None:
            self._storage.clear_extra_break(work_date)
        else:
            self._storage.set_extra_break(work_date, minutes)
        # 휴게 변경은 저장된 근무초에 영향 → 즉시 재계산
        self._service.recompute_work(work_date)

    def _handle_save_extra_work(
        self, work_date: str, minutes: int | None
    ) -> None:
        if minutes is None:
            self._storage.clear_extra_work(work_date)
        else:
            self._storage.set_extra_work(work_date, minutes)
        # 추가 업무 변경은 저장된 근무초에 영향 → 즉시 재계산
        self._service.recompute_work(work_date)

    # --- 실행 -----------------------------------------------------------
    def _handle_app_exit(self) -> None:
        """정상 종료 훅: 진행 중이면 자동 퇴근하고 재개용 마커를 남긴다."""
        rec = self._service.auto_clock_out()
        if rec is not None:
            config.set_auto_clock_out_date(rec.work_date)

    def run(self) -> None:
        self._service.record_clock_in()  # 부팅 = 자동 출근 (기존 동작 유지)
        # 직전 정상 종료가 자동 저장한 오늘 퇴근이면 취소해 근무 연속 재개
        self._service.resume_auto_clock_out(config.get_auto_clock_out_date())
        config.set_auto_clock_out_date(None)  # 마커 소비/무효화
        self._refresh()
        self._show_mode(config.get_last_mode())
        self._timer.start(self._ms_until_next_minute())
        self._app.exec()


class _NavResult(NamedTuple):
    """화살표 이동 결과 선택 상태 (anchor/base 는 Shift 사각형 선택용)."""

    selected: str
    multi: list[str]
    anchor: str | None
    base: list[str]


def _resolve_anchor(
    anchor: str | None,
    base: list[str],
    selected_date: str,
    multi_dates: list[str],
) -> tuple[str, list[str]]:
    """Shift 사각형 선택의 (앵커, 기준 선택)을 결정한다.

    앵커가 없으면 현재 선택 일자를 앵커로, 나머지 다중 선택을 기준으로 삼는다.
    """
    if anchor is not None:
        return anchor, list(base)
    return selected_date, [d for d in multi_dates if d != selected_date]


def _navigate_selection(
    selected_date: str,
    multi_dates: list[str],
    year: int,
    month: int,
    today: str,
    delta_days: int,
    extend: bool,
    anchor: str | None = None,
    base: list[str] | None = None,
) -> _NavResult:
    """화살표 이동 후의 선택 상태를 계산한다(순수 함수).

    선택 일자가 보는 달에 없으면 첫 입력은 기준일(오늘/1일)만 선택한다.
    경계를 벗어나면 아무 변화 없이 현재 상태를 그대로 돌려준다.
    extend 면 앵커~목표를 꼭짓점으로 하는 사각형을 기준 선택에 합친다.
    """
    base = base or []
    start, should_move = resolve_nav_base(selected_date, year, month, today)
    if not should_move:
        return _NavResult(start, [], None, [])
    target = step_within_month(start, delta_days, year, month)
    if target is None:  # 경계 no-op
        return _NavResult(selected_date, multi_dates, anchor, base)
    if not extend:
        return _NavResult(target, [], None, [])
    anchor, base = _resolve_anchor(anchor, base, start, multi_dates)
    multi = rectangle_selection(anchor, base, target, year, month)
    return _NavResult(target, multi, anchor, base)


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def run() -> None:
    AppController().run()
