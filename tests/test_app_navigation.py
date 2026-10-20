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


# --- 화살표 이동 선택 계산 (_navigate_selection) --------------------------

_TODAY = "2026-07-13"


def _nav(selected, multi, delta, extend, y=2026, m=7, today=_TODAY):
    return _navigate_selection(selected, multi, y, m, today, delta, extend)


def test_navigate_single_right_moves_one_day():
    sel, multi, _, _ = _nav("2026-07-10", [], DELTA_RIGHT, False)
    assert sel == "2026-07-11"
    assert multi == []


def test_navigate_single_down_moves_one_week():
    sel, multi, _, _ = _nav("2026-07-10", [], DELTA_DOWN, False)
    assert sel == "2026-07-17"
    assert multi == []


def test_navigate_single_clears_existing_multi():
    sel, multi, _, _ = _nav("2026-07-10", ["2026-07-08", "2026-07-10"], DELTA_LEFT, False)
    assert sel == "2026-07-09"
    assert multi == []


def test_navigate_boundary_right_at_month_end_is_noop():
    sel, multi, _, _ = _nav("2026-07-31", ["2026-07-30", "2026-07-31"], DELTA_RIGHT, False)
    assert sel == "2026-07-31"
    assert multi == ["2026-07-30", "2026-07-31"]


def test_navigate_shift_right_extends_range():
    sel, multi, _, _ = _nav("2026-07-10", [], DELTA_RIGHT, True)
    assert sel == "2026-07-11"
    assert multi == ["2026-07-10", "2026-07-11"]


def test_navigate_shift_down_selects_rectangle_column():
    # 금(07-10) → 다음 주 금(07-17): 같은 열 두 칸만 (사이 일자 미포함)
    sel, multi, _, _ = _nav("2026-07-10", [], DELTA_DOWN, True)
    assert sel == "2026-07-17"
    assert multi == ["2026-07-10", "2026-07-17"]


def test_navigate_shift_keeps_anchor_and_grows_rectangle():
    # 월(07-06) Shift+↓ → Shift+→ : 앵커 07-06 고정, 2×2 사각형
    first = _nav("2026-07-06", [], DELTA_DOWN, True)
    assert first.anchor == "2026-07-06"
    second = _navigate_selection(
        first.selected, first.multi, 2026, 7, _TODAY, DELTA_RIGHT, True,
        anchor=first.anchor, base=first.base,
    )
    assert second.selected == "2026-07-14"
    assert second.multi == [
        "2026-07-06", "2026-07-07", "2026-07-13", "2026-07-14",
    ]


def test_navigate_shift_shrinks_rectangle_back():
    # 사각형을 되돌리면 범위도 줄어든다 (누적 합집합 아님)
    first = _nav("2026-07-06", [], DELTA_RIGHT, True)
    second = _navigate_selection(
        first.selected, first.multi, 2026, 7, _TODAY, DELTA_LEFT, True,
        anchor=first.anchor, base=first.base,
    )
    assert second.selected == "2026-07-06"
    assert second.multi == []


def test_navigate_shift_up_unions_with_existing():
    # 기존 다중 선택(15·16)에서 커서(15)가 앵커 → 15~08 사각형 + 16 유지
    sel, multi, _, _ = _nav(
        "2026-07-15", ["2026-07-15", "2026-07-16"], DELTA_UP, True
    )
    assert sel == "2026-07-08"
    assert multi == ["2026-07-08", "2026-07-15", "2026-07-16"]


def test_navigate_without_shift_resets_anchor():
    result = _nav("2026-07-10", [], DELTA_RIGHT, False)
    assert result.anchor is None


def test_navigate_base_fallback_selects_today_without_moving():
    # 선택이 8월, 보는 달 7월 → 오늘(07-13) 선택만, 이동·확장 없음
    sel, multi, _, _ = _nav("2026-08-05", [], DELTA_RIGHT, True)
    assert sel == "2026-07-13"
    assert multi == []


def test_navigate_base_fallback_first_day_when_today_absent():
    sel, multi, _, _ = _nav("2026-08-05", [], DELTA_RIGHT, False, y=2026, m=9)
    assert sel == "2026-09-01"
    assert multi == []
