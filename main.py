"""근무시간 데스크탑 위젯 진입점."""
from __future__ import annotations

import config
from core import timeutil
from core.attendance import AttendanceService
from core.holidays import HolidayClient
from core.storage import Storage
from widget.calendar_model import build_month_grid, format_hms
from widget.edit_dialog import open_edit_dialog
from widget.window import WidgetWindow


class App:
    def __init__(self) -> None:
        self._storage = Storage(config.db_path())
        self._service = AttendanceService(self._storage)
        self._holidays = HolidayClient(
            config.get_service_key(), config.holidays_cache_path()
        )
        self._window = WidgetWindow(
            on_clock_out=self._handle_clock_out,
            on_edit_day=self._handle_edit_day,
        )

    def _refresh(self) -> None:
        now = timeutil.now()
        year, month = now.year, now.month
        today = timeutil.today_str(now)
        records = {
            r.work_date: r for r in self._storage.list_month(year, month)
        }
        holidays = self._holidays.get_holidays(year, month)
        grid = build_month_grid(year, month, today, records, holidays)

        today_rec = records.get(today)
        clock_in_txt = today_rec.clock_in[11:16] if today_rec else "-"
        total = self._service.month_total_seconds(year, month)
        header = f"출근 {clock_in_txt}  |  {month}월 누적 {format_hms(total)}"
        self._window.render(header, grid)

    def _handle_clock_out(self) -> None:
        try:
            self._service.record_clock_out()
        except ValueError:
            pass
        self._refresh()

    def _handle_edit_day(self, date: str) -> None:
        rec = self._storage.get(date)
        open_edit_dialog(
            self._window._root,
            date,
            rec.clock_in if rec else None,
            rec.clock_out if rec else None,
            self._handle_save_edit,
        )

    def _handle_save_edit(self, work_date, clock_in_iso, clock_out_iso) -> None:
        self._service.edit(work_date, clock_in_iso, clock_out_iso)
        self._refresh()

    def run(self) -> None:
        self._service.record_clock_in()  # 부팅 = 출근
        self._refresh()
        self._window.run()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
