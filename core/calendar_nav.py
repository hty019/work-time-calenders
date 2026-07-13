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
