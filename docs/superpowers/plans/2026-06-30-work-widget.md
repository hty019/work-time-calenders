# 근무시간 데스크탑 위젯 (work-widget) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** macOS 부팅 시 자동 실행되어 출근 시간을 자동 기록하고, '퇴근' 버튼/일자 클릭 수정으로 근무시간을 관리하며, 한국 공휴일과 월간 누적 근무시간을 바탕화면 달력 위젯으로 보여주는 프로그램을 만든다.

**Architecture:** 순수 로직(core)과 UI(widget)를 분리한다. core는 SQLite 저장소(`storage`), 출퇴근/근무시간 계산 로직(`attendance`), 공휴일 API 클라이언트(`holidays`)로 구성하며 UI 없이 단위 테스트한다. widget은 tkinter로 테두리 없는 always-on-top 창과 달력/수정 다이얼로그를 그린다. `main.py`가 둘을 조립하고 LaunchAgent로 자동 시작한다.

**Tech Stack:** Python 3.9+, tkinter(표준 라이브러리), sqlite3(표준 라이브러리), zoneinfo(표준 라이브러리), requests, pytest, macOS LaunchAgent.

## Global Constraints

- 시간대: 모든 날짜/시각 경계 계산은 KST(`zoneinfo.ZoneInfo("Asia/Seoul")`) 기준.
- 외부 의존성: `requests` 하나로 제한. 나머지는 표준 라이브러리만 사용.
- 점심 차감 상수(정확한 값, 코드에 매직넘버 금지):
  - `LUNCH_THRESHOLD_SECONDS = 9 * 3600`
  - `LUNCH_DEDUCT_SHORT_SECONDS = 30 * 60`
  - `LUNCH_DEDUCT_LONG_SECONDS = 60 * 60`
- 데이터 디렉터리: `~/.work-widget/` (DB: `attendance.db`, 공휴일 캐시: `holidays_cache.json`, 설정: `config.json`).
- 시크릿 금지: 공공데이터포털 서비스 키는 코드에 하드코딩하지 않고 `config.json` 또는 환경변수에서 로드. `config.json`은 git에 커밋 금지.
- DB 하루 1행: `attendance(work_date PK, clock_in, clock_out, work_seconds)`.
- 커밋 메시지 prefix 사용: ✨(기능), 🐛(버그), 🔧(설정), 📝(문서), ♻️(리팩토링), 🔥(삭제). 한글로 작성.
- 응답/커밋 한글.

---

## File Structure

```
work-widget/
├── main.py                # 앱 진입점, core+widget 조립, 생명주기
├── config.py              # 데이터 경로, 설정/서비스키/창위치 로드·저장
├── core/
│   ├── __init__.py
│   ├── timeutil.py        # KST now / 날짜 문자열 / ISO 파싱 헬퍼
│   ├── worktime.py        # 점심 차감 포함 work_seconds 순수 계산
│   ├── storage.py         # SQLite 접근 (attendance CRUD)
│   ├── attendance.py      # 출근 기록/퇴근/수동 수정/월간 합계 비즈니스 로직
│   └── holidays.py        # 공공데이터포털 특일정보 API + 캐시
├── widget/
│   ├── __init__.py
│   ├── window.py          # 테두리 없는 always-on-top 드래그 창
│   ├── calendar_view.py   # 월 달력 렌더 + 날짜 클릭 콜백
│   └── edit_dialog.py     # 출근/퇴근 시각 수정 다이얼로그
├── install_autostart.py   # LaunchAgent plist 설치/제거
├── requirements.txt
├── .gitignore             # (이미 존재)
└── tests/
    ├── __init__.py
    ├── test_worktime.py
    ├── test_storage.py
    ├── test_attendance.py
    └── test_holidays.py
```

각 파일은 단일 책임을 가지며, `storage`/`holidays`는 `attendance`가 주입받아 테스트 시 대체 가능하게 둔다.

---

### Task 1: 프로젝트 스캐폴딩 & 시간 유틸리티

**Files:**
- Create: `requirements.txt`
- Create: `core/__init__.py` (빈 파일)
- Create: `tests/__init__.py` (빈 파일)
- Create: `core/timeutil.py`
- Test: `tests/test_timeutil.py` (worktime 테스트는 Task 2에서 별도 생성)

**Interfaces:**
- Consumes: 없음
- Produces:
  - `core/timeutil.py`:
    - `KST` (= `zoneinfo.ZoneInfo("Asia/Seoul")`)
    - `now() -> datetime` — KST aware 현재 시각
    - `today_str(dt: datetime | None = None) -> str` — `YYYY-MM-DD` (KST)
    - `to_iso(dt: datetime) -> str` — ISO8601 문자열
    - `from_iso(s: str) -> datetime` — ISO8601 파싱 (aware)

- [ ] **Step 1: requirements.txt 작성**

```
requests>=2.31,<3
pytest>=8,<9
```

- [ ] **Step 2: 빈 패키지 파일 생성**

`core/__init__.py`, `tests/__init__.py` 를 빈 내용으로 생성.

- [ ] **Step 3: 가상환경 및 의존성 설치**

Run:
```bash
cd ~/work-widget && python3 -m venv venv && ./venv/bin/pip install -q -r requirements.txt && echo OK
```
Expected: `OK` 출력 (오류 없음)

- [ ] **Step 4: timeutil 실패 테스트 작성**

`tests/test_timeutil.py`:
```python
from datetime import datetime
from core import timeutil


def test_now_is_kst_aware():
    dt = timeutil.now()
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 9 * 3600


def test_today_str_format():
    dt = datetime(2026, 6, 30, 8, 5, tzinfo=timeutil.KST)
    assert timeutil.today_str(dt) == "2026-06-30"


def test_iso_roundtrip():
    dt = datetime(2026, 6, 30, 9, 0, tzinfo=timeutil.KST)
    assert timeutil.from_iso(timeutil.to_iso(dt)) == dt
```

- [ ] **Step 5: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_timeutil.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.timeutil'` 또는 attribute 없음)

- [ ] **Step 6: timeutil 구현**

`core/timeutil.py`:
```python
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
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_timeutil.py -v`
Expected: PASS (3 passed)

- [ ] **Step 8: 커밋**

```bash
cd ~/work-widget && git add requirements.txt core/ tests/ && git commit -m "🔧 프로젝트 스캐폴딩 및 KST 시간 유틸리티 추가"
```

---

### Task 2: 근무시간 순수 계산 (점심 차감)

