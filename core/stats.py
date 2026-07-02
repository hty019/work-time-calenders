"""월 근무 현황 집계 (status 패널용)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core import timeutil
from core.calendar_model import required_month_hours
from core.worktime import raw_seconds_for_net

_MINUTE_SECONDS = 60
_MINUTES_PER_HOUR = 60


@dataclass
class MonthSummary:
    year: int
    month: int
    planned_minutes: int
    required_minutes: int
    actual_seconds: int
    progress_ratio: float | None
    expected_clock_out: datetime | None
    remaining_seconds: int | None


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
    in_progress = attendance_service.today_in_progress_seconds() or 0
    actual_seconds = attendance_service.month_total_seconds(year, month) + in_progress

    planned_seconds = planned_minutes * _MINUTE_SECONDS
    progress_ratio = (
        actual_seconds / planned_seconds if planned_seconds > 0 else None
    )

    expected, remaining = _today_expectation(
        storage, plan_service, holidays, now
    )
    return MonthSummary(
        year=year,
        month=month,
        planned_minutes=planned_minutes,
        required_minutes=required_minutes,
        actual_seconds=actual_seconds,
        progress_ratio=progress_ratio,
        expected_clock_out=expected,
        remaining_seconds=remaining,
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
