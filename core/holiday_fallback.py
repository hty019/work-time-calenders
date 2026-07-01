"""API 키 없이도 표시할 수 있는 양력 고정 법정공휴일 기본값.

음력 기반 공휴일(설날·추석·부처님오신날)과 대체·임시공휴일은 해마다 날짜가
달라져 공공데이터포털 API로만 정확히 채울 수 있다. 이 모듈은 매년 날짜가
양력으로 고정된 법정공휴일만 제공하여, API 키가 없거나 조회에 실패해도
최소한의 공휴일은 빨간색으로 표시되도록 한다.
"""
from __future__ import annotations

# (월, 일): 공휴일명 — 매년 양력으로 고정된 법정공휴일
_FIXED_SOLAR_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "신정",
    (3, 1): "삼일절",
    (5, 5): "어린이날",
    (6, 6): "현충일",
    (8, 15): "광복절",
    (10, 3): "개천절",
    (10, 9): "한글날",
    (12, 25): "기독탄신일",
}


def fixed_holidays(year: int, month: int) -> dict[str, str]:
    """해당 연·월의 양력 고정 공휴일을 {YYYY-MM-DD: 이름}으로 반환한다."""
    return {
        f"{year:04d}-{month:02d}-{day:02d}": name
        for (m, day), name in _FIXED_SOLAR_HOLIDAYS.items()
        if m == month
    }