**Files:**
- Create: `core/worktime.py`
- Test: `tests/test_worktime.py`

**Interfaces:**
- Consumes: 없음 (순수 함수)
- Produces:
  - `core/worktime.py`:
    - 상수 `LUNCH_THRESHOLD_SECONDS`, `LUNCH_DEDUCT_SHORT_SECONDS`, `LUNCH_DEDUCT_LONG_SECONDS`
    - `compute_work_seconds(clock_in: datetime, clock_out: datetime) -> int`
      — raw = clock_out - clock_in 초. raw<9h이면 30분, raw>=9h이면 60분 차감. `max(0, raw-차감)`. raw<=0이면 0.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_worktime.py`:
```python
from datetime import datetime, timedelta
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_worktime.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.worktime'`)

- [ ] **Step 3: worktime 구현**

`core/worktime.py`:
```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_worktime.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
cd ~/work-widget && git add core/worktime.py tests/test_worktime.py && git commit -m "✨ 점심 차감 포함 근무시간 계산 로직 추가"
```

---

### Task 3: SQLite 저장소

**Files:**
- Create: `core/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `core/storage.py`:
    - `@dataclass Attendance`: `work_date: str`, `clock_in: str`, `clock_out: str | None`, `work_seconds: int | None`
    - `class Storage`:
      - `__init__(self, db_path: str)` — 디렉터리 생성 + 테이블 생성
      - `get(self, work_date: str) -> Attendance | None`
      - `upsert(self, rec: Attendance) -> None`
      - `list_month(self, year: int, month: int) -> list[Attendance]` — 해당 월 전체
      - `close(self) -> None`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_storage.py`:
```python
from core.storage import Storage, Attendance


def make_storage(tmp_path):
    return Storage(str(tmp_path / "att.db"))


def test_get_missing_returns_none(tmp_path):
    s = make_storage(tmp_path)
    assert s.get("2026-06-30") is None


def test_upsert_then_get(tmp_path):
    s = make_storage(tmp_path)
    rec = Attendance("2026-06-30", "2026-06-30T09:00:00+09:00", None, None)
    s.upsert(rec)
    got = s.get("2026-06-30")
    assert got == rec


def test_upsert_overwrites_same_date(tmp_path):
    s = make_storage(tmp_path)
    s.upsert(Attendance("2026-06-30", "2026-06-30T09:00:00+09:00", None, None))
    s.upsert(
        Attendance(
            "2026-06-30",
            "2026-06-30T09:00:00+09:00",
            "2026-06-30T18:00:00+09:00",
            8 * 3600,
        )
    )
    got = s.get("2026-06-30")
    assert got.clock_out == "2026-06-30T18:00:00+09:00"
    assert got.work_seconds == 8 * 3600


def test_list_month_filters_by_month(tmp_path):
    s = make_storage(tmp_path)
    s.upsert(Attendance("2026-06-01", "2026-06-01T09:00:00+09:00", None, None))
    s.upsert(Attendance("2026-06-30", "2026-06-30T09:00:00+09:00", None, None))
    s.upsert(Attendance("2026-07-01", "2026-07-01T09:00:00+09:00", None, None))
    rows = s.list_month(2026, 6)
    dates = sorted(r.work_date for r in rows)
    assert dates == ["2026-06-01", "2026-06-30"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_storage.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.storage'`)

- [ ] **Step 3: storage 구현**

`core/storage.py`:
```python
"""attendance 테이블 SQLite 접근."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass


@dataclass
class Attendance:
    work_date: str
    clock_in: str
    clock_out: str | None
    work_seconds: int | None


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS attendance (
    work_date    TEXT PRIMARY KEY,
    clock_in     TEXT NOT NULL,
    clock_out    TEXT,
    work_seconds INTEGER
)
"""


class Storage:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_SQL)
        self._conn.commit()

    def get(self, work_date: str) -> Attendance | None:
        cur = self._conn.execute(
            "SELECT work_date, clock_in, clock_out, work_seconds "
            "FROM attendance WHERE work_date = ?",
            (work_date,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return Attendance(
            row["work_date"], row["clock_in"], row["clock_out"], row["work_seconds"]
        )

    def upsert(self, rec: Attendance) -> None:
        self._conn.execute(
            "INSERT INTO attendance (work_date, clock_in, clock_out, work_seconds) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(work_date) DO UPDATE SET "
            "clock_in=excluded.clock_in, clock_out=excluded.clock_out, "
            "work_seconds=excluded.work_seconds",
            (rec.work_date, rec.clock_in, rec.clock_out, rec.work_seconds),
        )
        self._conn.commit()

    def list_month(self, year: int, month: int) -> list[Attendance]:
        prefix = f"{year:04d}-{month:02d}-"
        cur = self._conn.execute(
            "SELECT work_date, clock_in, clock_out, work_seconds "
            "FROM attendance WHERE work_date LIKE ? ORDER BY work_date",
            (prefix + "%",),
        )
        return [
            Attendance(r["work_date"], r["clock_in"], r["clock_out"], r["work_seconds"])
            for r in cur.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_storage.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
cd ~/work-widget && git add core/storage.py tests/test_storage.py && git commit -m "✨ attendance SQLite 저장소 추가"
```

---

### Task 4: 출퇴근/수동수정/월간합계 비즈니스 로직

**Files:**
- Create: `core/attendance.py`
- Test: `tests/test_attendance.py`

**Interfaces:**
- Consumes:
  - `core.storage.Storage`, `core.storage.Attendance`
  - `core.worktime.compute_work_seconds`
  - `core.timeutil` (`now`, `today_str`, `to_iso`, `from_iso`)
- Produces:
  - `core/attendance.py`:
    - `class AttendanceService`:
      - `__init__(self, storage: Storage, clock=timeutil.now)` — `clock`은 테스트 주입용 무인자 함수, KST datetime 반환
      - `record_clock_in(self) -> Attendance` — 오늘 행 없으면 현재 시각으로 생성, 있으면 그대로 반환(불변)
      - `record_clock_out(self) -> Attendance` — 오늘 행의 `clock_out`/`work_seconds` 설정 후 저장·반환. 오늘 행 없으면 `ValueError`
      - `edit(self, work_date: str, clock_in_iso: str, clock_out_iso: str | None) -> Attendance`
        — 수동 수정/생성. `clock_out_iso`가 None/빈문자면 미퇴근(둘 다 NULL). 값 있으면 `compute_work_seconds`로 재계산. 퇴근<=출근이면 `ValueError`.
      - `month_total_seconds(self, year: int, month: int) -> int` — `work_seconds` 합계(미퇴근 None 제외)

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_attendance.py`:
```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core.storage import Storage
from core.attendance import AttendanceService

