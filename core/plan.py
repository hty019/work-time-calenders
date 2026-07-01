"""날짜별 계획 근무시간(순근무 분) 도출 서비스."""
from __future__ import annotations

import calendar
import datetime
from typing import Callable

import config

SATURDAY = 5  # date.weekday(): 월=0 ~ 일=6, 토=5 · 일=6


class PlanService:
    def __init__(
        self,
        storage,
        default_minutes_getter: Callable[[], int] = config.get_default_daily_minutes,
    ) -> None:
        self._storage = storage
        self._default_getter = default_minutes_getter

    def get_override(self, date: str) -> int | None:
        return self._storage.get_plan(date)

    def set_plan(self, date: str, minutes: int) -> None:
        self._storage.set_plan(date, minutes)

    def clear_plan(self, date: str) -> None:
        self._storage.clear_plan(date)

    def effective_minutes(self, date: str, holidays: dict[str, str]) -> int:
        """오버라이드가 있으면 그 값, 없으면 주말·공휴일 0, 평일 기본값."""
        override = self._storage.get_plan(date)
        if override is not None:
            return override
        d = datetime.date.fromisoformat(date)
        if d.weekday() >= SATURDAY or date in holidays:
            return 0
        return self._default_getter()

    def month_planned_minutes(
        self, year: int, month: int, holidays: dict[str, str]
    ) -> int:
        last_day = calendar.monthrange(year, month)[1]
        total = 0
        for day in range(1, last_day + 1):
            date = f"{year:04d}-{month:02d}-{day:02d}"
            total += self.effective_minutes(date, holidays)
        return total
