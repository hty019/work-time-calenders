"""캘린더 화살표 이동 로직 (Qt 비의존 순수 함수).

방향별 일수 델타로 선택 일자를 이동하되, 현재 보는 달을 벗어나면 이동하지
않는다(경계 clamp). 달력 그리드에서 위/아래는 한 주(7일) 이동이다.
"""
from __future__ import annotations

import datetime

_DAYS_PER_WEEK = 7

DELTA_LEFT = -1
DELTA_RIGHT = 1
DELTA_UP = -_DAYS_PER_WEEK
DELTA_DOWN = _DAYS_PER_WEEK


def in_month(date: str, year: int, month: int) -> bool:
    """date(ISO) 가 주어진 연·월에 속하는지."""
    d = datetime.date.fromisoformat(date)
    return d.year == year and d.month == month


def step_within_month(
    date: str, delta_days: int, year: int, month: int
) -> str | None:
    """date + delta_days 를 계산하되, 같은 달이 아니면 None(경계 no-op)."""
    moved = datetime.date.fromisoformat(date) + datetime.timedelta(
        days=delta_days
    )
    if moved.year != year or moved.month != month:
        return None
    return moved.isoformat()


def resolve_nav_base(
    selected_date: str, year: int, month: int, today: str
) -> tuple[str, bool]:
    """화살표 이동의 기준일과 이동 여부를 결정한다.

    선택 일자가 보는 달에 있으면 (선택 일자, True) — 그 방향으로 이동.
    없으면 (오늘 또는 그 달 1일, False) — 첫 입력은 이동 없이 기준일만 선택.
    """
    if in_month(selected_date, year, month):
        return selected_date, True
    if in_month(today, year, month):
        return today, False
    return f"{year:04d}-{month:02d}-01", False


def _week_start(d: datetime.date) -> datetime.date:
    """d 가 속한 주(월요일 시작 그리드 행)의 월요일."""
    return d - datetime.timedelta(days=d.weekday())


def rectangle_dates(
    anchor: str, target: str, year: int, month: int
) -> list[str]:
    """달력 그리드에서 anchor~target 을 대각 꼭짓점으로 하는 사각형 일자.

    행 = 월요일 시작 주, 열 = 요일. 보는 달 밖 일자는 제외하고 정렬해 반환한다.
    """
    a = datetime.date.fromisoformat(anchor)
    t = datetime.date.fromisoformat(target)
    first_week, last_week = sorted((_week_start(a), _week_start(t)))
    first_col, last_col = sorted((a.weekday(), t.weekday()))
    week_count = (last_week - first_week).days // _DAYS_PER_WEEK + 1
    dates: list[str] = []
    for row in range(week_count):
        week = first_week + datetime.timedelta(days=row * _DAYS_PER_WEEK)
        for col in range(first_col, last_col + 1):
            day = week + datetime.timedelta(days=col)
            if day.year == year and day.month == month:
                dates.append(day.isoformat())
    return dates


def rectangle_selection(
    anchor: str, base: list[str], target: str, year: int, month: int
) -> list[str]:
    """Shift 선택 결과: 기준 선택(base) ∪ 사각형(anchor~target), 정렬.

    1일 이하이면 다중 선택이 아니므로 빈 목록.
    """
    dates = sorted(set(base) | set(rectangle_dates(anchor, target, year, month)))
    return dates if len(dates) >= 2 else []
