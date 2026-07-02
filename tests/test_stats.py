from datetime import datetime
from zoneinfo import ZoneInfo

from core.stats import ProgressLevel, build_month_summary, progress_state

KST = ZoneInfo("Asia/Seoul")


class FakeStorage:
    def __init__(self, rec=None, recog=None):
        self._rec = rec
        self._recog = recog

    def get(self, date):
        return self._rec

    def get_recognition(self, date):
        return self._recog


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
    # 최대 근로 가능시간: 주 52시간 기준, 공휴일 차감 없음
    assert s_no.max_minutes == 230 * 60
    assert s_hol.max_minutes == 230 * 60


def test_progress_ratio_none_when_planned_zero():
    s = build_month_summary(
        FakeStorage(), FakeAttendance(month_seconds=100),
        FakePlan(0, 0), 2026, 7, {}, datetime(2026, 7, 1, 12, tzinfo=KST),
    )
    assert s.progress_ratio is None


def test_expected_clock_out_from_clock_in_and_plan():
    # 출근 09:00, 계획 480분(8h) → 체류 9h(2차 휴게 60분 포함) → 예상 18:00
    rec = Rec("2026-07-01T09:00:00+09:00", None)
    now = datetime(2026, 7, 1, 12, 0, tzinfo=KST)
    s = build_month_summary(
        FakeStorage(rec), FakeAttendance(in_progress=10800),
        FakePlan(9600, 480), 2026, 7, {}, now,
    )
    assert s.expected_clock_out.hour == 18
    assert s.expected_clock_out.minute == 0
    # 남은시간 = 18:00 - 12:00 = 6h
    assert s.remaining_seconds == 6 * 3600


def test_expected_exceeds_recognition_end():
    # (가)계획 08:00~18:00, 출근 09:30, 계획 480분 → 예상 18:30 > 18:00 → 경고
    rec = Rec("2026-07-01T09:30:00+09:00", None)
    now = datetime(2026, 7, 1, 12, 0, tzinfo=KST)
    s = build_month_summary(
        FakeStorage(rec, recog=(480, 1080)), FakeAttendance(in_progress=9000),
        FakePlan(9600, 480), 2026, 7, {}, now,
    )
    assert s.expected_clock_out.hour == 18
    assert s.expected_clock_out.minute == 30
    assert s.expected_exceeds_range is True


def test_expected_within_recognition_end():
    # (가)계획 08:00~19:00, 출근 09:00 → 예상 18:00 ≤ 19:00 → 경고 없음
    rec = Rec("2026-07-01T09:00:00+09:00", None)
    now = datetime(2026, 7, 1, 12, 0, tzinfo=KST)
    s = build_month_summary(
        FakeStorage(rec, recog=(480, 1140)), FakeAttendance(in_progress=10800),
        FakePlan(9600, 480), 2026, 7, {}, now,
    )
    assert s.expected_exceeds_range is False


def test_expected_no_recognition_range_no_warning():
    rec = Rec("2026-07-01T09:00:00+09:00", None)
    now = datetime(2026, 7, 1, 12, 0, tzinfo=KST)
    s = build_month_summary(
        FakeStorage(rec), FakeAttendance(in_progress=10800),
        FakePlan(9600, 480), 2026, 7, {}, now,
    )
    assert s.expected_exceeds_range is False


def test_progress_state_normal_uses_required_as_max():
    # 법정 기준 이내: max=법정 기준, 녹색
    pct, level = progress_state(100 * 3600, 177 * 60, 230 * 60)
    assert level is ProgressLevel.NORMAL
    assert pct == 56  # 100/177

    pct, level = progress_state(177 * 3600, 177 * 60, 230 * 60)
    assert level is ProgressLevel.NORMAL
    assert pct == 100  # 정확히 법정 기준


def test_progress_state_truncates_minutes():
    # 분 단위는 버리고 시간 기준으로 산정: 177h59m → 177h → 아직 법정 이내
    pct, level = progress_state(
        177 * 3600 + 59 * 60, 177 * 60, 230 * 60
    )
    assert level is ProgressLevel.NORMAL
    assert pct == 100
    # 100h30m → 100h 기준 → 56%
    pct, _ = progress_state(100 * 3600 + 30 * 60, 177 * 60, 230 * 60)
    assert pct == 56


def test_progress_state_over_switches_to_max_basis():
    # 법정 기준 초과 ~ +20h 이내: max=최대 가능, 노랑
    pct, level = progress_state(180 * 3600, 177 * 60, 230 * 60)
    assert level is ProgressLevel.OVER
    assert pct == 78  # 180/230

    # 정확히 +20h(197h)까지는 노랑
    pct, level = progress_state(197 * 3600, 177 * 60, 230 * 60)
    assert level is ProgressLevel.OVER


def test_progress_state_critical_after_20h_over():
    # 법정 기준 +20h 초과 ~ 최대 가능 이내: 주황
    pct, level = progress_state(198 * 3600, 177 * 60, 230 * 60)
    assert level is ProgressLevel.CRITICAL
    assert pct == 86  # 198/230

    # 정확히 최대 가능(230h)까지는 주황
    pct, level = progress_state(230 * 3600, 177 * 60, 230 * 60)
    assert level is ProgressLevel.CRITICAL
    assert pct == 100


def test_progress_state_exceeded_over_max():
    # 최대 근로 가능시간 초과: 빨강, 100% 고정
    pct, level = progress_state(231 * 3600, 177 * 60, 230 * 60)
    assert level is ProgressLevel.EXCEEDED
    assert pct == 100


def test_progress_state_zero_required():
    pct, level = progress_state(3600, 0, 230 * 60)
    assert pct == 0
    assert level is ProgressLevel.NORMAL


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
