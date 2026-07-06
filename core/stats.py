"""월 근무 현황 집계 (status 패널용)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from core import timeutil
from core.calendar_model import max_month_hours, required_month_hours
from core.recognition import minutes_to_hhmm
from core.worktime import net_seconds_for_raw, raw_seconds_for_net

_MINUTE_SECONDS = 60
_MINUTES_PER_HOUR = 60
_HOUR_SECONDS = 3600
_OVER_LIMIT_HOURS = 20  # 법정 기준 초과 허용폭(20h). 넘으면 위험 단계.
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
    """진행률 바의 (백분율, 단계) 산출. 분 단위는 버리고 시간 기준으로 계산.

    법정 기준 이내면 법정 기준을 max 로, 초과하면 최대 가능시간을 max 로
    바꾼다. 단계는 법정 초과(노랑) → +20h 초과(주황) → 최대 초과(빨강).
    """
    required_hours = required_minutes // _MINUTES_PER_HOUR
    max_hours = max_minutes // _MINUTES_PER_HOUR
    if required_hours <= 0:
        return 0, ProgressLevel.NORMAL
    actual_hours = actual_seconds // _HOUR_SECONDS
    if actual_hours <= required_hours:
        return (
            actual_hours * _PERCENT // required_hours,
            ProgressLevel.NORMAL,
        )
    if actual_hours > max_hours:
        level = ProgressLevel.EXCEEDED
    elif actual_hours > required_hours + _OVER_LIMIT_HOURS:
        level = ProgressLevel.CRITICAL
    else:
        level = ProgressLevel.OVER
    if max_hours <= 0:
        return _PERCENT, level
    return min(actual_hours * _PERCENT // max_hours, _PERCENT), level


@dataclass
class MonthSummary:
    year: int
    month: int
    planned_minutes: int
    required_minutes: int
    max_minutes: int  # 최대 근로 가능시간(주 52h 기준)을 분으로 환산
    recog_planned_minutes: int  # 월 (가)계획 합계(각 범위 폭에서 휴게 차감)
    actual_seconds: int
    progress_ratio: float | None
    expected_clock_out: datetime | None
    remaining_seconds: int | None
    expected_exceeds_range: bool = False  # 예상 퇴근이 (가)계획 종료를 초과
    today_work_seconds: int | None = None  # 오늘 근로 인정초(진행 중=실시간)
    today_recog_end_hm: str | None = None  # 오늘 (가)계획 종료 "HH:MM"
    recog_end_passed: bool = False  # 현재 시각이 (가)계획 종료를 지났는지
    today_clock_in_hm: str | None = None  # 오늘 출근 시각 "HH:MM"
    today_stay_seconds: int | None = None  # 출근 후 체류초(휴게 포함 경과)
    expected_basis_minutes: int | None = None  # 예상 퇴근 산정 기준 순근무 분
    today_clocked_out_early: bool | None = None  # 예상보다 이른 퇴근 여부


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
    recog_planned_minutes = _recog_planned_minutes(storage, year, month)
    in_progress_raw = attendance_service.today_in_progress_seconds()
    in_progress = in_progress_raw or 0
    # 휴가는 근로 인정시간으로 월 누적에 합산한다.
    vacation_seconds = sum(
        row[0] * _MINUTE_SECONDS
        for row in storage.list_vacation_month(year, month).values()
    )
    actual_seconds = (
        attendance_service.month_total_seconds(year, month)
        + in_progress
        + vacation_seconds
    )

    planned_seconds = planned_minutes * _MINUTE_SECONDS
    progress_ratio = (
        actual_seconds / planned_seconds if planned_seconds > 0 else None
    )

    expected, remaining, expected_basis = _today_expectation(
        storage, plan_service, holidays, now
    )
    exceeds = _exceeds_recognition_end(storage, timeutil.today_str(now), expected)
    # 오늘 근로 인정초: 진행 중이면 실시간, 퇴근했으면 확정치.
    rec_today = storage.get(timeutil.today_str(now))
    today_work_seconds = (
        in_progress_raw
        if in_progress_raw is not None
        else (rec_today.work_seconds if rec_today else None)
    )
    today_clock_in_hm = (
        timeutil.from_iso(rec_today.clock_in).strftime("%H:%M")
        if rec_today and rec_today.clock_in
        else None
    )
    # 체류: 출근~현재(근무 중) 또는 출근~퇴근(완료). 휴게 포함 경과 시간.
    today_stay_seconds = None
    if rec_today and rec_today.clock_in:
        stay_end = (
            timeutil.from_iso(rec_today.clock_out)
            if rec_today.clock_out
            else now
        )
        today_stay_seconds = int(
            (stay_end - timeutil.from_iso(rec_today.clock_in)).total_seconds()
        )
    # 조기 퇴근 판정: 퇴근 기록이 예상 퇴근 시각보다 이른지. 판정 불가면 None.
    today_clocked_out_early = None
    if rec_today and rec_today.clock_out and expected is not None:
        today_clocked_out_early = (
            timeutil.from_iso(rec_today.clock_out) < expected
        )
    # 오늘 (가)계획 종료 시각과 초과 여부 (STATUS '계획 퇴근' 표시용).
    recog_today = storage.get_recognition(timeutil.today_str(now))
    today_recog_end_hm = None
    recog_end_passed = False
    if recog_today is not None:
        _, recog_end_min = recog_today
        today_recog_end_hm = minutes_to_hhmm(recog_end_min)
        now_minutes = now.hour * _MINUTES_PER_HOUR + now.minute
        recog_end_passed = now_minutes > recog_end_min
    return MonthSummary(
        year=year,
        month=month,
        planned_minutes=planned_minutes,
        required_minutes=required_minutes,
        max_minutes=max_minutes,
        recog_planned_minutes=recog_planned_minutes,
        actual_seconds=actual_seconds,
        progress_ratio=progress_ratio,
        expected_clock_out=expected,
        remaining_seconds=remaining,
        expected_exceeds_range=exceeds,
        today_work_seconds=today_work_seconds,
        today_recog_end_hm=today_recog_end_hm,
        recog_end_passed=recog_end_passed,
        today_clock_in_hm=today_clock_in_hm,
        today_stay_seconds=today_stay_seconds,
        expected_basis_minutes=expected_basis,
        today_clocked_out_early=today_clocked_out_early,
    )


def _recog_planned_minutes(storage, year: int, month: int) -> int:
    """월 (가)계획 합계(분). 각 범위 폭(체류)에서 휴게를 제한 순근무로 환산."""
    total = 0
    for start_min, end_min in storage.list_recognition_month(year, month).values():
        width_seconds = max(end_min - start_min, 0) * _MINUTE_SECONDS
        total += net_seconds_for_raw(width_seconds) // _MINUTE_SECONDS
    return total


def _today_expectation(storage, plan_service, holidays, now):
    """오늘 출근 기록+계획이 있으면 (예상 퇴근시각, 남은초, 기준 순근무 분) 반환.

    기준 순근무 분은 예상 퇴근 산정에 쓰인 순근무량(계획 − 휴가분)이다.
    오늘 휴가가 있으면 남은 필요 순근무 = 계획 − 휴가분으로 줄이고,
    시간제 휴가 구간이 예상 체류와 겹치면 겹침만큼 퇴근을 뒤로 민다.
    """
    today = timeutil.today_str(now)
    rec = storage.get(today)
    if rec is None or not rec.clock_in:
        return None, None, None
    planned_minutes = plan_service.effective_minutes(today, holidays)
    if planned_minutes <= 0:
        return None, None, None
    vacation = storage.get_vacation(today)
    vacation_minutes = vacation[0] if vacation else 0
    remaining_minutes = planned_minutes - vacation_minutes
    if remaining_minutes <= 0:
        return None, None, None  # 휴가만으로 계획 충족
    clock_in = timeutil.from_iso(rec.clock_in)
    raw = raw_seconds_for_net(remaining_minutes * _MINUTE_SECONDS)
    if vacation and vacation[1] is not None and vacation[2] is not None:
        raw = _extend_past_vacation(clock_in, raw, vacation[1], vacation[2])
    expected = clock_in + timedelta(seconds=raw)
    remaining = int((expected - now).total_seconds())
    return expected, remaining, remaining_minutes


def _extend_past_vacation(
    clock_in: datetime, raw: int, vac_start_min: int, vac_end_min: int
) -> int:
    """예상 체류 구간이 휴가 구간과 겹치면 겹침만큼 체류를 늘린다.

    늘어난 구간이 다시 휴가와 더 겹칠 수 있어 수렴할 때까지 반복한다
    (휴가 1건이므로 겹침이 휴가 길이로 유계 → 항상 수렴).
    """
    in_seconds = (
        clock_in.hour * 3600 + clock_in.minute * 60 + clock_in.second
    )
    vac_start = vac_start_min * 60
    vac_end = vac_end_min * 60
    total = raw
    while True:
        overlap = max(
            0, min(in_seconds + total, vac_end) - max(in_seconds, vac_start)
        )
        extended = raw + overlap
        if extended == total:
            return total
        total = extended


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
