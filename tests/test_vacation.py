import pytest

from core.vacation import Vacation, VacationService, build_vacation


class FakeStorage:
    def __init__(self):
        self._vacs = {}

    def get_vacation(self, d):
        return self._vacs.get(d)

    def set_vacation(self, d, minutes, start_min, end_min):
        self._vacs[d] = (minutes, start_min, end_min)

    def clear_vacation(self, d):
        self._vacs.pop(d, None)


# --- build_vacation 검증 -------------------------------------------------


def test_build_hourly_vacation_derives_end():
    # 시간제: 종료 = 시작 + 유형(분)
    v = build_vacation(120, start_min=900)  # 2h, 15:00~
    assert v == Vacation(120, 900, 1020)


def test_build_full_day_has_no_times():
    v = build_vacation(480)
    assert v == Vacation(480, None, None)
    # 1day 는 시작 시각을 받지 않는다
    with pytest.raises(ValueError):
        build_vacation(480, start_min=540)


def test_build_rejects_invalid_type():
    with pytest.raises(ValueError):
        build_vacation(180)  # 3h 는 허용 유형 아님


def test_build_hourly_requires_start():
    with pytest.raises(ValueError):
        build_vacation(120)  # 시간제인데 시작 없음


def test_build_rejects_out_of_day_range():
    with pytest.raises(ValueError):
        build_vacation(240, start_min=22 * 60)  # 22:00 + 4h = 26:00 초과
    with pytest.raises(ValueError):
        build_vacation(120, start_min=-10)


# --- VacationService -----------------------------------------------------


def test_service_set_get_clear():
    svc = VacationService(FakeStorage())
    assert svc.get("2026-07-01") is None
    svc.set("2026-07-01", build_vacation(120, start_min=900))
    assert svc.get("2026-07-01") == Vacation(120, 900, 1020)
    svc.clear("2026-07-01")
    assert svc.get("2026-07-01") is None
