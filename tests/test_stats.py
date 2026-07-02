from datetime import datetime
from zoneinfo import ZoneInfo

from core.stats import build_month_summary

KST = ZoneInfo("Asia/Seoul")


class FakeStorage:
    def __init__(self, rec=None):
        self._rec = rec

    def get(self, date):
        return self._rec


class FakeAttendance:
    def __init__(self, month_seconds=0, in_progress=None):
        self._month = month_seconds
        self._prog = in_progress

    def month_total_seconds(self, y, m):
        return self._month

    def today_in_progress_seconds(self):
        return self._prog


class FakePlan:
    def __init__(self, planned_month, effective):
        self._pm = planned_month
        self._eff = effective

    def month_planned_minutes(self, y, m, holidays):
        return self._pm

    def effective_minutes(self, date, holidays):
        return self._eff


class Rec:
    def __init__(self, clock_in, clock_out=None):
        self.clock_in = clock_in
        self.clock_out = clock_out


def test_actual_includes_in_progress():
    s = build_month_summary(
        FakeStorage(), FakeAttendance(month_seconds=100, in_progress=50),
        FakePlan(9600, 480), 2026, 7, {}, datetime(2026, 7, 1, 12, tzinfo=KST),
    )
    assert s.actual_seconds == 150
    assert s.planned_minutes == 9600


def test_required_minutes_deducts_weekday_holiday():
    # 2026-08: 말일 31 → floor(31/7*40)=177h. 8/17(월) 평일 공휴일이면 -8h → 169h.
    now = datetime(2026, 8, 3, 12, tzinfo=KST)
    s_no = build_month_summary(
        FakeStorage(), FakeAttendance(), FakePlan(0, 0), 2026, 8, {}, now,
    )
    s_hol = build_month_summary(
        FakeStorage(), FakeAttendance(), FakePlan(0, 0),
        2026, 8, {"2026-08-17": "테스트공휴일"}, now,
    )
    assert s_no.required_minutes == 177 * 60
    assert s_hol.required_minutes == (177 - 8) * 60


def test_progress_ratio_none_when_planned_zero():
    s = build_month_summary(
        FakeStorage(), FakeAttendance(month_seconds=100),
        FakePlan(0, 0), 2026, 7, {}, datetime(2026, 7, 1, 12, tzinfo=KST),
    )
    assert s.progress_ratio is None


def test_expected_clock_out_from_clock_in_and_plan():
    # 출근 09:00, 계획 480분(8h) → 체류 8h30m → 예상 17:30
    rec = Rec("2026-07-01T09:00:00+09:00", None)
    now = datetime(2026, 7, 1, 12, 0, tzinfo=KST)
    s = build_month_summary(
        FakeStorage(rec), FakeAttendance(in_progress=10800),
        FakePlan(9600, 480), 2026, 7, {}, now,
    )
    assert s.expected_clock_out.hour == 17
    assert s.expected_clock_out.minute == 30
    # 남은시간 = 17:30 - 12:00 = 5h30m
    assert s.remaining_seconds == 5 * 3600 + 30 * 60


def test_expected_none_without_clock_in():
    s = build_month_summary(
        FakeStorage(None), FakeAttendance(),
        FakePlan(9600, 480), 2026, 7, {}, datetime(2026, 7, 1, 12, tzinfo=KST),
    )
    assert s.expected_clock_out is None
    assert s.remaining_seconds is None


def test_expected_none_when_plan_zero():
    rec = Rec("2026-07-04T09:00:00+09:00", None)  # 토요일 계획 0
    s = build_month_summary(
        FakeStorage(rec), FakeAttendance(),
        FakePlan(9600, 0), 2026, 7, {}, datetime(2026, 7, 4, 12, tzinfo=KST),
    )
    assert s.expected_clock_out is None
