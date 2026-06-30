"""근무 시간 계산 (점심 자동 차감)."""
from __future__ import annotations

from datetime import datetime

LUNCH_THRESHOLD_SECONDS = 9 * 3600
LUNCH_DEDUCT_SHORT_SECONDS = 30 * 60
LUNCH_DEDUCT_LONG_SECONDS = 60 * 60


def compute_work_seconds(clock_in: datetime, clock_out: datetime) -> int:
    """출근~퇴근 raw 구간에서 점심시간을 차감한 근무 초.

    raw < 9시간 → 30분 차감, raw >= 9시간 → 60분 차감, 음수는 0으로 보정.
    """
    raw = int((clock_out - clock_in).total_seconds())
    if raw <= 0:
        return 0
    deduct = (
        LUNCH_DEDUCT_LONG_SECONDS
        if raw >= LUNCH_THRESHOLD_SECONDS
        else LUNCH_DEDUCT_SHORT_SECONDS
    )
    return max(0, raw - deduct)
