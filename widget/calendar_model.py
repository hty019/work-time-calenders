"""달력 그리드 구성 순수 로직 (tkinter 비의존)."""
from __future__ import annotations

import calendar
import math
from dataclasses import dataclass

from core.storage import Attendance

_WEEKLY_WORK_HOURS = 40  # 주 40시간 근로 기준
_DAYS_PER_WEEK = 7


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


def required_month_hours(year: int, month: int) -> int:
    """한 달간 채워야 하는 총 근로시간(시간).

    계산식: 말일 / 7 * 40 (소수점 버림). 예) 31일 → 177h.
    """
    last_day = calendar.monthrange(year, month)[1]
    return math.floor(last_day / _DAYS_PER_WEEK * _WEEKLY_WORK_HOURS)


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
