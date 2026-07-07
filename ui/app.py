"""Qt 앱 조립·모드 전환·주기 갱신 컨트롤러."""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import config
from core import timeutil
from core.attendance import AttendanceService
from core.calendar_model import build_month_grid
from core.day_detail import build_day_detail
from core.holidays import HolidayClient, verify_service_key
from core.plan import PlanService, weekday_dates
from core.recognition import (
    RecognitionRange,
    RecognitionService,
    validate_range_against_plan,
)
from core.stats import build_month_summary
from core.storage import Storage
from core.vacation import Vacation, VacationService, YearLeaveSummary
from ui import theme
from ui.api_key_dialog import open_api_key_dialog
from ui.day_dialog import open_day_dialog
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
from ui.weekday_dialog import open_weekday_plan_dialog
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

        callbacks = MainWindowCallbacks(
            on_clock_out=self._handle_clock_out,
            on_cancel_clock_out=self._handle_cancel_clock_out,
            on_select_day=self._handle_select_day,
            on_edit_day=self._handle_edit_day,
            on_edit_weekday=self._handle_edit_weekday,
            on_prev_month=self._handle_prev_month,
            on_next_month=self._handle_next_month,
            on_switch_mode=self._handle_switch_mode,
            on_manage_vacation=self._handle_manage_vacation,
            on_edit_selected=self._handle_edit_selected,
            on_go_today=self._handle_go_today,
            on_register_api_key=self._handle_register_api_key,
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
        self._window.render(year, month, status, grid, summary, leave, detail)
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
        self._widget.render(status, today_info)

    def _ms_until_next_minute(self) -> int:
        now = timeutil.now()
        remaining = _MINUTE_SECONDS - now.second - now.microsecond / 1_000_000
        return int(remaining * 1000) + _SYNC_BUFFER_MS

    def _tick(self) -> None:
        self._refresh()
        self._timer.start(self._ms_until_next_minute())

    # --- 핸들러 ---------------------------------------------------------
    def _handle_clock_out(self) -> None:
        try:
            self._service.record_clock_out()
        except ValueError:
            pass
        self._refresh()

    def _handle_cancel_clock_out(self) -> None:
        self._service.cancel_clock_out()
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

    def _handle_select_day(self, date: str) -> None:
        """셀 클릭 = 선택. 상세는 STATUS 패널에 표시된다."""
        self._selected_date = date
        self._refresh()

    def _handle_go_today(self) -> None:
        """[오늘]: 선택·캘린더를 오늘/현재 월로 복귀."""
        now = timeutil.now()
        self._selected_date = timeutil.today_str(now)
        self._view_year, self._view_month = now.year, now.month
        self._refresh()

    def _handle_edit_day(self, date: str) -> None:
        """셀 더블 클릭 = 해당 날짜 선택 후 곧바로 수정 다이얼로그."""
        self._selected_date = date
        self._handle_edit_selected()

    def _handle_edit_selected(self) -> None:
        """[수정]: 선택 날짜를 수정 다이얼로그(수정 모드)로 연다."""
        date = self._selected_date
        rec = self._storage.get(date)
        holidays = self._holidays.get_holidays(self._view_year, self._view_month)
        open_day_dialog(
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
            memo=self._storage.get_memo(date),
            on_save_memo=self._storage.set_memo,
            start_in_edit=True,
        )
        self._refresh()

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

    def _handle_edit_weekday(self, weekday: int) -> None:
        year, month = self._view_year, self._view_month
        dates = weekday_dates(year, month, weekday)
        holidays = self._holidays.get_holidays(year, month)
        # 퇴근까지 완료된 날짜는 계획·인정 범위 일괄 변경에서 제외한다
        records = {r.work_date: r for r in self._storage.list_month(year, month)}
        completed = {
            d for d in dates
            if d in records and records[d].clock_out is not None
        }
        target_dates = [d for d in dates if d not in completed]

        def validate(minutes, rng) -> str | None:
            """날짜별 유효 계획 대비 인정 범위 폭 검증. 첫 위반 날짜를 안내."""
            if rng is None:
                return None
            for date in target_dates:
                planned = (
                    minutes if minutes is not None
                    else self._plans.baseline_minutes(date, holidays)
                )
                err = validate_range_against_plan(planned, rng)
                if err is not None:
                    return f"{date}: {err}"
            return None

        def apply(minutes, rng) -> None:
            self._plans.set_weekday_plan(
                year, month, weekday, minutes, exclude_dates=completed
            )
            self._recog.set_weekday(
                year, month, weekday, rng, exclude_dates=completed
            )

        open_weekday_plan_dialog(
            self._window,
            _WEEKDAY_NAMES[weekday],
            len(target_dates),
            config.get_default_daily_minutes(),
            apply,
            validate,
            excluded_count=len(completed),
        )
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

    # --- 실행 -----------------------------------------------------------
    def run(self) -> None:
        self._service.record_clock_in()  # 부팅 = 자동 출근 (기존 동작 유지)
        self._refresh()
        self._show_mode(config.get_last_mode())
        self._timer.start(self._ms_until_next_minute())
        self._app.exec()


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def run() -> None:
    AppController().run()
