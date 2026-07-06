from core.attendance import WorkStatus
from core.stats import ProgressLevel
from core.vacation import YearLeaveSummary
from ui import theme
from ui.status_panel import (
    clock_in_line,
    expected_line,
    leave_line,
    progress_caption,
    remaining_line,
    state_display,
    state_rich_text,
    stay_line,
)


def test_state_rich_text_prefix_white_body_colored():
    # '상태: ' 접두는 흰색 고정, 상태 문구만 상태 색상 적용
    html = state_rich_text("상태: 조기 퇴근", "early")
    assert html == (
        f'<span style="color:{theme.FG_DATE};">상태: </span>'
        f'<span style="color:{theme.FG_OVERDUE}; font-weight:normal;">'
        "조기 퇴근</span>"
    )


def test_state_rich_text_bold_state():
    html = state_rich_text("상태: ⚠ 계획 시간 범위 초과!!", "over")
    assert html == (
        f'<span style="color:{theme.FG_DATE};">상태: </span>'
        f'<span style="color:{theme.FG_RANGE_WARN}; font-weight:bold;">'
        "⚠ 계획 시간 범위 초과!!</span>"
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


def test_expected_line_shows_time_with_basis():
    # 예상 퇴근 시각 + 산정 기준 순근무 시간 (경고는 상태 라인이 담당)
    assert expected_line("18:42", 480) == (
        "퇴근 예정 시간: 18:42 (8h 0m 근무 기준)"
    )


def test_expected_line_dash_without_expectation():
    assert expected_line(None, None) == "퇴근 예정 시간: -"


# --- 상태 라인 -------------------------------------------------------------


def test_state_normal_while_working():
    text, key = state_display(
        WorkStatus.WORKING, recog_end_passed=False,
        exceeds_range=False, reached=False,
    )
    assert text == "상태: 정상 근무중"
    assert key == "normal"


def test_state_reached_while_working():
    # 예상 퇴근 시각 달성 후 미퇴근
    text, key = state_display(
        WorkStatus.WORKING, recog_end_passed=False,
        exceeds_range=False, reached=True,
    )
    assert text == "상태: 금일 근무 달성 · 퇴근 가능"
    assert key == "reached"


def test_state_over_recog_end_wins():
    # 계획 퇴근 시각을 실제로 넘김: 최우선 경고
    text, key = state_display(
        WorkStatus.WORKING, recog_end_passed=True,
        exceeds_range=True, reached=True,
    )
    assert text == "상태: ⚠ 계획 시간 범위 초과!!"
    assert key == "over"


def test_state_warn_expected_exceeds_range():
    # 예상 퇴근이 계획 범위를 넘을 것으로 예상 (사전 경고)
    text, key = state_display(
        WorkStatus.WORKING, recog_end_passed=False,
        exceeds_range=True, reached=False,
    )
    assert text == "상태: ⚠ 계획 범위 초과 예상"
    assert key == "warn"


def test_state_clocked_out_early():
    # 예상 퇴근 시각 이전 퇴근: 조기 퇴근 (주황)
    text, key = state_display(
        WorkStatus.CLOCKED_OUT, recog_end_passed=False,
        exceeds_range=False, reached=False, clocked_out_early=True,
    )
    assert text == "상태: 조기 퇴근"
    assert key == "early"


def test_state_clocked_out_normal():
    # 예상 퇴근 시각 이후 퇴근: 정상 퇴근 (녹색)
    text, key = state_display(
        WorkStatus.CLOCKED_OUT, recog_end_passed=True,
        exceeds_range=False, reached=True, clocked_out_early=False,
    )
    assert text == "상태: 정상 퇴근"
    assert key == "done_normal"


def test_state_clocked_out_unknown_expectation():
    # 예상 퇴근이 없어 판정 불가: 기존 퇴근 완료 (회색)
    text, key = state_display(
        WorkStatus.CLOCKED_OUT, recog_end_passed=False,
        exceeds_range=False, reached=False, clocked_out_early=None,
    )
    assert text == "상태: 퇴근 완료"
    assert key == "done"


def test_state_not_clocked_in():
    text, key = state_display(
        WorkStatus.NOT_CLOCKED_IN, recog_end_passed=False,
        exceeds_range=False, reached=False,
    )
    assert text == "상태: 미출근"
    assert key == "off"


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


# --- 선택 날짜(과거/미래) 표시 ----------------------------------------------


def _detail(**kw):
    from core.day_detail import DayDetail
    base = dict(
        date="2026-07-01", kind="past", clock_in_hm=None, clock_out_hm=None,
        recog_start_hm=None, recog_end_hm=None, planned_minutes=0,
        memo=None, has_record=False, clocked_out_early=None,
    )
    base.update(kw)
    return DayDetail(**base)


def test_past_lines_with_record():
    from ui.status_panel import past_lines
    d = _detail(
        clock_in_hm="09:12", clock_out_hm="18:00",
        recog_start_hm="08:00", recog_end_hm="21:50", has_record=True,
    )
    assert past_lines(d) == [
        "출근 시간: 09:12",
        "퇴근 시간: 18:00",
        "계획 시간: 08:00~21:50",
    ]


def test_past_lines_without_data():
    from ui.status_panel import past_lines
    assert past_lines(_detail()) == [
        "출근 시간: -",
        "퇴근 시간: -",
        "계획 시간: -",
    ]


def test_future_lines():
    from ui.status_panel import future_lines
    d = _detail(
        kind="future", planned_minutes=480,
        recog_start_hm="08:00", recog_end_hm="21:50",
    )
    assert future_lines(d) == [
        "실 계획: 8h 0m",
        "(가)계획 시간: 08:00 ~ 21:50",
    ]


def test_future_lines_without_recog():
    from ui.status_panel import future_lines
    d = _detail(kind="future", planned_minutes=300)
    assert future_lines(d) == ["실 계획: 5h 0m", "(가)계획 시간: -"]


def test_past_state_variants():
    from ui.status_panel import past_state_display
    assert past_state_display(_detail()) == ("상태: 미출근", "off")
    assert past_state_display(
        _detail(has_record=True, clock_in_hm="09:00")
    ) == ("상태: ⚠ 퇴근 미기록", "over")
    assert past_state_display(
        _detail(has_record=True, clock_out_hm="16:00", clocked_out_early=True)
    ) == ("상태: 조기 퇴근", "early")
    assert past_state_display(
        _detail(has_record=True, clock_out_hm="18:00", clocked_out_early=False)
    ) == ("상태: 정상 퇴근", "done_normal")
    assert past_state_display(
        _detail(has_record=True, clock_out_hm="18:00", clocked_out_early=None)
    ) == ("상태: 퇴근 완료", "done")
