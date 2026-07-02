"""출퇴근 기록 및 근무시간 비즈니스 로직."""
from __future__ import annotations

from enum import Enum
from typing import Callable

from core import timeutil
from core.storage import Attendance, Storage
from core.vacation import FULL_DAY_MINUTES
from core.worktime import effective_work_seconds


class WorkStatus(Enum):
    """오늘의 근무 상태. 값은 위젯에 그대로 노출되는 표시 문구."""

    NOT_CLOCKED_IN = "미출근"
    WORKING = "근무중"
    CLOCKED_OUT = "퇴근"


class AttendanceService:
    def __init__(self, storage: Storage, clock: Callable[[], object] = timeutil.now) -> None:
        self._storage = storage
        self._clock = clock

    def record_clock_in(self) -> Attendance:
        now = self._clock()
        date = timeutil.today_str(now)
        existing = self._storage.get(date)
        if existing is not None:
            return existing
        rec = Attendance(date, timeutil.to_iso(now), None, None)
        self._storage.upsert(rec)
        return rec

    def _work_seconds(self, date: str, clock_in, clock_out) -> int:
        """휴가를 반영한 근무 초 (모든 쓰기 경로 공통).

        1day 휴가일은 출퇴근을 무시하고 근로 0 (인정은 휴가 8h 로 고정).
        시간제 휴가는 겹치는 구간을 제외한다.
        """
        row = self._storage.get_vacation(date)
        if row is None:
            return effective_work_seconds(clock_in, clock_out)
        minutes, start_min, end_min = row
        if minutes >= FULL_DAY_MINUTES:
            return 0
        return effective_work_seconds(clock_in, clock_out, start_min, end_min)

    def record_clock_out(self) -> Attendance:
        now = self._clock()
        date = timeutil.today_str(now)
        existing = self._storage.get(date)
        if existing is None:
            raise ValueError(f"출근 기록이 없습니다: {date}")
        clock_in = timeutil.from_iso(existing.clock_in)
        seconds = self._work_seconds(date, clock_in, now)
        rec = Attendance(date, existing.clock_in, timeutil.to_iso(now), seconds)
        self._storage.upsert(rec)
        return rec

    def cancel_clock_out(self) -> Attendance | None:
        """오늘의 퇴근 기록을 제거해 다시 진행 중(미퇴근) 상태로 되돌린다.

        퇴근 기록이 없으면 아무것도 하지 않고 None을 반환한다.
        """
        now = self._clock()
        date = timeutil.today_str(now)
        existing = self._storage.get(date)
        if existing is None or existing.clock_out is None:
            return None
        rec = Attendance(date, existing.clock_in, None, None)
        self._storage.upsert(rec)
        return rec

    def edit(
        self, work_date: str, clock_in_iso: str, clock_out_iso: str | None
    ) -> Attendance:
        if not clock_out_iso:
            rec = Attendance(work_date, clock_in_iso, None, None)
            self._storage.upsert(rec)
            return rec
        clock_in = timeutil.from_iso(clock_in_iso)
        clock_out = timeutil.from_iso(clock_out_iso)
        if clock_out <= clock_in:
            raise ValueError("퇴근 시각은 출근 시각보다 이후여야 합니다.")
        seconds = self._work_seconds(work_date, clock_in, clock_out)
        rec = Attendance(work_date, clock_in_iso, clock_out_iso, seconds)
        self._storage.upsert(rec)
        return rec

    def recompute_work(self, work_date: str) -> Attendance | None:
        """휴가 변경 등으로 저장된 근무초를 현재 규칙으로 재계산한다.

        퇴근 확정 기록이 없으면 아무것도 하지 않고 None 을 반환한다.
        """
        rec = self._storage.get(work_date)
        if rec is None or rec.clock_out is None:
            return None
        seconds = self._work_seconds(
            work_date,
            timeutil.from_iso(rec.clock_in),
            timeutil.from_iso(rec.clock_out),
        )
        updated = Attendance(work_date, rec.clock_in, rec.clock_out, seconds)
        self._storage.upsert(updated)
        return updated

    def month_total_seconds(self, year: int, month: int) -> int:
        rows = self._storage.list_month(year, month)
        return sum(r.work_seconds for r in rows if r.work_seconds is not None)

    def today_status(self) -> WorkStatus:
        """오늘 기록으로부터 근무 상태를 판정한다.

        기록 없음→미출근, 퇴근 시각 있음→퇴근, 그 외→근무중.
        """
        now = self._clock()
        date = timeutil.today_str(now)
        rec = self._storage.get(date)
        if rec is None:
            return WorkStatus.NOT_CLOCKED_IN
        if rec.clock_out is not None:
            return WorkStatus.CLOCKED_OUT
        return WorkStatus.WORKING

    def today_in_progress_seconds(self) -> int | None:
        """오늘 출근했으나 아직 퇴근하지 않았다면 지금까지의 근무 초.

        퇴근 완료·미출근 등 진행 중이 아닌 경우 None을 반환한다.
        점심 차감 등 계산 로직은 퇴근 확정값과 동일하게 적용된다.
        """
        now = self._clock()
        date = timeutil.today_str(now)
        rec = self._storage.get(date)
        if rec is None or rec.clock_out is not None:
            return None
        clock_in = timeutil.from_iso(rec.clock_in)
        return self._work_seconds(date, clock_in, now)
