from core.stats import ProgressLevel
from core.vacation import YearLeaveSummary
from ui.status_panel import (
    clock_in_line,
    expected_line,
    leave_line,
    progress_caption,
    remaining_line,
    stay_line,
)


def test_clock_in_line_shows_time():
    assert clock_in_line("09:12") == "금일 출근 시간: 09:12"


def test_clock_in_line_dash_without_record():
    assert clock_in_line(None) == "금일 출근 시간: -"


def test_leave_line_shows_remaining_and_total():
    s = YearLeaveSummary(
        year=2026,
        total_minutes=15 * 480,
        used_minutes=2 * 480 + 120,  # 2.25일 소진
        remaining_minutes=15 * 480 - (2 * 480 + 120),
        entries=[],
    )
    assert leave_line(s) == "연차   12.75 / 15"


def test_leave_line_without_total_shows_dash():
    s = YearLeaveSummary(
        year=2026,
        total_minutes=None,
        used_minutes=480,
        remaining_minutes=None,
        entries=[],
    )
    assert leave_line(s) == "연차   -"


def test_expected_line_shows_time_only():
    assert expected_line("18:42") == "퇴근 예정 시간: 18:42"


def test_expected_line_dash_without_expectation():
    assert expected_line(None) == "퇴근 예정 시간: -"


def test_expected_line_appends_range_warning():
    assert expected_line("18:30", exceeds_range=True) == (
        "퇴근 예정 시간: 18:30\n⚠ (가)계획 종료 초과"
    )


def test_expected_line_overdue_warning_wins():
    # 미퇴근 + (가)계획 퇴근 초과: 계획 수정 필요 경고 우선
    assert expected_line("17:30", exceeds_range=True, overdue=True) == (
        "퇴근 예정 시간: 17:30\n⚠ 계획 수정 필요"
    )


def test_stay_line_formats_elapsed():
    assert stay_line(3 * 3600 + 30 * 60) == "체류 시간: 3h 30m"


def test_stay_line_dash_without_record():
    assert stay_line(None) == "체류 시간: -"


def test_remaining_line_formats_remaining():
    assert remaining_line(2 * 3600 + 30 * 60) == "남은 시간: 2h 30m"


def test_remaining_line_clamps_negative_to_zero():
    # 예상 퇴근 시각을 지나면 0 으로 고정
    assert remaining_line(-600) == "남은 시간: 0h 0m"


def test_remaining_line_dash_without_expectation():
    assert remaining_line(None) == "남은 시간: -"


def test_caption_normal_shows_percent():
    # 법정 기준 이내: 진행도 퍼센트 표시
    text = progress_caption(
        56, ProgressLevel.NORMAL, 100 * 3600, 177 * 60
    )
    assert text == "근로 시간 진행도: 56%"


def test_caption_over_shows_exceeded_hours():
    # 법정 기준 초과: +초과시간(h) 표시 (분 버림)
    text = progress_caption(
        78, ProgressLevel.OVER, 180 * 3600 + 30 * 60, 177 * 60
    )
    assert text == "초과 근로 진행: +3h"


def test_caption_critical_and_exceeded_also_show_hours():
    assert progress_caption(
        86, ProgressLevel.CRITICAL, 198 * 3600, 177 * 60
    ) == "초과 근로 진행: +21h"
    assert progress_caption(
        100, ProgressLevel.EXCEEDED, 231 * 3600, 177 * 60
    ) == "초과 근로 진행: +54h"
