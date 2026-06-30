from datetime import datetime
from zoneinfo import ZoneInfo

from core.worktime import compute_work_seconds

KST = ZoneInfo("Asia/Seoul")


def _t(h, m=0):
    return datetime(2026, 6, 30, h, m, tzinfo=KST)


def test_under_9h_deducts_30min():
    # 09:00 ~ 17:00 = 8시간 → 30분 차감 = 7시간 30분
    assert compute_work_seconds(_t(9), _t(17)) == 7 * 3600 + 30 * 60


def test_exactly_9h_deducts_60min():
    # 09:00 ~ 18:00 = 9시간 → 60분 차감 = 8시간
    assert compute_work_seconds(_t(9), _t(18)) == 8 * 3600


def test_over_9h_deducts_60min():
    # 09:00 ~ 20:00 = 11시간 → 60분 차감 = 10시간
    assert compute_work_seconds(_t(9), _t(20)) == 10 * 3600


def test_short_span_clamped_to_zero():
    # 09:00 ~ 09:10 = 10분, 30분 차감 → 음수 → 0
    assert compute_work_seconds(_t(9, 0), _t(9, 10)) == 0


def test_non_positive_span_is_zero():
    assert compute_work_seconds(_t(18), _t(9)) == 0
