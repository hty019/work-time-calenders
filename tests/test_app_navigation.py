from core.calendar_nav import (
    DELTA_DOWN,
    DELTA_LEFT,
    DELTA_RIGHT,
    DELTA_UP,
)
from ui.app import _navigate_selection, _prev_month, _next_month


def test_prev_month_wraps_year():
    assert _prev_month(2026, 1) == (2025, 12)
    assert _prev_month(2026, 7) == (2026, 6)


def test_next_month_wraps_year():
    assert _next_month(2026, 12) == (2027, 1)
    assert _next_month(2026, 7) == (2026, 8)


def test_date_range_forward():
    from ui.app import _date_range

    assert _date_range("2026-07-01", "2026-07-03") == [
        "2026-07-01", "2026-07-02", "2026-07-03",
    ]


def test_date_range_backward_and_single():
    from ui.app import _date_range

    assert _date_range("2026-07-03", "2026-07-01") == [
        "2026-07-03", "2026-07-02", "2026-07-01",
    ]
    assert _date_range("2026-07-05", "2026-07-05") == ["2026-07-05"]


def test_date_range_crosses_month():
    from ui.app import _date_range

    assert _date_range("2026-06-30", "2026-07-02") == [
        "2026-06-30", "2026-07-01", "2026-07-02",
    ]


# --- 화살표 이동 선택 계산 (_navigate_selection) --------------------------

_TODAY = "2026-07-13"


def _nav(selected, multi, delta, extend, y=2026, m=7, today=_TODAY):
    return _navigate_selection(selected, multi, y, m, today, delta, extend)


def test_navigate_single_right_moves_one_day():
    sel, multi = _nav("2026-07-10", [], DELTA_RIGHT, False)
    assert sel == "2026-07-11"
    assert multi == []


def test_navigate_single_down_moves_one_week():
    sel, multi = _nav("2026-07-10", [], DELTA_DOWN, False)
    assert sel == "2026-07-17"
    assert multi == []


def test_navigate_single_clears_existing_multi():
    sel, multi = _nav("2026-07-10", ["2026-07-08", "2026-07-10"], DELTA_LEFT, False)
    assert sel == "2026-07-09"
    assert multi == []


def test_navigate_boundary_right_at_month_end_is_noop():
    sel, multi = _nav("2026-07-31", ["2026-07-30", "2026-07-31"], DELTA_RIGHT, False)
    assert sel == "2026-07-31"
    assert multi == ["2026-07-30", "2026-07-31"]


def test_navigate_shift_right_extends_range():
    sel, multi = _nav("2026-07-10", [], DELTA_RIGHT, True)
    assert sel == "2026-07-11"
    assert multi == ["2026-07-10", "2026-07-11"]


def test_navigate_shift_down_selects_days_in_between():
    sel, multi = _nav("2026-07-10", [], DELTA_DOWN, True)
    assert sel == "2026-07-17"
    assert multi == [
        "2026-07-10", "2026-07-11", "2026-07-12", "2026-07-13",
        "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17",
    ]


def test_navigate_shift_up_unions_with_existing():
    sel, multi = _nav("2026-07-15", ["2026-07-15", "2026-07-16"], DELTA_UP, True)
    assert sel == "2026-07-08"
    # 기존 15·16 유지 + 08~15 추가
    assert set(multi) == {
        "2026-07-08", "2026-07-09", "2026-07-10", "2026-07-11",
        "2026-07-12", "2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16",
    }


def test_navigate_base_fallback_selects_today_without_moving():
    # 선택이 8월, 보는 달 7월 → 오늘(07-13) 선택만, 이동·확장 없음
    sel, multi = _nav("2026-08-05", [], DELTA_RIGHT, True)
    assert sel == "2026-07-13"
    assert multi == []


def test_navigate_base_fallback_first_day_when_today_absent():
    sel, multi = _nav("2026-08-05", [], DELTA_RIGHT, False, y=2026, m=9)
    assert sel == "2026-09-01"
    assert multi == []
