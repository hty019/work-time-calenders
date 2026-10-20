from core.calendar_nav import (
    DELTA_DOWN,
    DELTA_LEFT,
    DELTA_RIGHT,
    DELTA_UP,
    in_month,
    resolve_nav_base,
    step_within_month,
)


def test_delta_constants():
    assert (DELTA_LEFT, DELTA_RIGHT, DELTA_UP, DELTA_DOWN) == (-1, 1, -7, 7)


def test_in_month():
    assert in_month("2026-07-15", 2026, 7) is True
    assert in_month("2026-08-01", 2026, 7) is False
    assert in_month("2026-06-30", 2026, 7) is False


def test_step_right_sunday_to_monday():
    # 2026-07-05 는 일요일 → +1 = 월요일 07-06 (순차 이동)
    assert step_within_month("2026-07-05", DELTA_RIGHT, 2026, 7) == "2026-07-06"


def test_step_left_and_right_within_month():
    assert step_within_month("2026-07-15", DELTA_LEFT, 2026, 7) == "2026-07-14"
    assert step_within_month("2026-07-15", DELTA_RIGHT, 2026, 7) == "2026-07-16"


def test_step_up_and_down_by_week():
    assert step_within_month("2026-07-15", DELTA_UP, 2026, 7) == "2026-07-08"
    assert step_within_month("2026-07-15", DELTA_DOWN, 2026, 7) == "2026-07-22"


def test_step_right_at_month_end_clamps():
    # 2026-07-31 에서 → 는 다음 달이므로 None
    assert step_within_month("2026-07-31", DELTA_RIGHT, 2026, 7) is None


def test_step_left_at_month_start_clamps():
    assert step_within_month("2026-07-01", DELTA_LEFT, 2026, 7) is None


def test_step_up_first_week_clamps():
    # 07-05 −7 = 06-28 (이전 달) → None
    assert step_within_month("2026-07-05", DELTA_UP, 2026, 7) is None


def test_step_down_last_week_clamps():
    # 07-28 +7 = 08-04 (다음 달) → None
    assert step_within_month("2026-07-28", DELTA_DOWN, 2026, 7) is None


def test_resolve_base_selected_in_view_moves():
    base, should_move = resolve_nav_base("2026-07-10", 2026, 7, "2026-07-13")
    assert base == "2026-07-10"
    assert should_move is True


def test_resolve_base_falls_back_to_today_in_view():
    # 선택이 8월, 보는 달은 7월, 오늘은 7월 → 오늘 기준, 이동 없이 선택만
    base, should_move = resolve_nav_base("2026-08-10", 2026, 7, "2026-07-13")
    assert base == "2026-07-13"
    assert should_move is False


def test_resolve_base_falls_back_to_first_day():
    # 선택도 오늘도 보는 달(2026-09)에 없음 → 1일
    base, should_move = resolve_nav_base("2026-08-10", 2026, 9, "2026-07-13")
    assert base == "2026-09-01"
    assert should_move is False


# --- 사각형 범위 선택 (rectangle_dates / rectangle_selection) -------------
# 2026-07: 1일=수. 1주차 = 06-29(월)~07-05(일), 2주차 = 07-06(월)~07-12(일)


def test_rectangle_same_weekday_two_weeks_selects_only_two():
    from core.calendar_nav import rectangle_dates

    assert rectangle_dates("2026-07-06", "2026-07-13", 2026, 7) == [
        "2026-07-06", "2026-07-13",
    ]


def test_rectangle_two_by_two():
    from core.calendar_nav import rectangle_dates

    assert rectangle_dates("2026-07-06", "2026-07-14", 2026, 7) == [
        "2026-07-06", "2026-07-07", "2026-07-13", "2026-07-14",
    ]


def test_rectangle_reverse_direction_same_result():
    from core.calendar_nav import rectangle_dates

    # 우하→좌상 방향도 같은 사각형
    assert rectangle_dates("2026-07-14", "2026-07-06", 2026, 7) == [
        "2026-07-06", "2026-07-07", "2026-07-13", "2026-07-14",
    ]


def test_rectangle_anti_diagonal():
    from core.calendar_nav import rectangle_dates

    # 1주차 일(07-12) → 2주차 토(07-18): 토·일 열 × 2행
    assert rectangle_dates("2026-07-12", "2026-07-18", 2026, 7) == [
        "2026-07-11", "2026-07-12", "2026-07-18", "2026-07-19",
    ]


def test_rectangle_same_row_is_contiguous_days():
    from core.calendar_nav import rectangle_dates

    assert rectangle_dates("2026-07-08", "2026-07-10", 2026, 7) == [
        "2026-07-08", "2026-07-09", "2026-07-10",
    ]


def test_rectangle_excludes_days_outside_view_month():
    from core.calendar_nav import rectangle_dates

    # 1주차 월·화(06-29, 06-30)는 6월 → 보는 달(7월) 밖이라 제외
    assert rectangle_dates("2026-07-01", "2026-07-06", 2026, 7) == [
        "2026-07-01", "2026-07-06", "2026-07-07", "2026-07-08",
    ]


def test_rectangle_single_cell():
    from core.calendar_nav import rectangle_dates

    assert rectangle_dates("2026-07-06", "2026-07-06", 2026, 7) == [
        "2026-07-06",
    ]


def test_rectangle_selection_unions_base():
    from core.calendar_nav import rectangle_selection

    assert rectangle_selection(
        "2026-07-06", ["2026-07-20"], "2026-07-13", 2026, 7
    ) == ["2026-07-06", "2026-07-13", "2026-07-20"]


def test_rectangle_selection_single_cell_without_base_is_empty():
    from core.calendar_nav import rectangle_selection

    # 1일 이하 → 다중 선택 아님
    assert rectangle_selection("2026-07-06", [], "2026-07-06", 2026, 7) == []
