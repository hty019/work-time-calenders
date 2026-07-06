from core.attendance import WorkStatus
from core.stats import ProgressLevel
from core.vacation import YearLeaveSummary
from ui.status_panel import (
    clock_in_line,
    expected_display,
    leave_line,
    progress_caption,
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


def test_expected_display_pending_shows_remaining():
    # 근무 중 + 예상 퇴근 전: 퇴근 예정 시각 + 남은 시간
    text, sub, state = expected_display(
        WorkStatus.WORKING, "18:00", 2 * 3600, 6 * 3600, False,
        recog_end_hm="19:00", recog_end_passed=False,
    )
    assert text == "퇴근 예정 시간: 18:00 (2h 0m 남음)"
    assert sub is None
    assert state == "pending"


def test_expected_display_pending_with_range_warning():
    text, _, state = expected_display(
        WorkStatus.WORKING, "18:30", 2 * 3600, 6 * 3600, True,
        recog_end_hm="18:00", recog_end_passed=False,
    )
    assert "퇴근 예정 시간: 18:30" in text
    assert "⚠ (가)계획 종료 초과" in text
    assert state == "warn"


def test_expected_display_done_after_clock_out():
    # 퇴근 완료: 금일 근로 시간(녹색) + 회색 (가)계획 퇴근 안내
    text, sub, state = expected_display(
        WorkStatus.CLOCKED_OUT, "17:30", -600, 8 * 3600, False,
        recog_end_hm="18:00", recog_end_passed=False,
    )
    assert text == "금일 근로 시간: 8h 0m"
    assert sub == "계획 퇴근 시간: ~18:00"  # (가)계획 종료 시각
    assert state == "done"


def test_expected_display_done_without_recog_has_no_sub():
    _, sub, state = expected_display(
        WorkStatus.CLOCKED_OUT, "17:30", -600, 8 * 3600, False,
        recog_end_hm=None, recog_end_passed=False,
    )
    assert sub is None
    assert state == "done"


def test_expected_display_overdue_past_recog_end():
    # 미퇴근 상태로 (가)계획 퇴근 시각 초과: 주황 + 계획 수정 필요
    text, sub, state = expected_display(
        WorkStatus.WORKING, "17:30", -1800, 8 * 3600 + 30 * 60, False,
        recog_end_hm="18:00", recog_end_passed=True,
    )
    assert "금일 근로 시간: 8h 30m" in text
    assert "⚠ 계획 수정 필요" in text
    assert sub == "계획 퇴근 시간: ~18:00"
    assert state == "overdue"


def test_expected_display_green_after_expected_reached_while_working():
    # 예상 퇴근 시각 달성(미퇴근, (가)계획 종료 전): 녹색 금일 근로 시간 전환
    text, sub, state = expected_display(
        WorkStatus.WORKING, "17:30", -600, 8 * 3600, False,
        recog_end_hm="19:00", recog_end_passed=False,
    )
    assert text == "금일 근로 시간: 8h 0m"
    assert sub == "계획 퇴근 시간: ~19:00"
    assert state == "done"


def test_expected_display_none_without_expectation():
    text, sub, state = expected_display(
        WorkStatus.NOT_CLOCKED_IN, None, None, None, False,
        recog_end_hm=None, recog_end_passed=False,
    )
    assert text == "퇴근 예정 시간: -"
    assert sub is None
    assert state == "pending"


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
