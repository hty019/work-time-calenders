"""날짜별 계획 근무시간(순근무 분) 도출 서비스."""
from __future__ import annotations

import calendar
import datetime
from typing import Callable

import config

SATURDAY = 5  # date.weekday(): 월=0 ~ 일=6, 토=5 · 일=6


def weekday_dates(year: int, month: int, weekday: int) -> list[str]:
    """해당 월에서 주어진 요일(월=0..일=6)의 모든 날짜(YYYY-MM-DD) 목록."""
    last_day = calendar.monthrange(year, month)[1]
    dates = []
    for day in range(1, last_day + 1):
        d = datetime.date(year, month, day)
        if d.weekday() == weekday:
            dates.append(d.isoformat())
    return dates


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

    def set_weekday_plan(
        self, year: int, month: int, weekday: int, minutes: int | None
    ) -> int:
        """해당 월의 지정 요일 모든 날짜에 계획(분)을 일괄 설정한다.

        minutes 가 None 이면 오버라이드를 해제(기본값 복귀)한다.
        실제 처리한 날짜 수를 반환한다.
        """
        dates = weekday_dates(year, month, weekday)
        for date in dates:
            if minutes is None:
                self._storage.clear_plan(date)
            else:
                self._storage.set_plan(date, minutes)
        return len(dates)

    def baseline_minutes(self, date: str, holidays: dict[str, str]) -> int:
        """오버라이드를 무시한 기본 계획: 주말·공휴일 0, 평일 기본값."""
        d = datetime.date.fromisoformat(date)
        if d.weekday() >= SATURDAY or date in holidays:
            return 0
        return self._default_getter()

    def effective_minutes(self, date: str, holidays: dict[str, str]) -> int:
        """오버라이드가 있으면 그 값, 없으면 기본 계획(baseline)."""
        override = self._storage.get_plan(date)
        if override is not None:
            return override
        return self.baseline_minutes(date, holidays)

    def month_planned_minutes(
        self, year: int, month: int, holidays: dict[str, str]
    ) -> int:
        last_day = calendar.monthrange(year, month)[1]
        total = 0
        for day in range(1, last_day + 1):
            date = f"{year:04d}-{month:02d}-{day:02d}"
            total += self.effective_minutes(date, holidays)
        return total
