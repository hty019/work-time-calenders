"""근무시간 데스크탑 위젯 진입점."""
from __future__ import annotations

import config
from core import timeutil
from core.attendance import AttendanceService
from core.holidays import HolidayClient
from core.storage import Storage
from core.calendar_model import (
    build_month_grid,
    format_hms,
    required_month_hours,
)
from widget.edit_dialog import open_edit_dialog
from widget.window import WidgetWindow

_MINUTE_SECONDS = 60
_SYNC_BUFFER_MS = 100  # 분 경계를 살짝 지난 뒤 갱신해 초가 00으로 넘어간 것을 보장


class App:
    def __init__(self) -> None:
        self._storage = Storage(config.db_path())
        self._service = AttendanceService(self._storage)
        self._holidays = HolidayClient(
            config.get_service_key(), config.holidays_cache_path()
        )
        self._window = WidgetWindow(
            on_clock_out=self._handle_clock_out,
            on_cancel_clock_out=self._handle_cancel_clock_out,
            on_edit_day=self._handle_edit_day,
        )

    def _build_header(
        self, records: dict, year: int, month: int, today: str,
        holidays: dict, today_seconds: int | None,
    ) -> str:
        today_rec = records.get(today)
        clock_in_txt = today_rec.clock_in[11:16] if today_rec else "-"
        total = self._service.month_total_seconds(year, month) + (
            today_seconds or 0
        )
        required = required_month_hours(year, month, holidays)
        return (
            f"출근 {clock_in_txt}  |  {month}월 누적 "
            f"{format_hms(total)} / {required}h"
        )

    def _refresh(self) -> None:
        now = timeutil.now()
        year, month = now.year, now.month
        today = timeutil.today_str(now)
        records = {
            r.work_date: r for r in self._storage.list_month(year, month)
        }
        holidays = self._holidays.get_holidays(year, month)
        today_seconds = self._service.today_in_progress_seconds()
        grid = build_month_grid(
            year, month, today, records, holidays, today_seconds
        )
        header = self._build_header(
            records, year, month, today, holidays, today_seconds
        )
        self._window.render(header, grid, self._service.today_status())

    def _ms_until_next_minute(self) -> int:
        """다음 분 경계(:00)까지 남은 밀리초. 벽시계 분 갱신과 동기화한다."""
        now = timeutil.now()
        remaining = _MINUTE_SECONDS - now.second - now.microsecond / 1_000_000
        return int(remaining * 1000) + _SYNC_BUFFER_MS

    def _tick(self) -> None:
        """매 분 경계에 헤더와 오늘 셀의 진행 중 근무시간만 갱신한다."""
        now = timeutil.now()
        year, month = now.year, now.month
        today = timeutil.today_str(now)
        records = {
            r.work_date: r for r in self._storage.list_month(year, month)
        }
        holidays = self._holidays.get_holidays(year, month)
        today_seconds = self._service.today_in_progress_seconds()
        header = self._build_header(
            records, year, month, today, holidays, today_seconds
        )
        today_text = format_hms(today_seconds) if today_seconds is not None else None
        self._window.update_live(header, today_text)
        self._window.root.after(self._ms_until_next_minute(), self._tick)

    def _handle_clock_out(self) -> None:
        try:
            self._service.record_clock_out()
        except ValueError:
            pass
        self._refresh()

    def _handle_cancel_clock_out(self) -> None:
        self._service.cancel_clock_out()
        self._refresh()

    def _handle_edit_day(self, date: str) -> None:
        rec = self._storage.get(date)
        open_edit_dialog(
            self._window.root,
            date,
            rec.clock_in if rec else None,
            rec.clock_out if rec else None,
            self._handle_save_edit,
        )

    def _handle_save_edit(self, work_date: str, clock_in_iso: str, clock_out_iso: str | None) -> None:
        self._service.edit(work_date, clock_in_iso, clock_out_iso)
        self._refresh()

    def run(self) -> None:
        self._service.record_clock_in()  # 부팅 = 출근
        self._refresh()
        self._window.root.after(self._ms_until_next_minute(), self._tick)
        self._window.run()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