KST = ZoneInfo("Asia/Seoul")


def make_service(tmp_path, fixed_dt):
    storage = Storage(str(tmp_path / "att.db"))
    return AttendanceService(storage, clock=lambda: fixed_dt)


def test_clock_in_creates_today_row(tmp_path):
    dt = datetime(2026, 6, 30, 8, 30, tzinfo=KST)
    svc = make_service(tmp_path, dt)
    rec = svc.record_clock_in()
    assert rec.work_date == "2026-06-30"
    assert rec.clock_in == dt.isoformat()
    assert rec.clock_out is None


def test_clock_in_is_immutable_on_rerun(tmp_path):
    dt1 = datetime(2026, 6, 30, 8, 30, tzinfo=KST)
    svc = make_service(tmp_path, dt1)
    svc.record_clock_in()
    # 같은 날 더 늦은 시각으로 재실행해도 최초 기록 유지
    svc._clock = lambda: datetime(2026, 6, 30, 10, 0, tzinfo=KST)
    rec = svc.record_clock_in()
    assert rec.clock_in == dt1.isoformat()


def test_clock_out_computes_work_seconds(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    rec = svc.record_clock_out()
    assert rec.clock_out == datetime(2026, 6, 30, 18, 0, tzinfo=KST).isoformat()
    assert rec.work_seconds == 8 * 3600  # 9시간 - 60분


def test_clock_out_without_row_raises(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 18, 0, tzinfo=KST))
    with pytest.raises(ValueError):
        svc.record_clock_out()


