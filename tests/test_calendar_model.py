from core.storage import Attendance
from core.calendar_model import (
    build_month_grid,
    format_hm,
    format_hms,
    max_month_hours,
    required_month_hours,
)


def test_format_hms():
    assert format_hms(None) == "-"
    assert format_hms(27000) == "7h 30m"
    assert format_hms(8 * 3600) == "8h 0m"


def test_required_month_hours():
    # 말일 / 7 * 40 (버림), 공휴일 없음
    assert required_month_hours(2026, 7) == 177   # 31일
    assert required_month_hours(2026, 6) == 171   # 30일
    assert required_month_hours(2026, 2) == 160   # 28일
    assert required_month_hours(2024, 2) == 165   # 29일(윤년)


def test_required_month_hours_subtracts_weekday_holidays():
    # 2026-02: 설날 2/16(월)·17(화)·18(수) 모두 평일 → 3일 × 8h 차감
    holidays = {
        "2026-02-16": "설날",
        "2026-02-17": "설날",
        "2026-02-18": "설날",
    }
    assert required_month_hours(2026, 2, holidays) == 160 - 3 * 8  # 136


def test_required_month_hours_ignores_weekend_holidays():
    # 2026-08-15(광복절)은 토요일 → 차감 없음
    holidays = {"2026-08-15": "광복절"}
    assert required_month_hours(2026, 8, holidays) == 177  # 31일, 차감 0


def test_max_month_hours_uses_52_week():
    # 말일 / 7 * 52 (버림), 공휴일 없음
    assert max_month_hours(2026, 7) == 230   # 31일: floor(31/7*52)
    assert max_month_hours(2026, 6) == 222   # 30일: floor(30/7*52)


def test_max_month_hours_ignores_holidays():
    # 최대 근로 가능시간은 공휴일 차감 없이 말일/7*52 그대로
    holidays = {"2026-02-16": "설날"}  # 월요일(평일 공휴일)
    assert max_month_hours(2026, 2, holidays) == 208  # 28일: floor(28/7*52)


def test_grid_has_full_weeks():
    grid = build_month_grid(2026, 6, "2026-06-30", {}, {})
    assert all(len(week) == 7 for week in grid)
    # 2026-06-01은 월요일 → 첫 주 첫 칸이 1일
    assert grid[0][0].day == 1


def test_grid_reflects_today_in_progress_seconds():
    # 오늘 미퇴근 상태 + 진행 중 근무초를 셀에 실시간 반영
    records = {
        "2026-06-30": Attendance(
            "2026-06-30", "2026-06-30T09:00:00+09:00", None, None,
        ),
    }
    grid = build_month_grid(
        2026, 6, "2026-06-30", records, {}, today_seconds=3 * 3600,
    )
    cells = {c.date: c for week in grid for c in week if c.day != 0}
    today = cells["2026-06-30"]
    assert today.work_seconds == 3 * 3600
    assert today.is_incomplete is False  # 미퇴근 대신 진행 시간 표시
    assert today.is_clocked_out is False  # 진행 중은 '퇴근 완료' 아님


def test_grid_past_incomplete_stays_incomplete():
    # 과거의 미퇴근 날짜는 today_seconds 와 무관하게 '미퇴근' 유지
    records = {
        "2026-06-02": Attendance(
            "2026-06-02", "2026-06-02T09:00:00+09:00", None, None,
        ),
    }
    grid = build_month_grid(
        2026, 6, "2026-06-30", records, {}, today_seconds=3 * 3600,
    )
    cells = {c.date: c for week in grid for c in week if c.day != 0}
    assert cells["2026-06-02"].is_incomplete is True
    assert cells["2026-06-02"].work_seconds is None


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
    assert cells["2026-06-30"].is_clocked_out is True  # 퇴근 완료
    assert cells["2026-06-30"].clock_in_hm == "09:00"
    assert cells["2026-06-30"].clock_out_hm == "18:00"
    assert cells["2026-06-06"].holiday_name == "현충일"
    assert cells["2026-06-02"].is_incomplete is True
    assert cells["2026-06-02"].is_clocked_out is False  # 미퇴근


def test_format_hm():
    assert format_hm(0) == "0h 0m"
    assert format_hm(480) == "8h 0m"
    assert format_hm(150) == "2h 30m"


def test_grid_includes_recognition_range_and_deviation():
    # 인정 범위 09:00~15:00, 근로 08:00~16:00 → 범위 이탈
    records = {
        "2026-06-29": Attendance(
            "2026-06-29", "2026-06-29T08:00:00+09:00",
            "2026-06-29T16:00:00+09:00", 7 * 3600 + 30 * 60,
        ),
        "2026-06-30": Attendance(
            "2026-06-30", "2026-06-30T09:00:00+09:00",
            "2026-06-30T15:00:00+09:00", 5 * 3600 + 30 * 60,
        ),
    }
    ranges = {
        "2026-06-29": (540, 900),
        "2026-06-30": (540, 900),
    }
    grid = build_month_grid(
        2026, 6, "2026-06-30", records, {},
        recognition=lambda d: ranges.get(d),
    )
    cells = {c.date: c for week in grid for c in week if c.day != 0}
    out = cells["2026-06-29"]
    assert out.recog_hm == "09:00~15:00"
    assert out.out_of_range is True
    ok = cells["2026-06-30"]
    assert ok.recog_hm == "09:00~15:00"
    assert ok.out_of_range is False
    # 범위 미설정 날짜는 빈 값
    assert cells["2026-06-01"].recog_hm == ""
    assert cells["2026-06-01"].out_of_range is False


def test_grid_recognition_ignores_missing_record():
    # 범위만 있고 기록 없음 → 표시만 하고 이탈 아님
    grid = build_month_grid(
        2026, 6, "2026-06-30", {}, {},
        recognition=lambda d: (540, 900) if d == "2026-06-05" else None,
    )
    cells = {c.date: c for week in grid for c in week if c.day != 0}
    assert cells["2026-06-05"].recog_hm == "09:00~15:00"
    assert cells["2026-06-05"].out_of_range is False


def test_grid_includes_vacation_minutes():
    vacations = {"2026-06-10": (120, 900, 1020), "2026-06-11": (480, None, None)}
    grid = build_month_grid(
        2026, 6, "2026-06-30", {}, {},
        vacation=lambda d: vacations.get(d),
    )
    cells = {c.date: c for week in grid for c in week if c.day != 0}
    assert cells["2026-06-10"].vacation_minutes == 120
    assert cells["2026-06-11"].vacation_minutes == 480
    assert cells["2026-06-12"].vacation_minutes == 0


def test_grid_includes_planned_minutes():
    # effective_planned 콜백이 각 셀 planned_minutes 로 반영되는지
    records = {}
    holidays = {}
    planned = {"2026-07-01": 480, "2026-07-04": 0}
    grid = build_month_grid(
        2026, 7, "2026-07-01", records, holidays,
        effective_planned=lambda d: planned.get(d, 240),
    )
    cells = {c.date: c for week in grid for c in week if c.date}
    assert cells["2026-07-01"].planned_minutes == 480
    assert cells["2026-07-04"].planned_minutes == 0
    assert cells["2026-07-02"].planned_minutes == 240  # 콜백 기본
