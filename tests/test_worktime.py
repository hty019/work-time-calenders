from datetime import datetime
from zoneinfo import ZoneInfo

from core.worktime import compute_work_seconds

KST = ZoneInfo("Asia/Seoul")


def _t(h, m=0):
    return datetime(2026, 6, 30, h, m, tzinfo=KST)


def test_under_9h_deducts_30min():
    # 09:00 ~ 17:00 = 8시간 → 1차 휴게 30분 차감 = 7시간 30분
    assert compute_work_seconds(_t(9), _t(17)) == 7 * 3600 + 30 * 60


def test_exactly_9h_deducts_60min():
    # 09:00 ~ 18:00 = 9시간 → 총 60분 차감 = 8시간
    assert compute_work_seconds(_t(9), _t(18)) == 8 * 3600


def test_over_9h_deducts_60min():
    # 09:00 ~ 20:00 = 11시간 → 총 60분 차감 = 10시간
    assert compute_work_seconds(_t(9), _t(20)) == 10 * 3600


def test_first_four_hours_count_fully():
    # 09:00 ~ 12:59 = 3시간 59분 → 정상 누적 (차감 없음)
    assert compute_work_seconds(_t(9, 0), _t(12, 59)) == 3 * 3600 + 59 * 60


def test_first_break_freezes_at_four_hours():
    # 4h ~ 4h30m 구간은 4시간 00분으로 고정
    assert compute_work_seconds(_t(9), _t(13, 0)) == 4 * 3600       # 4h00m
    assert compute_work_seconds(_t(9), _t(13, 15)) == 4 * 3600      # 4h15m
    assert compute_work_seconds(_t(9), _t(13, 30)) == 4 * 3600      # 4h30m
    # 4h31m 부터 4시간 01분으로 재개
    assert compute_work_seconds(_t(9), _t(13, 31)) == 4 * 3600 + 60


def test_second_break_freezes_at_eight_hours():
    # 누적 8h 도달 = raw 8h30m → 8h30m~9h 동안 8시간 00분 고정
    assert compute_work_seconds(_t(9), _t(17, 30)) == 8 * 3600      # raw 8h30m
    assert compute_work_seconds(_t(9), _t(17, 59)) == 8 * 3600      # raw 8h59m
    # raw 9h01m 부터 8시간 01분으로 재개
    assert compute_work_seconds(_t(9), _t(18, 1)) == 8 * 3600 + 60


def test_short_span_counts_fully():
    # 09:00 ~ 09:10 = 10분 → 첫 4시간 이내라 그대로 누적
    assert compute_work_seconds(_t(9, 0), _t(9, 10)) == 10 * 60


def test_non_positive_span_is_zero():
    assert compute_work_seconds(_t(18), _t(9)) == 0
