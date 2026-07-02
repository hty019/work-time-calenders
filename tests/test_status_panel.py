from core.attendance import WorkStatus
from core.stats import ProgressLevel
from ui.status_panel import expected_display, progress_caption


def test_expected_display_pending_shows_remaining():
    # 근무 중 + 예상 퇴근 전: 기존 예상 퇴근 표시
    title, text, sub, state = expected_display(
        WorkStatus.WORKING, "18:00", 2 * 3600, 6 * 3600, False
    )
    assert title == "오늘 예상 퇴근"
    assert text == "18:00 (2h 0m 남음)"
    assert sub is None
    assert state == "pending"


def test_expected_display_pending_with_range_warning():
    _, text, _, state = expected_display(
        WorkStatus.WORKING, "18:30", 2 * 3600, 6 * 3600, True
    )
    assert "⚠ (가)계획 종료 초과" in text
    assert state == "warn"


def test_expected_display_done_after_clock_out():
    # 퇴근 완료: 금일 근로 시간(녹색) + 회색 계획 퇴근 안내
    title, text, sub, state = expected_display(
        WorkStatus.CLOCKED_OUT, "17:30", -600, 8 * 3600, False
    )
    assert title == "금일 근로 시간"
    assert text == "8h 0m"
    assert sub == "계획 퇴근 ~17:30"
    assert state == "done"


def test_expected_display_overdue_without_clock_out():
    # 미퇴근 상태로 계획 퇴근 시간 초과: 주황 + 계획 수정 필요 경고
    title, text, sub, state = expected_display(
        WorkStatus.WORKING, "17:30", -1800, 8 * 3600 + 30 * 60, False
    )
    assert title == "금일 근로 시간"
    assert "8h 30m" in text
    assert "⚠ 계획 수정 필요" in text
    assert sub == "계획 퇴근 ~17:30"
    assert state == "overdue"


def test_expected_display_none_without_expectation():
    title, text, sub, state = expected_display(
        WorkStatus.NOT_CLOCKED_IN, None, None, None, False
    )
    assert text == "-"
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
