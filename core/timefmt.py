"""HH:MM ↔ KST ISO8601 변환 (UI 비의존)."""
from __future__ import annotations

import re

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_KST_OFFSET = "+09:00"
_MINUTES_PER_HOUR = 60


def format_break(minutes: int) -> str:
    """임의 휴게 표기. 1h 미만 '45m', 1h 이상 '1h 30m', 정시는 '1h'."""
    if minutes < _MINUTES_PER_HOUR:
        return f"{minutes}m"
    hours, rest = divmod(minutes, _MINUTES_PER_HOUR)
    if rest == 0:
        return f"{hours}h"
    return f"{hours}h {rest}m"


def build_iso(work_date: str, hhmm: str) -> str:
    """work_date(YYYY-MM-DD)와 HH:MM을 KST ISO8601 문자열로."""
    m = _HHMM_RE.match(hhmm.strip())
    if not m:
        raise ValueError(f"시각 형식은 HH:MM 이어야 합니다: {hhmm!r}")
    return f"{work_date}T{m.group(1)}:{m.group(2)}:00{_KST_OFFSET}"
