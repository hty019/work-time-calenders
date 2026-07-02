"""KST 기준 시간 유틸리티."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now() -> datetime:
    """KST aware 현재 시각."""
    return datetime.now(KST)


def today_str(dt: datetime | None = None) -> str:
    """KST 기준 YYYY-MM-DD 문자열."""
    target = dt if dt is not None else now()
    return target.astimezone(KST).strftime("%Y-%m-%d")


def to_iso(dt: datetime) -> str:
    return dt.isoformat()


def from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def hhmm(s: str | None) -> str:
    """ISO 시각 문자열에서 'HH:MM' 추출. None/빈 값은 빈 문자열."""
    if not s:
        return ""
    return from_iso(s).strftime("%H:%M")
