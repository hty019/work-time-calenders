"""근무 시간 계산 (휴게시간 임계-정지 차감).

일괄 차감이 아니라, 누적 근무가 임계에 도달하면 그 지점에서 30분 동안
카운트를 멈추는 방식이다. 실제 경과시간(raw)에 대한 누적 근무시간은 다음과
같이 연속·단조 증가한다.

    raw 0 ~ 4h         : raw 그대로 정상 누적
    raw 4h ~ 4h30m     : 4h 고정 (1차 휴게)
    raw 4h30m ~ 8h30m  : raw - 30m
    raw 8h30m ~ 9h     : 8h 고정 (2차 휴게)  ← 누적 8h 도달 시점에 시작
    raw 9h ~ 13h       : raw - 60m
    raw 13h ~ 13h30m   : 12h 고정 (3차 휴게)  ← 누적 12h 도달 시점에 시작
    raw 13h30m ~       : raw - 90m

정규 근무의 최종값은 기존과 동일하다 (9h→8h, 8h→7h30m).
휴게는 최대 3회(총 90분)로 고정한다.
"""
from __future__ import annotations

from datetime import datetime

FOUR_HOURS_SECONDS = 4 * 3600
EIGHT_HOURS_SECONDS = 8 * 3600
TWELVE_HOURS_SECONDS = 12 * 3600
BREAK_SECONDS = 30 * 60


def compute_work_seconds(clock_in: datetime, clock_out: datetime) -> int:
    """출근~퇴근 raw 구간에서 휴게시간을 차감한 근무 초."""
    raw = int((clock_out - clock_in).total_seconds())
    if raw <= 0:
        return 0
    if raw < FOUR_HOURS_SECONDS:                       # 0 ~ 4h
        return raw
    if raw < FOUR_HOURS_SECONDS + BREAK_SECONDS:       # 1차 휴게 [4h, 4h30m)
        return FOUR_HOURS_SECONDS
    if raw < EIGHT_HOURS_SECONDS + BREAK_SECONDS:      # 4h30m ~ 8h30m
        return raw - BREAK_SECONDS
    if raw < EIGHT_HOURS_SECONDS + 2 * BREAK_SECONDS:  # 2차 휴게 [8h30m, 9h)
        return EIGHT_HOURS_SECONDS
    if raw < TWELVE_HOURS_SECONDS + 2 * BREAK_SECONDS:  # 9h ~ 13h
        return raw - 2 * BREAK_SECONDS
    if raw < TWELVE_HOURS_SECONDS + 3 * BREAK_SECONDS:  # 3차 휴게 [13h, 13h30m)
        return TWELVE_HOURS_SECONDS
    return raw - 3 * BREAK_SECONDS                      # 13h30m ~


def raw_seconds_for_net(net_seconds: int) -> int:
    """목표 순근무 초에 도달하는 최소 체류 초. compute_work_seconds 의 역함수.

    net ≤ 4h         : 휴게 없음 → raw = net
    4h < net < 8h    : 1차 휴게 30분 포함 → raw = net + 30m
    8h ≤ net < 12h   : 2차 휴게까지 60분 포함 → raw = net + 60m
    net ≥ 12h        : 3차 휴게까지 90분 포함 → raw = net + 90m

    8h 정각 계획은 2차 휴게(총 60분)까지, 12h 이상 계획은 3차 휴게(총 90분)까지
    포함해 산정한다. 예상 퇴근시각은 clock_in + net + 해당 휴게시간.
    """
    if net_seconds <= 0:
        return 0
    if net_seconds <= FOUR_HOURS_SECONDS:
        return net_seconds
    if net_seconds < EIGHT_HOURS_SECONDS:
        return net_seconds + BREAK_SECONDS
    if net_seconds < TWELVE_HOURS_SECONDS:
        return net_seconds + 2 * BREAK_SECONDS
    return net_seconds + 3 * BREAK_SECONDS
