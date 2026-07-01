"""Qt 앱 조립·모드 전환·주기 갱신 컨트롤러."""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import config
from core import timeutil
from core.attendance import AttendanceService
from core.calendar_model import build_month_grid
from core.holidays import HolidayClient
from core.plan import PlanService
from core.stats import build_month_summary
from core.storage import Storage
from ui import theme
from ui.day_dialog import open_day_dialog
from ui.main_window import MainWindow, MainWindowCallbacks

_MINUTE_SECONDS = 60
_SYNC_BUFFER_MS = 100


class AppController:
    def __init__(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyleSheet(theme.base_stylesheet())

        self._storage = Storage(config.db_path())
        self._service = AttendanceService(self._storage)
        self._plans = PlanService(self._storage)
        self._holidays = HolidayClient(
            config.get_service_key(), config.holidays_cache_path()
        )

        now = timeutil.now()
        self._view_year, self._view_month = now.year, now.month

        callbacks = MainWindowCallbacks(
            on_clock_out=self._handle_clock_out,
            on_cancel_clock_out=self._handle_cancel_clock_out,
            on_edit_day=self._handle_edit_day,
            on_prev_month=self._handle_prev_month,
            on_next_month=self._handle_next_month,
            on_switch_mode=self._handle_switch_mode,
        )
        self._window = MainWindow(callbacks)
        self._timer = QTimer(self._window)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)

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
        )
        summary = build_month_summary(
            self._storage, self._service, self._plans,
            year, month, holidays, now,
        )
        self._window.render(
            year, month, self._service.today_status(), grid, summary
        )

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
        # Task 12 에서 위젯 모드 전환 구현. 지금은 상태만 저장.
        config.set_last_mode(config.MODE_WIDGET)

    def _handle_edit_day(self, date: str) -> None:
        rec = self._storage.get(date)
        open_day_dialog(
            self._window,
            date,
            rec.clock_in if rec else None,
            rec.clock_out if rec else None,
            self._plans.get_override(date),
            config.get_default_daily_minutes(),
            self._handle_save_times,
            self._handle_save_plan,
        )
        self._refresh()

    def _handle_save_times(self, work_date, clock_in_iso, clock_out_iso) -> None:
        self._service.edit(work_date, clock_in_iso, clock_out_iso)

    def _handle_save_plan(self, work_date, minutes) -> None:
        if minutes is None:
            self._plans.clear_plan(work_date)
        else:
            self._plans.set_plan(work_date, minutes)

    # --- 실행 -----------------------------------------------------------
    def run(self) -> None:
        self._service.record_clock_in()  # 부팅 = 자동 출근 (기존 동작 유지)
        self._refresh()
        self._window.show()
        self._timer.start(self._ms_until_next_minute())
        self._app.exec()


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def run() -> None:
    AppController().run()
