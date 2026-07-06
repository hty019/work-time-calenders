from core.day_detail import DayDetail, build_day_detail


class FakeStorage:
    def __init__(self, rec=None, recog=None, vacation=None, memo=None):
        self._rec = rec
        self._recog = recog
        self._vacation = vacation
        self._memo = memo

    def get(self, date):
        return self._rec

    def get_recognition(self, date):
        return self._recog

    def get_vacation(self, date):
        return self._vacation

    def get_memo(self, date):
        return self._memo


class FakePlan:
    def __init__(self, effective):
        self._eff = effective

    def effective_minutes(self, date, holidays):
        return self._eff


class Rec:
    def __init__(self, clock_in, clock_out=None):
        self.clock_in = clock_in
        self.clock_out = clock_out


TODAY = "2026-07-06"


def _build(date, storage=None, plan_minutes=480):
    return build_day_detail(
        storage or FakeStorage(), FakePlan(plan_minutes), {}, date, TODAY
    )


def test_kind_classification():
    assert _build("2026-07-01").kind == "past"
    assert _build("2026-07-06").kind == "today"
    assert _build("2026-07-10").kind == "future"


def test_past_day_fields_from_record():
    storage = FakeStorage(
        rec=Rec("2026-07-01T09:12:00+09:00", "2026-07-01T18:00:00+09:00"),
        recog=(480, 1310),  # 08:00~21:50
        memo="주간 회의",
    )
    d = _build("2026-07-01", storage)
    assert d.has_record is True
    assert d.clock_in_hm == "09:12"
    assert d.clock_out_hm == "18:00"
    assert d.recog_start_hm == "08:00"
    assert d.recog_end_hm == "21:50"
    assert d.planned_minutes == 480
    assert d.memo == "주간 회의"


def test_no_record_gives_none_fields():
    d = _build("2026-07-01")
    assert d.has_record is False
    assert d.clock_in_hm is None
    assert d.clock_out_hm is None
    assert d.recog_start_hm is None
    assert d.memo is None
    assert d.clocked_out_early is None


def test_past_clocked_out_early():
    # 계획 8h → 체류 8h30m 필요. 09:00 출근, 16:00 퇴근 → 예상(17:30) 전 조기
    storage = FakeStorage(
        rec=Rec("2026-07-01T09:00:00+09:00", "2026-07-01T16:00:00+09:00")
    )
    assert _build("2026-07-01", storage).clocked_out_early is True


def test_past_clocked_out_normal():
    # 09:00 출근, 18:00 퇴근 → 예상(17:30) 이후 정상
    storage = FakeStorage(
        rec=Rec("2026-07-01T09:00:00+09:00", "2026-07-01T18:00:00+09:00")
    )
    assert _build("2026-07-01", storage).clocked_out_early is False


def test_early_none_when_no_plan_or_no_clock_out():
    # 계획 0 → 예상 퇴근 없음 → 판정 불가
    storage = FakeStorage(
        rec=Rec("2026-07-01T09:00:00+09:00", "2026-07-01T18:00:00+09:00")
    )
    assert _build("2026-07-01", storage, plan_minutes=0).clocked_out_early is None
    # 퇴근 미기록 → 판정 불가
    storage2 = FakeStorage(rec=Rec("2026-07-01T09:00:00+09:00"))
    assert _build("2026-07-01", storage2).clocked_out_early is None
