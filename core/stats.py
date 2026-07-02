"""월 근무 현황 집계 (status 패널용)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from core import timeutil
from core.calendar_model import max_month_hours, required_month_hours
from core.worktime import raw_seconds_for_net

_MINUTE_SECONDS = 60
_MINUTES_PER_HOUR = 60
_OVER_LIMIT_MINUTES = 20 * 60  # 법정 기준 초과 허용폭(20h). 넘으면 위험 단계.
_PERCENT = 100


class ProgressLevel(Enum):
    """진행률 바 단계: 법정 이내 / 초과 / +20h 초과 / 최대 초과."""

    NORMAL = "normal"        # 법정 기준 이내 (녹색)
    OVER = "over"            # 법정 기준 초과 ~ +20h (노랑)
    CRITICAL = "critical"    # 법정 기준 +20h 초과 ~ 최대 가능 (주황)
    EXCEEDED = "exceeded"    # 최대 근로 가능시간 초과 (빨강)


def progress_state(
    actual_seconds: int, required_minutes: int, max_minutes: int
) -> tuple[int, ProgressLevel]:
    """진행률 바의 (백분율, 단계) 산출.

    법정 기준 이내면 법정 기준을 max 로, 초과하면 최대 가능시간을 max 로
    바꾼다. 단계는 법정 초과(노랑) → +20h 초과(주황) → 최대 초과(빨강).
    """
    if required_minutes <= 0:
        return 0, ProgressLevel.NORMAL
    actual_minutes = actual_seconds // _MINUTE_SECONDS
    if actual_minutes <= required_minutes:
        return (
            actual_minutes * _PERCENT // required_minutes,
            ProgressLevel.NORMAL,
        )
    if actual_minutes > max_minutes:
        level = ProgressLevel.EXCEEDED
    elif actual_minutes > required_minutes + _OVER_LIMIT_MINUTES:
        level = ProgressLevel.CRITICAL
    else:
        level = ProgressLevel.OVER
    if max_minutes <= 0:
        return _PERCENT, level
    return min(actual_minutes * _PERCENT // max_minutes, _PERCENT), level


@dataclass
class MonthSummary:
    year: int
    month: int
    planned_minutes: int
    required_minutes: int
    max_minutes: int  # 최대 근로 가능시간(주 52h 기준)을 분으로 환산
    actual_seconds: int
    progress_ratio: float | None
    expected_clock_out: datetime | None
    remaining_seconds: int | None
    expected_exceeds_range: bool = False  # 예상 퇴근이 (가)계획 종료를 초과


def build_month_summary(
    storage,
    attendance_service,
    plan_service,
    year: int,
    month: int,
    holidays: dict[str, str],
    now: datetime,
) -> MonthSummary:
    planned_minutes = plan_service.month_planned_minutes(year, month, holidays)
    # 법정 요구 근로시간(말일/7*40 − 평일 공휴일*8). 시간 단위를 분으로 환산해 보관.
    required_minutes = (
        required_month_hours(year, month, holidays) * _MINUTES_PER_HOUR
    )
    # 최대 근로 가능시간(말일/7*52, 공휴일 차감 없음).
    max_minutes = max_month_hours(year, month, holidays) * _MINUTES_PER_HOUR
    in_progress = attendance_service.today_in_progress_seconds() or 0
    actual_seconds = attendance_service.month_total_seconds(year, month) + in_progress

    planned_seconds = planned_minutes * _MINUTE_SECONDS
    progress_ratio = (
        actual_seconds / planned_seconds if planned_seconds > 0 else None
    )

    expected, remaining = _today_expectation(
        storage, plan_service, holidays, now
    )
    exceeds = _exceeds_recognition_end(storage, timeutil.today_str(now), expected)
    return MonthSummary(
        year=year,
        month=month,
        planned_minutes=planned_minutes,
        required_minutes=required_minutes,
        max_minutes=max_minutes,
        actual_seconds=actual_seconds,
        progress_ratio=progress_ratio,
        expected_clock_out=expected,
        remaining_seconds=remaining,
        expected_exceeds_range=exceeds,
    )


def _today_expectation(storage, plan_service, holidays, now):
    """오늘 출근 기록+계획이 있으면 (예상 퇴근시각, 남은초) 반환."""
    today = timeutil.today_str(now)
    rec = storage.get(today)
    if rec is None or not rec.clock_in:
        return None, None
    planned_minutes = plan_service.effective_minutes(today, holidays)
    if planned_minutes <= 0:
        return None, None
    clock_in = timeutil.from_iso(rec.clock_in)
    raw = raw_seconds_for_net(planned_minutes * _MINUTE_SECONDS)
    expected = clock_in + timedelta(seconds=raw)
    remaining = int((expected - now).total_seconds())
    return expected, remaining


def _exceeds_recognition_end(
    storage, today: str, expected: datetime | None
) -> bool:
    """예상 퇴근 시각이 오늘 (가)계획 종료 시각을 넘는지 판정."""
    if expected is None:
        return False
    recog = storage.get_recognition(today)
    if recog is None:
        return False
    _, end_min = recog
    if timeutil.today_str(expected) != today:
        return True  # 자정을 넘기면 어떤 범위든 초과
    return expected.hour * _MINUTES_PER_HOUR + expected.minute > end_min
