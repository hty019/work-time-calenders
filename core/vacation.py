"""휴가 도메인 로직.

휴가는 2h/4h/6h/8h(1day) 단위로 사용한다. 해당 일자에는 휴가 시간만큼
근로 인정시간으로 집계된다. 시간제(2/4/6h)는 시작~종료 구간을 가지며,
근로 구간과 겹치면 겹친 시간을 근로에서 제외해 이중 집계를 막는다
(worktime.effective_work_seconds). 8h(1day)는 구간 없이 합산한다.
"""
from __future__ import annotations

from dataclasses import dataclass

_MINUTES_PER_HOUR = 60
_DAY_MINUTES = 24 * _MINUTES_PER_HOUR

ALLOWED_MINUTES = (120, 240, 360, 480)  # 2h, 4h, 6h, 8h(1day)
FULL_DAY_MINUTES = 480


@dataclass(frozen=True)
class Vacation:
    """하루의 휴가. 시간제는 [start_min, end_min) 구간, 1day 는 구간 없음."""

    minutes: int
    start_min: int | None = None
    end_min: int | None = None

    @property
    def is_full_day(self) -> bool:
        return self.minutes >= FULL_DAY_MINUTES


def build_vacation(minutes: int, start_min: int | None = None) -> Vacation:
    """유형(분)·시작 시각으로 휴가를 생성. 종료는 시작+유형으로 자동 산출.

    검증 실패 시 ValueError.
    """
    if minutes not in ALLOWED_MINUTES:
        raise ValueError("휴가는 2h/4h/6h/8h(1day) 만 사용할 수 있습니다.")
    if minutes >= FULL_DAY_MINUTES:
        if start_min is not None:
            raise ValueError("8h(1day) 휴가는 시작 시각을 지정하지 않습니다.")
        return Vacation(minutes)
    if start_min is None:
        raise ValueError("시간제 휴가는 시작 시각(HH:MM)이 필요합니다.")
    if start_min < 0 or start_min + minutes > _DAY_MINUTES:
        raise ValueError("휴가 구간이 하루(00:00~24:00) 범위를 벗어납니다.")
    return Vacation(minutes, start_min, start_min + minutes)


class VacationService:
    def __init__(self, storage) -> None:
        self._storage = storage

    def get(self, date: str) -> Vacation | None:
        row = self._storage.get_vacation(date)
        if row is None:
            return None
        return Vacation(row[0], row[1], row[2])

    def set(self, date: str, vacation: Vacation) -> None:
        self._storage.set_vacation(
            date, vacation.minutes, vacation.start_min, vacation.end_min
        )

    def clear(self, date: str) -> None:
        self._storage.clear_vacation(date)
