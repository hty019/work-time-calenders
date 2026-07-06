import pytest

from core.vacation import (
    Vacation,
    VacationService,
    build_vacation,
    days_str_to_minutes,
    minutes_to_days_str,
)


class FakeStorage:
    def __init__(self):
        self._vacs = {}
        self._annual = {}

    def get_vacation(self, d):
        return self._vacs.get(d)

    def set_vacation(self, d, minutes, start_min, end_min):
        self._vacs[d] = (minutes, start_min, end_min)

    def clear_vacation(self, d):
        self._vacs.pop(d, None)

    def list_vacation_year(self, y):
        prefix = f"{y:04d}-"
        return {
            d: v for d, v in sorted(self._vacs.items()) if d.startswith(prefix)
        }

    def get_annual_leave(self, y):
        return self._annual.get(y)

    def set_annual_leave(self, y, minutes):
        self._annual[y] = minutes


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


# --- 일수 변환 헬퍼 --------------------------------------------------------


def test_minutes_to_days_str():
    assert minutes_to_days_str(15 * 480) == "15"
    assert minutes_to_days_str(7320) == "15.25"  # 15일 + 2h
    assert minutes_to_days_str(240) == "0.5"
    assert minutes_to_days_str(0) == "0"


def test_days_str_to_minutes():
    assert days_str_to_minutes("15") == 15 * 480
    assert days_str_to_minutes("15.25") == 7320
    assert days_str_to_minutes("0.5") == 240


def test_days_str_to_minutes_rejects_invalid():
    with pytest.raises(ValueError):
        days_str_to_minutes("연차")  # 숫자 아님
    with pytest.raises(ValueError):
        days_str_to_minutes("15.1")  # 0.25일 단위 아님
    with pytest.raises(ValueError):
        days_str_to_minutes("-1")  # 음수


# --- 연간 요약 -------------------------------------------------------------


def test_year_summary_empty_year():
    svc = VacationService(FakeStorage())
    s = svc.year_summary(2026)
    assert s.total_minutes is None  # 총 연차 미설정
    assert s.used_minutes == 0
    assert s.remaining_minutes is None
    assert s.entries == []


def test_year_summary_aggregates_used_and_remaining():
    svc = VacationService(FakeStorage())
    svc.set_annual_total(2026, 15 * 480)
    svc.set("2026-01-05", build_vacation(480))               # 1day
    svc.set("2026-03-10", build_vacation(120, start_min=900))  # 2h
    svc.set("2026-07-01", build_vacation(240, start_min=540))  # 4h
    svc.set("2025-12-31", build_vacation(480))               # 다른 해 → 제외
    s = svc.year_summary(2026)
    assert s.total_minutes == 15 * 480
    assert s.used_minutes == 480 + 120 + 240
    assert s.remaining_minutes == 15 * 480 - 840
    # 날짜 오름차순 (날짜, Vacation) 목록
    assert s.entries == [
        ("2026-01-05", Vacation(480, None, None)),
        ("2026-03-10", Vacation(120, 900, 1020)),
        ("2026-07-01", Vacation(240, 540, 780)),
    ]
