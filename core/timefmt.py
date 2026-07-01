"""HH:MM ↔ KST ISO8601 변환 (UI 비의존)."""
from __future__ import annotations

import re

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_KST_OFFSET = "+09:00"


def build_iso(work_date: str, hhmm: str) -> str:
    """work_date(YYYY-MM-DD)와 HH:MM을 KST ISO8601 문자열로."""
    m = _HHMM_RE.match(hhmm.strip())
    if not m:
        raise ValueError(f"시각 형식은 HH:MM 이어야 합니다: {hhmm!r}")
    return f"{work_date}T{m.group(1)}:{m.group(2)}:00{_KST_OFFSET}"
