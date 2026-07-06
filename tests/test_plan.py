from core.plan import PlanService, weekday_dates


class FakeStorage:
    def __init__(self):
        self._plans = {}

    def get_plan(self, d):
        return self._plans.get(d)

    def set_plan(self, d, m):
        self._plans[d] = m

    def clear_plan(self, d):
        self._plans.pop(d, None)

    def list_plan_month(self, y, mo):
        prefix = f"{y:04d}-{mo:02d}-"
        return {d: m for d, m in self._plans.items() if d.startswith(prefix)}


def _svc():
    return PlanService(FakeStorage(), default_minutes_getter=lambda: 480)


def test_weekday_uses_default():
    # 2026-07-01 은 수요일 → 기본 480
    assert _svc().effective_minutes("2026-07-01", {}) == 480


def test_weekend_is_zero():
    # 2026-07-04 토, 2026-07-05 일
    svc = _svc()
    assert svc.effective_minutes("2026-07-04", {}) == 0
    assert svc.effective_minutes("2026-07-05", {}) == 0


def test_holiday_is_zero():
    # 평일이지만 공휴일이면 0
    svc = _svc()
    assert svc.effective_minutes("2026-07-01", {"2026-07-01": "임시공휴일"}) == 0


def test_override_wins_over_everything():
    svc = _svc()
    svc.set_plan("2026-07-04", 240)  # 토요일에도 오버라이드 적용
    assert svc.effective_minutes("2026-07-04", {}) == 240
    svc.set_plan("2026-07-01", 0)  # 평일 0시간 오버라이드(휴가)
    assert svc.effective_minutes("2026-07-01", {}) == 0


def test_month_planned_sums_effective():
    # 2026-07: 평일 수 23일(공휴일 없음 가정) × 480
    svc = _svc()
    total = svc.month_planned_minutes(2026, 7, {})
    assert total == 23 * 480


def test_month_planned_applies_override_and_holiday():
    svc = _svc()
    svc.set_plan("2026-07-01", 240)  # 평일 하루 480→240
    holidays = {"2026-07-17": "제헌절가정"}  # 평일 하루 480→0
    total = svc.month_planned_minutes(2026, 7, holidays)
    # 기준 23*480 에서 (480-240) 및 480 차감
    assert total == 23 * 480 - 240 - 480


def test_weekday_dates_lists_all_in_month():
    # 2026-07 의 수요일(월=0..일=6 에서 2): 1,8,15,22,29
    assert weekday_dates(2026, 7, 2) == [
        "2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29",
    ]


def test_set_weekday_plan_applies_to_all():
    svc = _svc()
    count = svc.set_weekday_plan(2026, 7, 2, 300)  # 수요일 전체 300분
    assert count == 5
    for d in weekday_dates(2026, 7, 2):
        assert svc.effective_minutes(d, {}) == 300


def test_set_weekday_plan_none_clears_override():
    svc = _svc()
    svc.set_weekday_plan(2026, 7, 2, 300)
    cleared = svc.set_weekday_plan(2026, 7, 2, None)  # 오버라이드 해제
    assert cleared == 5
    # 해제 후 평일 기본값 480 복귀
    assert svc.effective_minutes("2026-07-01", {}) == 480


def test_set_weekday_plan_skips_excluded_dates():
    # 퇴근 완료일 등 제외 날짜는 건드리지 않고, 처리 건수에서도 뺀다
    svc = _svc()
    count = svc.set_weekday_plan(2026, 7, 2, 300, exclude_dates={"2026-07-08"})
    assert count == 4
    assert svc.effective_minutes("2026-07-08", {}) == 480  # 제외일은 기본값 유지
    assert svc.effective_minutes("2026-07-01", {}) == 300


def test_set_weekday_plan_clear_skips_excluded_dates():
    svc = _svc()
    svc.set_weekday_plan(2026, 7, 2, 300)
    cleared = svc.set_weekday_plan(2026, 7, 2, None, exclude_dates={"2026-07-08"})
    assert cleared == 4
    # 제외일의 기존 오버라이드는 해제되지 않는다
    assert svc.effective_minutes("2026-07-08", {}) == 300
    assert svc.effective_minutes("2026-07-01", {}) == 480
