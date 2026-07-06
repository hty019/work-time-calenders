from core.recognition import (
    RecognitionRange,
    RecognitionService,
    hhmm_to_minutes,
    minutes_to_hhmm,
    validate_range_against_plan,
)


class FakeStorage:
    def __init__(self):
        self._ranges = {}

    def get_recognition(self, d):
        return self._ranges.get(d)

    def set_recognition(self, d, s, e):
        self._ranges[d] = (s, e)

    def clear_recognition(self, d):
        self._ranges.pop(d, None)

    def list_recognition_month(self, y, mo):
        prefix = f"{y:04d}-{mo:02d}-"
        return {d: r for d, r in self._ranges.items() if d.startswith(prefix)}


# --- 변환 헬퍼 ---------------------------------------------------------


def test_hhmm_to_minutes():
    assert hhmm_to_minutes("09:00") == 540
    assert hhmm_to_minutes("15:30") == 930


def test_hhmm_to_minutes_rejects_bad_format():
    import pytest
    with pytest.raises(ValueError):
        hhmm_to_minutes("9시")
    with pytest.raises(ValueError):
        hhmm_to_minutes("25:00")


def test_minutes_to_hhmm():
    assert minutes_to_hhmm(540) == "09:00"
    assert minutes_to_hhmm(930) == "15:30"


# --- RecognitionRange --------------------------------------------------


def test_range_width_and_contains():
    r = RecognitionRange(540, 900)  # 09:00~15:00
    assert r.width_minutes == 360
    assert r.covers(540, 900) is True
    assert r.covers(480, 900) is False   # 08:00 출근 → 이탈
    assert r.covers(540, 960) is False   # 16:00 퇴근 → 이탈


# --- 검증: 계획 대비 범위 폭 -------------------------------------------


def test_validate_blocks_when_range_narrower_than_needed():
    # 계획 480분(8h) → 필요 체류 540분(9h, 휴게 60분 포함)
    # 09:00~17:00(480분)은 부족 → 오류 메시지 반환
    err = validate_range_against_plan(480, RecognitionRange(540, 1020))
    assert err is not None


def test_validate_passes_when_range_wide_enough():
    # 09:00~18:00(540분) ≥ 필요 540분 → 통과
    assert validate_range_against_plan(480, RecognitionRange(540, 1080)) is None


def test_validate_no_break_plan_uses_plan_as_is():
    # 계획 240분(4h 이하, 휴게 없음) → 09:00~13:00(240분) 통과
    assert validate_range_against_plan(240, RecognitionRange(540, 780)) is None


def test_validate_rejects_inverted_or_empty_range():
    assert validate_range_against_plan(240, RecognitionRange(900, 540)) is not None
    assert validate_range_against_plan(240, RecognitionRange(540, 540)) is not None


# --- RecognitionService -------------------------------------------------


def _svc():
    return RecognitionService(FakeStorage())


def test_service_set_get_clear():
    svc = _svc()
    assert svc.get("2026-07-01") is None
    svc.set("2026-07-01", RecognitionRange(540, 900))
    assert svc.get("2026-07-01") == RecognitionRange(540, 900)
    svc.clear("2026-07-01")
    assert svc.get("2026-07-01") is None


def test_service_weekday_bulk_set_and_clear():
    svc = _svc()
    count = svc.set_weekday(2026, 7, 2, RecognitionRange(540, 900))  # 수요일
    assert count == 5
    assert svc.get("2026-07-08") == RecognitionRange(540, 900)
    cleared = svc.set_weekday(2026, 7, 2, None)
    assert cleared == 5
    assert svc.get("2026-07-08") is None


def test_service_weekday_bulk_skips_excluded_dates():
    # 퇴근 완료일 등 제외 날짜는 인정 범위도 변경하지 않는다
    svc = _svc()
    count = svc.set_weekday(
        2026, 7, 2, RecognitionRange(540, 900), exclude_dates={"2026-07-08"}
    )
    assert count == 4
    assert svc.get("2026-07-08") is None
    assert svc.get("2026-07-01") == RecognitionRange(540, 900)
