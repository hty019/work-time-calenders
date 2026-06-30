"""출퇴근 기록 및 근무시간 비즈니스 로직."""
from __future__ import annotations

from typing import Callable

from core import timeutil
from core.storage import Attendance, Storage
from core.worktime import compute_work_seconds


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

    def record_clock_out(self) -> Attendance:
        now = self._clock()
        date = timeutil.today_str(now)
        existing = self._storage.get(date)
        if existing is None:
            raise ValueError(f"출근 기록이 없습니다: {date}")
        clock_in = timeutil.from_iso(existing.clock_in)
        seconds = compute_work_seconds(clock_in, now)
        rec = Attendance(date, existing.clock_in, timeutil.to_iso(now), seconds)
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
        seconds = compute_work_seconds(clock_in, clock_out)
        rec = Attendance(work_date, clock_in_iso, clock_out_iso, seconds)
        self._storage.upsert(rec)
        return rec

    def month_total_seconds(self, year: int, month: int) -> int:
        rows = self._storage.list_month(year, month)
        return sum(r.work_seconds for r in rows if r.work_seconds is not None)
