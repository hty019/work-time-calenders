"""일자 데이터의 되돌리기 스냅샷과 복사/붙여넣기 버퍼 (Qt 비의존)."""
from __future__ import annotations

from dataclasses import dataclass

from core.recognition import RecognitionRange
from core.storage import Attendance
from core.vacation import Vacation

_MULTI_MIN = 2  # 다중 선택으로 간주하는 최소 일수


@dataclass(frozen=True)
class DayState:
    """한 일자의 되돌리기 가능한 전체 상태 스냅샷.

    equality 로 변경 여부를 판정한다(hash 는 사용하지 않음).
    """

    date: str
    record: Attendance | None
    plan_override: int | None
    recog: RecognitionRange | None
    vacation: Vacation | None
    memo: str | None


@dataclass(frozen=True)
class DayPlanClipboard:
    """복사 버퍼: 실계획(분)과 (가)계획 범위."""

    plan_minutes: int
    recog: RecognitionRange | None


def snapshot_day(storage, plans, recog, vacations, date: str) -> DayState:
    """해당 일자의 전체 상태를 스냅샷한다."""
    return DayState(
        date=date,
        record=storage.get(date),
        plan_override=plans.get_override(date),
        recog=recog.get(date),
        vacation=vacations.get(date),
        memo=storage.get_memo(date),
    )


def restore_day(storage, recog, vacations, state: DayState) -> None:
    """스냅샷대로 해당 일자의 전체 상태를 정확히 복원한다."""
    date = state.date
    if state.record is None:
        storage.delete(date)
    else:
        storage.upsert(state.record)
    if state.plan_override is None:
        storage.clear_plan(date)
    else:
        storage.set_plan(date, state.plan_override)
    if state.recog is None:
        recog.clear(date)
    else:
        recog.set(date, state.recog)
    if state.vacation is None:
        vacations.clear(date)
    else:
        vacations.set(date, state.vacation)
    storage.set_memo(date, state.memo or "")


def paste_targets(selected_date: str, multi_dates: list[str]) -> list[str]:
    """붙여넣기 대상: 다중(2일 이상)이면 전체, 아니면 단일 선택 일자."""
    if len(multi_dates) >= _MULTI_MIN:
        return list(multi_dates)
    return [selected_date]


def apply_clipboard(
    storage, recog, clipboard: DayPlanClipboard, dates: list[str]
) -> None:
    """대상 일자들에 클립보드(실계획+(가)계획)를 그대로 복제한다."""
    for date in dates:
        storage.set_plan(date, clipboard.plan_minutes)
        if clipboard.recog is None:
            recog.clear(date)
        else:
            recog.set(date, clipboard.recog)