def test_edit_recomputes(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    rec = svc.edit(
        "2026-06-29",
        "2026-06-29T09:00:00+09:00",
        "2026-06-29T17:00:00+09:00",
    )
    assert rec.work_seconds == 7 * 3600 + 30 * 60  # 8시간 - 30분


def test_edit_clear_clock_out_sets_incomplete(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    rec = svc.edit("2026-06-29", "2026-06-29T09:00:00+09:00", "")
    assert rec.clock_out is None
    assert rec.work_seconds is None


def test_edit_clock_out_before_in_raises(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    with pytest.raises(ValueError):
        svc.edit(
            "2026-06-29",
            "2026-06-29T18:00:00+09:00",
            "2026-06-29T09:00:00+09:00",
        )


def test_month_total_excludes_incomplete(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.edit("2026-06-01", "2026-06-01T09:00:00+09:00", "2026-06-01T18:00:00+09:00")
    svc.edit("2026-06-02", "2026-06-02T09:00:00+09:00", "")  # 미퇴근
    assert svc.month_total_seconds(2026, 6) == 8 * 3600
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_attendance.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.attendance'`)

- [ ] **Step 3: attendance 구현**

`core/attendance.py`:
```python
"""출퇴근 기록 및 근무시간 비즈니스 로직."""
from __future__ import annotations

from typing import Callable

from core import timeutil
from core.storage import Attendance, Storage
from core.worktime import compute_work_seconds


class AttendanceService:
    def __init__(self, storage: Storage, clock: Callable[[], object] = timeutil.now) -> None:
        self._storage = storage
        self._clock = clock

    def record_clock_in(self) -> Attendance:
        now = self._clock()
        date = timeutil.today_str(now)
        existing = self._storage.get(date)
        if existing is not None:
            return existing
        rec = Attendance(date, timeutil.to_iso(now), None, None)
        self._storage.upsert(rec)
        return rec

    def record_clock_out(self) -> Attendance:
        now = self._clock()
        date = timeutil.today_str(now)
        existing = self._storage.get(date)
        if existing is None:
            raise ValueError(f"출근 기록이 없습니다: {date}")
        clock_in = timeutil.from_iso(existing.clock_in)
        seconds = compute_work_seconds(clock_in, now)
        rec = Attendance(date, existing.clock_in, timeutil.to_iso(now), seconds)
        self._storage.upsert(rec)
        return rec

    def edit(
        self, work_date: str, clock_in_iso: str, clock_out_iso: str | None
    ) -> Attendance:
        if not clock_out_iso:
            rec = Attendance(work_date, clock_in_iso, None, None)
            self._storage.upsert(rec)
            return rec
        clock_in = timeutil.from_iso(clock_in_iso)
        clock_out = timeutil.from_iso(clock_out_iso)
        if clock_out <= clock_in:
            raise ValueError("퇴근 시각은 출근 시각보다 이후여야 합니다.")
        seconds = compute_work_seconds(clock_in, clock_out)
        rec = Attendance(work_date, clock_in_iso, clock_out_iso, seconds)
        self._storage.upsert(rec)
        return rec

    def month_total_seconds(self, year: int, month: int) -> int:
        rows = self._storage.list_month(year, month)
        return sum(r.work_seconds for r in rows if r.work_seconds is not None)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_attendance.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
cd ~/work-widget && git add core/attendance.py tests/test_attendance.py && git commit -m "✨ 출퇴근/수동수정/월간합계 로직 추가"
```

---

### Task 5: 공휴일 API 클라이언트 + 캐시

**Files:**
- Create: `core/holidays.py`
- Test: `tests/test_holidays.py`

**Interfaces:**
- Consumes: `requests` (HTTP), 로컬 JSON 캐시 파일 경로
- Produces:
  - `core/holidays.py`:
    - `class HolidayClient`:
      - `__init__(self, service_key: str | None, cache_path: str, fetcher: Callable[[str, int, int], list[dict]] | None = None)`
        — `fetcher`는 테스트 주입용. None이면 내부 `_http_fetch` 사용.
      - `get_holidays(self, year: int, month: int) -> dict[str, str]`
        — `{"2026-06-06": "현충일", ...}`. 캐시 우선, 없으면 fetch 후 캐시 저장. service_key 없거나 fetch 실패 시 캐시(있으면) 또는 빈 dict 반환(예외 던지지 않음).
    - 모듈 함수 `parse_items(items: list[dict], year: int, month: int) -> dict[str, str]`
      — 특일정보 API item(`locdate`: int YYYYMMDD, `dateName`: str)을 `{YYYY-MM-DD: name}`으로 변환.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_holidays.py`:
```python
import json

from core.holidays import HolidayClient, parse_items


def test_parse_items_converts_locdate():
    items = [
        {"locdate": 20260606, "dateName": "현충일"},
        {"locdate": 20260615, "dateName": "임시공휴일"},
    ]
    result = parse_items(items, 2026, 6)
    assert result == {"2026-06-06": "현충일", "2026-06-15": "임시공휴일"}


def test_get_holidays_uses_fetcher_and_caches(tmp_path):
    cache = tmp_path / "cache.json"
    calls = []

    def fake_fetch(key, year, month):
        calls.append((year, month))
        return [{"locdate": 20260606, "dateName": "현충일"}]

    client = HolidayClient("KEY", str(cache), fetcher=fake_fetch)
    first = client.get_holidays(2026, 6)
    assert first == {"2026-06-06": "현충일"}
    # 두 번째 호출은 캐시 사용 → fetcher 재호출 없음
    second = client.get_holidays(2026, 6)
    assert second == {"2026-06-06": "현충일"}
    assert calls == [(2026, 6)]


def test_get_holidays_returns_empty_without_key(tmp_path):
    client = HolidayClient(None, str(tmp_path / "c.json"))
    assert client.get_holidays(2026, 6) == {}


def test_get_holidays_falls_back_to_cache_on_fetch_error(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"2026-06": {"2026-06-06": "현충일"}}), encoding="utf-8")

    def boom(key, year, month):
        raise RuntimeError("network down")

    client = HolidayClient("KEY", str(cache), fetcher=boom)
    assert client.get_holidays(2026, 6) == {"2026-06-06": "현충일"}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_holidays.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.holidays'`)

- [ ] **Step 3: holidays 구현**

`core/holidays.py`:
```python
"""공공데이터포털 특일정보 API 공휴일 클라이언트 + 로컬 캐시."""
from __future__ import annotations

import json
import os
from typing import Callable

import requests

_API_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/"
    "SpcdeInfoService/getRestDeInfo"
)
_HTTP_TIMEOUT_SECONDS = 5


def parse_items(items: list[dict], year: int, month: int) -> dict[str, str]:
    """특일정보 item 목록을 {YYYY-MM-DD: 이름} 으로 변환."""
    result: dict[str, str] = {}
    for item in items:
        locdate = str(item.get("locdate", "")).strip()
        if len(locdate) != 8:
            continue
        iso = f"{locdate[0:4]}-{locdate[4:6]}-{locdate[6:8]}"
        result[iso] = item.get("dateName", "공휴일")
    return result


def _http_fetch(service_key: str, year: int, month: int) -> list[dict]:
    params = {
        "serviceKey": service_key,
        "solYear": str(year),
        "solMonth": f"{month:02d}",
        "_type": "json",
        "numOfRows": "100",
    }
    resp = requests.get(_API_URL, params=params, timeout=_HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    body = resp.json()["response"]["body"]
    items = body.get("items")
    if not items:
        return []
    raw = items.get("item", [])
    return raw if isinstance(raw, list) else [raw]


class HolidayClient:
    def __init__(
        self,
        service_key: str | None,
        cache_path: str,
        fetcher: Callable[[str, int, int], list[dict]] | None = None,
    ) -> None:
        self._service_key = service_key
        self._cache_path = cache_path
        self._fetcher = fetcher or _http_fetch

    def _cache_key(self, year: int, month: int) -> str:
        return f"{year:04d}-{month:02d}"

    def _load_cache(self) -> dict:
        if not os.path.exists(self._cache_path):
            return {}
        try:
            with open(self._cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_cache(self, cache: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self._cache_path)), exist_ok=True)
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)

    def get_holidays(self, year: int, month: int) -> dict[str, str]:
        key = self._cache_key(year, month)
        cache = self._load_cache()
        if key in cache:
            return cache[key]
        if not self._service_key:
            return {}
        try:
            items = self._fetcher(self._service_key, year, month)
        except Exception:
            return cache.get(key, {})
        holidays = parse_items(items, year, month)
        cache[key] = holidays
        self._save_cache(cache)
        return holidays
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_holidays.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
cd ~/work-widget && git add core/holidays.py tests/test_holidays.py && git commit -m "✨ 공휴일 API 클라이언트 및 캐시 추가"
```

---

### Task 6: 설정/경로 모듈

**Files:**
- Create: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 없음 (표준 라이브러리)
- Produces:
  - `config.py`:
    - `DATA_DIR` — 기본 `~/.work-widget` (환경변수 `WORK_WIDGET_HOME`로 override 가능)
    - `db_path() -> str` (`DATA_DIR/attendance.db`)
    - `holidays_cache_path() -> str` (`DATA_DIR/holidays_cache.json`)
    - `config_path() -> str` (`DATA_DIR/config.json`)
    - `load_config() -> dict` — 없으면 `{}`
    - `save_config(cfg: dict) -> None`
    - `get_service_key() -> str | None` — 환경변수 `DATA_GO_KR_SERVICE_KEY` 우선, 없으면 config의 `service_key`
    - `get_window_pos() -> tuple[int, int] | None`, `save_window_pos(x: int, y: int) -> None`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_config.py`:
```python
import importlib
import os


def load_config_module(tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_WIDGET_HOME", str(tmp_path))
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    import config as config_module

    importlib.reload(config_module)
    return config_module


def test_paths_under_data_dir(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    assert cfg.db_path() == os.path.join(str(tmp_path), "attendance.db")
    assert cfg.holidays_cache_path() == os.path.join(
        str(tmp_path), "holidays_cache.json"
    )


def test_service_key_env_takes_priority(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    cfg.save_config({"service_key": "FROM_FILE"})
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "FROM_ENV")
    assert cfg.get_service_key() == "FROM_ENV"


def test_service_key_falls_back_to_file(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    cfg.save_config({"service_key": "FROM_FILE"})
    assert cfg.get_service_key() == "FROM_FILE"


def test_window_pos_roundtrip(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    assert cfg.get_window_pos() is None
    cfg.save_window_pos(100, 200)
    assert cfg.get_window_pos() == (100, 200)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'config'`)

- [ ] **Step 3: config 구현**

`config.py`:
```python
"""데이터 경로 및 설정 로드/저장."""
from __future__ import annotations

import json
import os

DATA_DIR = os.environ.get(
    "WORK_WIDGET_HOME", os.path.expanduser("~/.work-widget")
)

_SERVICE_KEY_ENV = "DATA_GO_KR_SERVICE_KEY"


def db_path() -> str:
    return os.path.join(DATA_DIR, "attendance.db")


def holidays_cache_path() -> str:
    return os.path.join(DATA_DIR, "holidays_cache.json")


def config_path() -> str:
    return os.path.join(DATA_DIR, "config.json")


def load_config() -> dict:
    path = config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_service_key() -> str | None:
    env = os.environ.get(_SERVICE_KEY_ENV)
    if env:
        return env
    return load_config().get("service_key")


def get_window_pos() -> tuple[int, int] | None:
    pos = load_config().get("window_pos")
    if isinstance(pos, list) and len(pos) == 2:
        return int(pos[0]), int(pos[1])
    return None


def save_window_pos(x: int, y: int) -> None:
    cfg = load_config()
    cfg["window_pos"] = [x, y]
    save_config(cfg)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_config.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
cd ~/work-widget && git add config.py tests/test_config.py && git commit -m "🔧 데이터 경로·설정 모듈 추가"
```

---

### Task 7: 달력 렌더 보조 순수 함수

**Files:**
- Create: `widget/__init__.py` (빈 파일)
- Create: `widget/calendar_model.py`
- Test: `tests/test_calendar_model.py`

**Interfaces:**
- Consumes: `core.storage.Attendance`
- Produces:
  - `widget/calendar_model.py`:
    - `@dataclass DayCell`: `day: int` (0이면 빈칸), `date: str | None`, `is_today: bool`, `holiday_name: str | None`, `work_seconds: int | None`, `is_incomplete: bool`
    - `format_hms(seconds: int | None) -> str` — `None`→`"-"`, 초→`"Hh Mm"` (예: 27000→`"7h 30m"`)
    - `build_month_grid(year, month, today: str, records: dict[str, Attendance], holidays: dict[str, str]) -> list[list[DayCell]]`
      — 주(월요일 시작) x 7일 그리드. 해당 월 외 칸은 `day=0` 빈 셀.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_calendar_model.py`:
```python
from core.storage import Attendance
from widget.calendar_model import build_month_grid, format_hms


def test_format_hms():
    assert format_hms(None) == "-"
    assert format_hms(27000) == "7h 30m"
    assert format_hms(8 * 3600) == "8h 0m"


def test_grid_has_full_weeks():
    grid = build_month_grid(2026, 6, "2026-06-30", {}, {})
    assert all(len(week) == 7 for week in grid)
    # 2026-06-01은 월요일 → 첫 주 첫 칸이 1일
    assert grid[0][0].day == 1


def test_grid_marks_today_holiday_and_work():
    records = {
        "2026-06-30": Attendance(
            "2026-06-30", "2026-06-30T09:00:00+09:00",
            "2026-06-30T18:00:00+09:00", 8 * 3600,
        ),
        "2026-06-02": Attendance(
            "2026-06-02", "2026-06-02T09:00:00+09:00", None, None,
        ),
    }
    holidays = {"2026-06-06": "현충일"}
    grid = build_month_grid(2026, 6, "2026-06-30", records, holidays)
    cells = {c.date: c for week in grid for c in week if c.day != 0}
    assert cells["2026-06-30"].is_today is True
    assert cells["2026-06-30"].work_seconds == 8 * 3600
    assert cells["2026-06-06"].holiday_name == "현충일"
    assert cells["2026-06-02"].is_incomplete is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_calendar_model.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'widget.calendar_model'`)

- [ ] **Step 3: calendar_model 구현**

`widget/__init__.py`: 빈 파일.

`widget/calendar_model.py`:
```python
"""달력 그리드 구성 순수 로직 (tkinter 비의존)."""
from __future__ import annotations

import calendar
from dataclasses import dataclass

from core.storage import Attendance


@dataclass
class DayCell:
    day: int
    date: str | None
    is_today: bool
    holiday_name: str | None
    work_seconds: int | None
    is_incomplete: bool


def format_hms(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"


def build_month_grid(
    year: int,
    month: int,
    today: str,
    records: dict[str, Attendance],
    holidays: dict[str, str],
) -> list[list[DayCell]]:
    cal = calendar.Calendar(firstweekday=0)  # 0 = Monday
    grid: list[list[DayCell]] = []
    for week in cal.monthdayscalendar(year, month):
        row: list[DayCell] = []
        for day in week:
            if day == 0:
                row.append(DayCell(0, None, False, None, None, False))
                continue
            date = f"{year:04d}-{month:02d}-{day:02d}"
            rec = records.get(date)
            work_seconds = rec.work_seconds if rec else None
            is_incomplete = rec is not None and rec.clock_out is None
            row.append(
                DayCell(
                    day=day,
                    date=date,
                    is_today=(date == today),
                    holiday_name=holidays.get(date),
                    work_seconds=work_seconds,
                    is_incomplete=is_incomplete,
                )
            )
        grid.append(row)
    return grid
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_calendar_model.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
cd ~/work-widget && git add widget/__init__.py widget/calendar_model.py tests/test_calendar_model.py && git commit -m "✨ 달력 그리드 구성 순수 로직 추가"
```

---

### Task 8: 수정 다이얼로그 (tkinter)

**Files:**
- Create: `widget/edit_dialog.py`
- Test: 없음 (tkinter UI는 수동 확인). 단, 입력 파싱 보조 함수는 순수 함수로 분리해 Task 4의 검증을 재사용.

**Interfaces:**
- Consumes: `tkinter`, `core.timeutil`
- Produces:
  - `widget/edit_dialog.py`:
    - `def open_edit_dialog(parent, work_date: str, clock_in_iso: str | None, clock_out_iso: str | None, on_save: Callable[[str, str, str | None], None]) -> None`
      — 모달 Toplevel. 출근/퇴근 시각을 `HH:MM` 텍스트로 입력. 저장 시 `work_date`와 합쳐 ISO 문자열로 만들어 `on_save(work_date, clock_in_iso, clock_out_iso_or_None)` 호출. 출근 비우면 저장 불가(경고). 퇴근 비우면 None 전달.
    - 모듈 함수 `build_iso(work_date: str, hhmm: str) -> str` — `"2026-06-30"`,`"09:00"` → `"2026-06-30T09:00:00+09:00"`. 형식 오류 시 `ValueError`.

**Note (구현자 주의):** `on_save` 콜백 안에서 `AttendanceService.edit`가 `ValueError`를 던질 수 있으므로 호출부(Task 10)에서 try/except로 감싸 경고를 표시한다. 이 다이얼로그 자체는 형식 검증(`build_iso`)만 담당.

- [ ] **Step 1: build_iso 실패 테스트 작성**

`tests/test_edit_dialog.py`:
```python
import pytest

from widget.edit_dialog import build_iso


def test_build_iso_ok():
    assert build_iso("2026-06-30", "09:05") == "2026-06-30T09:05:00+09:00"


def test_build_iso_invalid_raises():
    with pytest.raises(ValueError):
        build_iso("2026-06-30", "9시")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_edit_dialog.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'widget.edit_dialog'`)

- [ ] **Step 3: edit_dialog 구현**

`widget/edit_dialog.py`:
```python
"""출근/퇴근 시각 수정 다이얼로그."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_KST_OFFSET = "+09:00"


def build_iso(work_date: str, hhmm: str) -> str:
    """work_date(YYYY-MM-DD)와 HH:MM을 KST ISO8601 문자열로."""
    m = _HHMM_RE.match(hhmm.strip())
    if not m:
        raise ValueError(f"시각 형식은 HH:MM 이어야 합니다: {hhmm!r}")
    return f"{work_date}T{m.group(1)}:{m.group(2)}:00{_KST_OFFSET}"


def _hhmm_from_iso(iso: Optional[str]) -> str:
    if not iso:
        return ""
    # ...T09:05:00+09:00 → 09:05
    return iso[11:16]


def open_edit_dialog(
    parent,
    work_date: str,
    clock_in_iso: Optional[str],
    clock_out_iso: Optional[str],
    on_save: Callable[[str, str, Optional[str]], None],
) -> None:
    top = tk.Toplevel(parent)
    top.title(f"{work_date} 근무시간 수정")
    top.transient(parent)
    top.grab_set()

    tk.Label(top, text="출근 (HH:MM)").grid(row=0, column=0, padx=8, pady=6)
    in_var = tk.StringVar(value=_hhmm_from_iso(clock_in_iso))
    tk.Entry(top, textvariable=in_var, width=8).grid(row=0, column=1, padx=8)

    tk.Label(top, text="퇴근 (HH:MM, 비우면 미퇴근)").grid(row=1, column=0, padx=8, pady=6)
    out_var = tk.StringVar(value=_hhmm_from_iso(clock_out_iso))
    tk.Entry(top, textvariable=out_var, width=8).grid(row=1, column=1, padx=8)

    def handle_save() -> None:
        in_text = in_var.get().strip()
        if not in_text:
            messagebox.showwarning("입력 오류", "출근 시각을 입력하세요.", parent=top)
            return
        try:
            clock_in = build_iso(work_date, in_text)
            out_text = out_var.get().strip()
            clock_out = build_iso(work_date, out_text) if out_text else None
        except ValueError as exc:
            messagebox.showwarning("입력 오류", str(exc), parent=top)
            return
        try:
            on_save(work_date, clock_in, clock_out)
        except ValueError as exc:
            messagebox.showwarning("저장 실패", str(exc), parent=top)
            return
        top.destroy()

    tk.Button(top, text="저장", command=handle_save).grid(
        row=2, column=0, columnspan=2, pady=10
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_edit_dialog.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
cd ~/work-widget && git add widget/edit_dialog.py tests/test_edit_dialog.py && git commit -m "✨ 출근/퇴근 시각 수정 다이얼로그 추가"
```

---

### Task 9: 위젯 창 + 달력 뷰 (tkinter)

**Files:**
- Create: `widget/window.py`
- Create: `widget/calendar_view.py`
- Test: 없음 (수동 확인). 렌더 데이터는 Task 7의 `build_month_grid`로 검증됨.

**Interfaces:**
- Consumes: `tkinter`, `widget.calendar_model`, `widget.edit_dialog.open_edit_dialog`, `config`
- Produces:
  - `widget/window.py`:
    - `class WidgetWindow`:
      - `__init__(self, on_clock_out: Callable[[], None], on_edit_day: Callable[[str], None])`
      - `render(self, header_text: str, grid: list[list[DayCell]]) -> None` — 헤더(오늘 출근시각·월 누적)와 달력 그리드 갱신
      - `run(self) -> None` — `mainloop`
      - 테두리 없는 always-on-top 창, 드래그 이동, 종료 시 `config.save_window_pos`
  - `widget/calendar_view.py`:
    - `def render_grid(parent, grid, on_day_click: Callable[[str], None]) -> None` — 그리드를 parent 프레임에 그린다. 셀 클릭 시 `on_day_click(date)`. 공휴일 빨강, 오늘 강조, 미퇴근 표시, 근무시간 `format_hms`.

- [ ] **Step 1: calendar_view 구현**

`widget/calendar_view.py`:
```python
"""tkinter 달력 그리드 렌더링."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from widget.calendar_model import DayCell, format_hms

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
_TODAY_BG = "#2d6cdf"
_HOLIDAY_FG = "#d33"
_NORMAL_FG = "#222"


def render_grid(
    parent: tk.Widget,
    grid: list[list[DayCell]],
    on_day_click: Callable[[str], None],
) -> None:
    for child in parent.winfo_children():
        child.destroy()

    for col, name in enumerate(_WEEKDAYS):
        fg = _HOLIDAY_FG if name in ("토", "일") else _NORMAL_FG
        tk.Label(parent, text=name, fg=fg, width=6).grid(row=0, column=col, padx=1, pady=1)

    for r, week in enumerate(grid, start=1):
        for c, cell in enumerate(week):
            if cell.day == 0:
                tk.Label(parent, text="", width=6, height=2).grid(row=r, column=c)
                continue
            is_holiday = cell.holiday_name is not None or c >= 5
            fg = _HOLIDAY_FG if is_holiday else _NORMAL_FG
            bg = _TODAY_BG if cell.is_today else None
            day_fg = "white" if cell.is_today else fg
            if cell.is_incomplete:
                sub = "미퇴근"
            else:
                sub = format_hms(cell.work_seconds) if cell.work_seconds is not None else ""
            text = f"{cell.day}\n{sub}"
            btn = tk.Label(
                parent, text=text, width=6, height=2, fg=day_fg, bg=bg,
                relief="flat", cursor="hand2", justify="center",
            )
            btn.grid(row=r, column=c, padx=1, pady=1)
            btn.bind("<Button-1>", lambda _e, d=cell.date: on_day_click(d))
```

- [ ] **Step 2: window 구현**

`widget/window.py`:
```python
"""테두리 없는 always-on-top 위젯 창."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import config
from widget.calendar_model import DayCell
from widget.calendar_view import render_grid


class WidgetWindow:
    def __init__(
        self,
        on_clock_out: Callable[[], None],
        on_edit_day: Callable[[str], None],
    ) -> None:
        self._on_clock_out = on_clock_out
        self._on_edit_day = on_edit_day
        self._root = tk.Tk()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        pos = config.get_window_pos()
        if pos:
            self._root.geometry(f"+{pos[0]}+{pos[1]}")

        self._header = tk.Label(self._root, text="", font=("Helvetica", 12, "bold"))
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        self._cal_frame = tk.Frame(self._root)
        self._cal_frame.pack(padx=8, pady=4)

        tk.Button(self._root, text="퇴근", command=self._on_clock_out).pack(
            pady=(4, 8)
        )

        self._bind_drag()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_drag(self) -> None:
        self._drag = {"x": 0, "y": 0}

        def start(e):
            self._drag["x"], self._drag["y"] = e.x, e.y

        def move(e):
            x = self._root.winfo_x() + (e.x - self._drag["x"])
            y = self._root.winfo_y() + (e.y - self._drag["y"])
            self._root.geometry(f"+{x}+{y}")

        self._header.bind("<Button-1>", start)
        self._header.bind("<B1-Motion>", move)

    def _on_close(self) -> None:
        config.save_window_pos(self._root.winfo_x(), self._root.winfo_y())
        self._root.destroy()

    def render(self, header_text: str, grid: list[list[DayCell]]) -> None:
        self._header.config(text=header_text)
        render_grid(self._cal_frame, grid, self._on_edit_day)

    def run(self) -> None:
        self._root.mainloop()
```

- [ ] **Step 3: import 스모크 테스트**

Run:
```bash
cd ~/work-widget && ./venv/bin/python -c "import widget.window, widget.calendar_view; print('import OK')"
```
Expected: `import OK` (tkinter import 오류 없음. macOS 기본 python3에 tkinter 포함)

- [ ] **Step 4: 커밋**

```bash
cd ~/work-widget && git add widget/window.py widget/calendar_view.py && git commit -m "✨ always-on-top 위젯 창 및 달력 뷰 추가"
```

---

### Task 10: 앱 조립 (main.py)

**Files:**
- Create: `main.py`
- Test: 없음 (수동 실행 확인)

**Interfaces:**
- Consumes: `config`, `core.storage.Storage`, `core.attendance.AttendanceService`, `core.holidays.HolidayClient`, `core.timeutil`, `widget.window.WidgetWindow`, `widget.calendar_model.build_month_grid`, `widget.calendar_model.format_hms`, `widget.edit_dialog.open_edit_dialog`
- Produces: `main.py`의 `class App` + `def main()`

- [ ] **Step 1: main 구현**

`main.py`:
```python
"""근무시간 데스크탑 위젯 진입점."""
from __future__ import annotations

import config
from core import timeutil
from core.attendance import AttendanceService
from core.holidays import HolidayClient
from core.storage import Storage
from widget.calendar_model import build_month_grid, format_hms
from widget.edit_dialog import open_edit_dialog
from widget.window import WidgetWindow


class App:
    def __init__(self) -> None:
        self._storage = Storage(config.db_path())
        self._service = AttendanceService(self._storage)
        self._holidays = HolidayClient(
            config.get_service_key(), config.holidays_cache_path()
        )
        self._window = WidgetWindow(
            on_clock_out=self._handle_clock_out,
            on_edit_day=self._handle_edit_day,
        )

    def _refresh(self) -> None:
        now = timeutil.now()
        year, month = now.year, now.month
        today = timeutil.today_str(now)
        records = {
            r.work_date: r for r in self._storage.list_month(year, month)
        }
        holidays = self._holidays.get_holidays(year, month)
        grid = build_month_grid(year, month, today, records, holidays)

        today_rec = records.get(today)
        clock_in_txt = today_rec.clock_in[11:16] if today_rec else "-"
        total = self._service.month_total_seconds(year, month)
        header = f"출근 {clock_in_txt}  |  {month}월 누적 {format_hms(total)}"
        self._window.render(header, grid)

    def _handle_clock_out(self) -> None:
        try:
            self._service.record_clock_out()
        except ValueError:
            pass
        self._refresh()

    def _handle_edit_day(self, date: str) -> None:
        rec = self._storage.get(date)
        open_edit_dialog(
            self._window._root,
            date,
            rec.clock_in if rec else None,
            rec.clock_out if rec else None,
            self._handle_save_edit,
        )

    def _handle_save_edit(self, work_date, clock_in_iso, clock_out_iso) -> None:
        self._service.edit(work_date, clock_in_iso, clock_out_iso)
        self._refresh()

    def run(self) -> None:
        self._service.record_clock_in()  # 부팅 = 출근
        self._refresh()
        self._window.run()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 전체 테스트 + 스모크 확인**

Run:
```bash
cd ~/work-widget && ./venv/bin/pytest -q && ./venv/bin/python -c "import main; print('import OK')"
```
Expected: 모든 테스트 PASS, `import OK`

- [ ] **Step 3: 수동 실행 확인 (사용자)**

Run: `cd ~/work-widget && ./venv/bin/python main.py`
Expected: 바탕화면에 달력 위젯이 뜨고, 오늘 칸 강조 + 헤더에 출근시각 표시. '퇴근' 클릭 시 누적 갱신. 날짜 클릭 시 수정 다이얼로그.
(확인 후 창 닫기)

- [ ] **Step 4: 커밋**

```bash
cd ~/work-widget && git add main.py && git commit -m "✨ 앱 조립 진입점(main) 추가"
```

---

### Task 11: 자동 시작 (LaunchAgent)

**Files:**
- Create: `install_autostart.py`
- Test: `tests/test_install_autostart.py`

**Interfaces:**
- Consumes: 없음 (표준 라이브러리, plist 텍스트 생성)
- Produces:
  - `install_autostart.py`:
    - `LABEL = "com.taeyeon.workwidget"`
    - `build_plist(python_path: str, main_path: str, label: str = LABEL) -> str` — `RunAtLoad=true` plist XML 문자열
    - `plist_target_path(label: str = LABEL) -> str` — `~/Library/LaunchAgents/<label>.plist`
    - `install() -> str` — 현재 venv python과 main.py 절대경로로 plist 작성·저장, 경로 반환
    - `uninstall() -> None`
    - `python -m install_autostart install|uninstall` CLI

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_install_autostart.py`:
```python
from install_autostart import build_plist, plist_target_path


def test_build_plist_contains_paths_and_runatload():
    xml = build_plist("/venv/bin/python", "/home/u/work-widget/main.py", "com.x.y")
    assert "/venv/bin/python" in xml
    assert "/home/u/work-widget/main.py" in xml
    assert "<key>RunAtLoad</key>" in xml
    assert "<true/>" in xml
    assert "com.x.y" in xml


def test_plist_target_path_uses_label():
    path = plist_target_path("com.x.y")
    assert path.endswith("Library/LaunchAgents/com.x.y.plist")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_install_autostart.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'install_autostart'`)

- [ ] **Step 3: install_autostart 구현**

`install_autostart.py`:
```python
"""macOS LaunchAgent 자동 시작 설치/제거."""
from __future__ import annotations

import os
import sys

LABEL = "com.taeyeon.workwidget"

_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{main_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/workwidget.out.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/workwidget.err.log</string>
</dict>
</plist>
"""


def build_plist(python_path: str, main_path: str, label: str = LABEL) -> str:
    log_dir = os.path.expanduser("~/.work-widget")
    return _PLIST_TEMPLATE.format(
        label=label, python_path=python_path, main_path=main_path, log_dir=log_dir
    )


def plist_target_path(label: str = LABEL) -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")


def install() -> str:
    python_path = os.path.abspath(sys.executable)
    main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    xml = build_plist(python_path, main_path)
    target = plist_target_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.makedirs(os.path.expanduser("~/.work-widget"), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(xml)
    return target


def uninstall() -> None:
    target = plist_target_path()
    if os.path.exists(target):
        os.remove(target)


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if action == "install":
        path = install()
        print(f"설치됨: {path}")
        print(f"활성화: launchctl load {path}")
    elif action == "uninstall":
        uninstall()
        print("제거됨")
    else:
        print("사용법: python install_autostart.py [install|uninstall]")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest tests/test_install_autostart.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 자동 시작 등록 (사용자 수동)**

Run:
```bash
cd ~/work-widget && ./venv/bin/python install_autostart.py install && launchctl load ~/Library/LaunchAgents/com.taeyeon.workwidget.plist
```
Expected: `설치됨: ...` 출력 후 재부팅(또는 재로그인) 시 위젯 자동 실행.

- [ ] **Step 6: 커밋**

```bash
cd ~/work-widget && git add install_autostart.py tests/test_install_autostart.py && git commit -m "🔧 LaunchAgent 자동 시작 설치 스크립트 추가"
```

---

### Task 12: README & 최종 검증

**Files:**
- Create: `README.md`
- Test: 전체 스위트

**Interfaces:**
- Consumes: 전체
- Produces: 사용 설명서

- [ ] **Step 1: README 작성**

`README.md`:
```markdown
# work-widget — 근무시간 데스크탑 위젯

macOS 부팅 시 자동 실행되어 출근 시간을 기록하고, 한국 공휴일과
월간 누적 근무시간을 바탕화면 달력 위젯으로 보여준다.

## 설치

```bash
cd ~/work-widget
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 공휴일 API 키 설정 (선택)

공공데이터포털(data.go.kr) "특일정보" 서비스 키를 발급받아 설정:

```bash
mkdir -p ~/.work-widget
echo '{"service_key": "발급받은_키"}' > ~/.work-widget/config.json
```
또는 환경변수 `DATA_GO_KR_SERVICE_KEY` 사용. 키가 없으면 공휴일 없이 동작.

## 실행

```bash
./venv/bin/python main.py
```

## 자동 시작 등록

```bash
./venv/bin/python install_autostart.py install
launchctl load ~/Library/LaunchAgents/com.taeyeon.workwidget.plist
```

해제: `launchctl unload ...` 후 `python install_autostart.py uninstall`.

## 사용

- 부팅(실행) 시 그날 첫 실행 시각이 출근으로 기록됨(이미 있으면 유지).
- '퇴근' 버튼으로 근무시간 확정. 점심 차감: 9시간 미만 -30분, 9시간 이상 -1시간.
- 날짜 클릭 → 출근/퇴근 시각 수동 수정. 퇴근 비우면 미퇴근 처리.

## 데이터 위치

`~/.work-widget/attendance.db` (근무 기록), `holidays_cache.json` (공휴일 캐시).
```

- [ ] **Step 2: 전체 테스트 통과 + 커버리지 확인**

Run: `cd ~/work-widget && ./venv/bin/pytest -q`
Expected: 모든 테스트 PASS (대략 30+ passed)

- [ ] **Step 3: 커밋**

```bash
cd ~/work-widget && git add README.md && git commit -m "📝 README 추가 및 최종 검증"
```

---

## Self-Review

**Spec coverage 확인:**
- 부팅 자동 실행 → Task 11 (LaunchAgent)
- 출근 자동 기록 + 최초기록 유지 → Task 4 (`record_clock_in`), Task 10 (`run`)
- 퇴근 버튼 → Task 4 (`record_clock_out`), Task 9/10
- 점심 차감(9h 30분/60분, 음수보정) → Task 2 (`compute_work_seconds`)
- 월간 누적 → Task 4 (`month_total_seconds`), Task 10 헤더
- 공휴일 API + KST + 캐시 → Task 5, Task 1 (timeutil)
- 이번 달 달력/오늘 강조/공휴일 표시 → Task 7, Task 9
- 일자 클릭 수동 수정(생성/미퇴근/검증) → Task 4 (`edit`), Task 8, Task 10
- 미퇴근 처리(합계 제외/표시) → Task 4, Task 7
- 로컬 저장 → Task 3
- 시크릿 비하드코딩 → Task 6
- always-on-top 데스크탑 창 → Task 9

**Type consistency:** `Attendance` 필드(`work_date/clock_in/clock_out/work_seconds`), `AttendanceService.edit/record_clock_in/record_clock_out/month_total_seconds`, `build_month_grid`/`format_hms`/`DayCell`, `HolidayClient.get_holidays`, `build_iso`/`open_edit_dialog`, `WidgetWindow.render/run`, `build_plist`/`plist_target_path` — 정의 태스크와 소비 태스크 간 시그니처 일치 확인 완료.

**Placeholder scan:** TBD/TODO/추상 지시 없음. 모든 코드 단계에 실제 코드 포함.
