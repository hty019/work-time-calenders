"""선택 날짜 상세(과거/오늘/미래) 집계 — STATUS 패널 표시용."""
from __future__ import annotations

from dataclasses import dataclass

from core import timeutil
from core.recognition import minutes_to_hhmm
from core.stats import expected_clock_out_at

KIND_PAST = "past"
KIND_TODAY = "today"
KIND_FUTURE = "future"


@dataclass(frozen=True)
class DayDetail:
    """선택 날짜의 표시용 상세. 시각은 'HH:MM', 없으면 None."""

    date: str
    kind: str  # past | today | future
    clock_in_hm: str | None
    clock_out_hm: str | None
    recog_start_hm: str | None
    recog_end_hm: str | None
    planned_minutes: int
    memo: str | None
    has_record: bool
    clocked_out_early: bool | None  # 예상 퇴근 대비 조기 여부 (판정 불가 None)
    vacation_minutes: int = 0       # 휴가 분 (없으면 0)
    vacation_start_hm: str | None = None  # 시간제 휴가 시작 "HH:MM"
    vacation_end_hm: str | None = None    # 시간제 휴가 종료 "HH:MM"
    work_seconds: int | None = None       # 저장된 순근로(초), 미퇴근이면 None


def _classify(date: str, today: str) -> str:
    if date == today:
        return KIND_TODAY
    return KIND_PAST if date < today else KIND_FUTURE


def build_day_detail(
    storage, plan_service, holidays: dict[str, str], date: str, today: str
) -> DayDetail:
    """저장된 출퇴근·(가)계획·계획·메모로 선택 날짜 상세를 구성한다."""
    rec = storage.get(date)
    recog = storage.get_recognition(date)
    vacation = storage.get_vacation(date)
    planned_minutes = plan_service.effective_minutes(date, holidays)
    clocked_out_early = None
    if rec and rec.clock_in and rec.clock_out:
        result = expected_clock_out_at(
            timeutil.from_iso(rec.clock_in), planned_minutes, vacation
        )
        if result is not None:
            clocked_out_early = timeutil.from_iso(rec.clock_out) < result[0]
    return DayDetail(
        date=date,
        kind=_classify(date, today),
        clock_in_hm=timeutil.hhmm(rec.clock_in) if rec and rec.clock_in else None,
        clock_out_hm=(
            timeutil.hhmm(rec.clock_out) if rec and rec.clock_out else None
        ),
        recog_start_hm=minutes_to_hhmm(recog[0]) if recog else None,
        recog_end_hm=minutes_to_hhmm(recog[1]) if recog else None,
        planned_minutes=planned_minutes,
        memo=storage.get_memo(date),
        has_record=rec is not None,
        clocked_out_early=clocked_out_early,
        vacation_minutes=vacation[0] if vacation else 0,
        vacation_start_hm=(
            minutes_to_hhmm(vacation[1])
            if vacation and vacation[1] is not None
            else None
        ),
        vacation_end_hm=(
            minutes_to_hhmm(vacation[2])
            if vacation and vacation[2] is not None
            else None
        ),
        work_seconds=rec.work_seconds if rec else None,
    )
