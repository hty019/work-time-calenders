"""사전 정의 출근 인정 시간 범위 도메인 로직. UI 표기는 '(가)계획'.

인정 범위((가)계획)는 근로가 인정되는 시각 구간(예 09:00~15:00)이다. 실제 근로가
이 범위를 벗어나면 벗어난 시간은 인정받지 못하므로, 범위를 미리 설정해
이탈 여부를 표시하고 계획(분)과의 정합성을 검증한다.
근무시간(work_seconds) 계산 자체는 변경하지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.plan import weekday_dates
from core.worktime import raw_seconds_for_net

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_MINUTES_PER_HOUR = 60
_SECONDS_PER_MINUTE = 60


def hhmm_to_minutes(hhmm: str) -> int:
    """'HH:MM' → 자정 기준 분. 형식 오류 시 ValueError."""
    m = _HHMM_RE.match(hhmm.strip())
    if not m:
        raise ValueError(f"시각 형식은 HH:MM 이어야 합니다: {hhmm!r}")
    return int(m.group(1)) * _MINUTES_PER_HOUR + int(m.group(2))


def minutes_to_hhmm(minutes: int) -> str:
    """자정 기준 분 → 'HH:MM'."""
    return f"{minutes // _MINUTES_PER_HOUR:02d}:{minutes % _MINUTES_PER_HOUR:02d}"


@dataclass(frozen=True)
class RecognitionRange:
    """자정 기준 분 단위의 인정 시각 구간 [start_min, end_min]."""

    start_min: int
    end_min: int

    @property
    def width_minutes(self) -> int:
        return self.end_min - self.start_min

    def covers(self, in_min: int, out_min: int) -> bool:
        """실제 출근·퇴근(자정 기준 분)이 범위 안에 있는지."""
        return self.start_min <= in_min and out_min <= self.end_min


def validate_range_against_plan(
    planned_minutes: int, rng: RecognitionRange
) -> str | None:
    """계획(순근무 분) 대비 인정 범위 폭 검증. 문제 없으면 None, 있으면 메시지.

    계획을 채우려면 휴게시간까지 포함한 체류(raw_seconds_for_net)가 필요하므로
    범위 폭이 필요 체류보다 좁으면 저장을 막아야 한다.
    """
    if rng.width_minutes <= 0:
        return "(가)계획의 종료 시각은 시작 시각보다 늦어야 합니다."
    needed_minutes = (
        raw_seconds_for_net(planned_minutes * _SECONDS_PER_MINUTE)
        // _SECONDS_PER_MINUTE
    )
    if rng.width_minutes < needed_minutes:
        return (
            f"(가)계획 범위({rng.width_minutes}분)가 실 계획을 채우는 데 필요한 "
            f"체류시간({needed_minutes}분, 휴게 포함)보다 좁습니다."
        )
    return None


class RecognitionService:
    def __init__(self, storage) -> None:
        self._storage = storage

    def get(self, date: str) -> RecognitionRange | None:
        row = self._storage.get_recognition(date)
        if row is None:
            return None
        return RecognitionRange(row[0], row[1])

    def set(self, date: str, rng: RecognitionRange) -> None:
        self._storage.set_recognition(date, rng.start_min, rng.end_min)

    def clear(self, date: str) -> None:
        self._storage.clear_recognition(date)

    def set_weekday(
        self,
        year: int,
        month: int,
        weekday: int,
        rng: RecognitionRange | None,
        exclude_dates: set[str] = frozenset(),
    ) -> int:
        """해당 월의 지정 요일 모든 날짜에 인정 범위를 일괄 설정/해제.

        exclude_dates(퇴근 완료일 등)는 건드리지 않는다.
        """
        dates = [
            d for d in weekday_dates(year, month, weekday)
            if d not in exclude_dates
        ]
        for date in dates:
            if rng is None:
                self._storage.clear_recognition(date)
            else:
                self._storage.set_recognition(date, rng.start_min, rng.end_min)
        return len(dates)
