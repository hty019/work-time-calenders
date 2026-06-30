"""달력 그리드 구성 순수 로직 (tkinter 비의존)."""
from __future__ import annotations

import calendar
from dataclasses import dataclass

from core.storage import Attendance


@dataclass
class DayCell:
    day: int
    date: str | None
    is_today: bool
    holiday_name: str | None
    work_seconds: int | None
    is_incomplete: bool


def format_hms(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"


def build_month_grid(
    year: int,
    month: int,
    today: str,
    records: dict[str, Attendance],
    holidays: dict[str, str],
) -> list[list[DayCell]]:
    cal = calendar.Calendar(firstweekday=0)  # 0 = Monday
    grid: list[list[DayCell]] = []
    for week in cal.monthdayscalendar(year, month):
        row: list[DayCell] = []
        for day in week:
            if day == 0:
                row.append(DayCell(0, None, False, None, None, False))
                continue
            date = f"{year:04d}-{month:02d}-{day:02d}"
            rec = records.get(date)
            work_seconds = rec.work_seconds if rec else None
            is_incomplete = rec is not None and rec.clock_out is None
            row.append(
                DayCell(
                    day=day,
                    date=date,
                    is_today=(date == today),
                    holiday_name=holidays.get(date),
                    work_seconds=work_seconds,
                    is_incomplete=is_incomplete,
                )
            )
        grid.append(row)
    return grid
