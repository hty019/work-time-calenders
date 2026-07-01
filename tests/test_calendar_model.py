from core.storage import Attendance
from widget.calendar_model import (
    build_month_grid,
    format_hms,
    required_month_hours,
)


def test_format_hms():
    assert format_hms(None) == "-"
    assert format_hms(27000) == "7h 30m"
    assert format_hms(8 * 3600) == "8h 0m"


def test_required_month_hours():
    # 말일 / 7 * 40 (버림)
    assert required_month_hours(2026, 7) == 177   # 31일
    assert required_month_hours(2026, 6) == 171   # 30일
    assert required_month_hours(2026, 2) == 160   # 28일
    assert required_month_hours(2024, 2) == 165   # 29일(윤년)


def test_grid_has_full_weeks():
    grid = build_month_grid(2026, 6, "2026-06-30", {}, {})
    assert all(len(week) == 7 for week in grid)
    # 2026-06-01은 월요일 → 첫 주 첫 칸이 1일
    assert grid[0][0].day == 1


def test_grid_marks_today_holiday_and_work():
    records = {
        "2026-06-30": Attendance(
            "2026-06-30", "2026-06-30T09:00:00+09:00",
            "2026-06-30T18:00:00+09:00", 8 * 3600,
        ),
        "2026-06-02": Attendance(
            "2026-06-02", "2026-06-02T09:00:00+09:00", None, None,
        ),
    }
    holidays = {"2026-06-06": "현충일"}
    grid = build_month_grid(2026, 6, "2026-06-30", records, holidays)
    cells = {c.date: c for week in grid for c in week if c.day != 0}
    assert cells["2026-06-30"].is_today is True
    assert cells["2026-06-30"].work_seconds == 8 * 3600
    assert cells["2026-06-06"].holiday_name == "현충일"
    assert cells["2026-06-02"].is_incomplete is True
