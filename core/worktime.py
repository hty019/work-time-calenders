"""근무 시간 계산 (휴게시간 임계-정지 차감).

일괄 차감이 아니라, 누적 근무가 임계에 도달하면 그 지점에서 정해진 시간
동안 카운트를 멈추는 방식이다. 실제 경과시간(raw)에 대한 누적 근무시간은
다음과 같이 연속·단조 증가한다.

    raw 0 ~ 4h         : raw 그대로 정상 누적
    raw 4h ~ 5h        : 4h 고정 (1차 휴게 60분)
    raw 5h ~ 13h       : raw - 60m   (누적 8h 도달 시 휴게 없음)
    raw 13h ~ 13h30m   : 12h 고정 (2차 휴게 30분)  ← 누적 12h 도달 시점에 시작
    raw 13h30m ~       : raw - 90m

정규 근무 9h 체류 → 8h 는 기존과 동일하다.
휴게는 최대 2회(총 90분)로 고정한다.
"""
from __future__ import annotations

from datetime import datetime

FOUR_HOURS_SECONDS = 4 * 3600
TWELVE_HOURS_SECONDS = 12 * 3600
FIRST_BREAK_SECONDS = 60 * 60
SECOND_BREAK_SECONDS = 30 * 60
TOTAL_BREAK_SECONDS = FIRST_BREAK_SECONDS + SECOND_BREAK_SECONDS


def net_seconds_for_raw(raw_seconds: int) -> int:
    """체류(raw) 초에서 휴게 임계-정지 모델로 순근무 초를 산출."""
    raw = raw_seconds
    if raw <= 0:
        return 0
    if raw < FOUR_HOURS_SECONDS:                               # 0 ~ 4h
        return raw
    if raw < FOUR_HOURS_SECONDS + FIRST_BREAK_SECONDS:         # 1차 휴게 [4h, 5h)
        return FOUR_HOURS_SECONDS
    if raw < TWELVE_HOURS_SECONDS + FIRST_BREAK_SECONDS:       # 5h ~ 13h
        return raw - FIRST_BREAK_SECONDS
    if raw < TWELVE_HOURS_SECONDS + TOTAL_BREAK_SECONDS:       # 2차 휴게 [13h, 13h30m)
        return TWELVE_HOURS_SECONDS
    return raw - TOTAL_BREAK_SECONDS                           # 13h30m ~


def compute_work_seconds(clock_in: datetime, clock_out: datetime) -> int:
    """출근~퇴근 raw 구간에서 휴게시간을 차감한 근무 초."""
    return net_seconds_for_raw(int((clock_out - clock_in).total_seconds()))


def effective_work_seconds(
    clock_in: datetime,
    clock_out: datetime,
    vac_start_min: int | None = None,
    vac_end_min: int | None = None,
) -> int:
    """휴가 구간과 겹치는 체류를 제외한 근무 초 (이중 집계 방지).

    근로 구간에서 휴가 구간(자정 기준 분)과 겹치는 시간을 raw 에서 빼고
    휴게 임계-정지 모델을 적용한다. 휴가 구간이 없으면 기존 계산과 동일.
    """
    raw = int((clock_out - clock_in).total_seconds())
    if raw <= 0:
        return 0
    if vac_start_min is None or vac_end_min is None:
        return net_seconds_for_raw(raw)
    in_seconds = (
        clock_in.hour * 3600 + clock_in.minute * 60 + clock_in.second
    )
    out_seconds = in_seconds + raw
    overlap = max(
        0, min(out_seconds, vac_end_min * 60) - max(in_seconds, vac_start_min * 60)
    )
    return net_seconds_for_raw(raw - overlap)


def raw_seconds_for_net(net_seconds: int) -> int:
    """목표 순근무 초에 도달하는 최소 체류 초. compute_work_seconds 의 역함수.

    net ≤ 4h         : 휴게 없음 → raw = net
    4h < net < 12h   : 1차 휴게 60분 포함 → raw = net + 60m
    net ≥ 12h        : 2차 휴게까지 90분 포함 → raw = net + 90m

    12h 이상 계획은 2차 휴게(총 90분)까지 포함해 산정한다.
    예상 퇴근시각은 clock_in + net + 해당 휴게시간.
    """
    if net_seconds <= 0:
        return 0
    if net_seconds <= FOUR_HOURS_SECONDS:
        return net_seconds
    if net_seconds < TWELVE_HOURS_SECONDS:
        return net_seconds + FIRST_BREAK_SECONDS
    return net_seconds + TOTAL_BREAK_SECONDS
