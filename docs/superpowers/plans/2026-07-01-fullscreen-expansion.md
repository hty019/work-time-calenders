# 전체 화면 프로그램 확장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** tkinter 위젯을 PySide6/Qt 기반 전체 화면 앱으로 확장하되 위젯 모드도 지원하고, 날짜별 계획 근무 시간·예상 퇴근시각·월 현황 status 패널을 추가한다.

**Architecture:** `core/`는 Qt 비의존 순수 도메인 로직으로 확장(단위 테스트 대상). `ui/`는 PySide6 표현 계층(얇게). 단일 `QApplication`이 전체화면·위젯 두 창을 소유하고 같은 서비스 인스턴스를 공유하며 모드 전환한다.

**Tech Stack:** Python 3, PySide6, SQLite, pytest. 기존 `core/`(storage·attendance·worktime·holidays·timeutil) 재사용.

## Global Constraints

- 모든 코드 주석·커밋 메시지·UI 문구는 **한글**.
- 커밋 prefix: ✨기능 🐛버그 🔧설정 📝문서 ♻️리팩토링 🔥삭제.
- 매직 넘버 금지 — 상수로 정의. 하드코딩 시크릿 금지. `print`/디버그 코드 커밋 금지.
- 시간대는 **KST**(`core.timeutil.KST`) 기준. 날짜 문자열은 `YYYY-MM-DD`.
- **계획·근무는 순 근무시간(휴게 제외) 기준**. 계획 단위는 분(minutes) 정수.
- 평일 기본 계획 = `config.get_default_daily_minutes()`(기본 480분=8h). 주말(토=5·일=6)·공휴일 기본 0.
- 기존 SQLite DB 무손상: 새 테이블은 `CREATE IF NOT EXISTS`.
- `core/`는 `import tkinter`·`import PySide6` 를 하지 않는다(순수 유지).
- 작업 완료 후 커밋은 사용자 승인 후 수행(단, 이 플랜의 각 Task는 스텝에 커밋을 포함하며 실행 스킬 규칙을 따른다).

---

### Task 1: 예상 퇴근 역산 `raw_seconds_for_net`

목표 순근무 초에 도달하는 최소 체류 초를 구한다. `compute_work_seconds`의 역함수.

**Files:**
- Modify: `core/worktime.py`
- Test: `tests/test_worktime.py`

**Interfaces:**
- Consumes: 기존 `core/worktime.py`의 상수 `FOUR_HOURS_SECONDS`, `EIGHT_HOURS_SECONDS`, `BREAK_SECONDS`.
- Produces: `raw_seconds_for_net(net_seconds: int) -> int`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_worktime.py` 끝에 추가

```python
from core.worktime import raw_seconds_for_net, compute_work_seconds


def test_raw_for_net_under_4h_no_break():
    # 순근무 3h → 휴게 없음 → 체류 3h
    assert raw_seconds_for_net(3 * 3600) == 3 * 3600


def test_raw_for_net_exactly_4h():
    # 순근무 4h 도달 최소 체류 = 4h (휴게 시작 직전)
    assert raw_seconds_for_net(4 * 3600) == 4 * 3600


def test_raw_for_net_between_4h_and_8h_adds_30m():
    # 순근무 7h30m → 체류 8h (1차 휴게 30분 포함)
    assert raw_seconds_for_net(7 * 3600 + 30 * 60) == 8 * 3600


def test_raw_for_net_exactly_8h_adds_30m():
    # 순근무 8h → 체류 8h30m
    assert raw_seconds_for_net(8 * 3600) == 8 * 3600 + 30 * 60


def test_raw_for_net_over_8h_adds_60m():
    # 순근무 10h → 체류 11h (2차 휴게까지 60분)
    assert raw_seconds_for_net(10 * 3600) == 11 * 3600


def test_raw_for_net_zero_or_negative():
    assert raw_seconds_for_net(0) == 0
    assert raw_seconds_for_net(-100) == 0


def test_raw_for_net_roundtrips_with_compute():
    # 역산한 체류로 다시 순근무를 계산하면 목표와 일치(플랫 경계 제외 지점)
    from datetime import datetime
    from zoneinfo import ZoneInfo
    kst = ZoneInfo("Asia/Seoul")
    base = datetime(2026, 6, 30, 9, 0, tzinfo=kst)
    for net in (2 * 3600, 5 * 3600, 7 * 3600, 9 * 3600, 11 * 3600):
        raw = raw_seconds_for_net(net)
        out = base.fromtimestamp(base.timestamp() + raw, tz=kst)
        assert compute_work_seconds(base, out) == net
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_worktime.py -k raw_for_net -v`
Expected: FAIL — `ImportError: cannot import name 'raw_seconds_for_net'`

- [ ] **Step 3: 최소 구현** — `core/worktime.py` 끝에 추가

```python
def raw_seconds_for_net(net_seconds: int) -> int:
    """목표 순근무 초에 도달하는 최소 체류 초. compute_work_seconds 의 역함수.

    net ≤ 4h        : 휴게 없음 → raw = net
    4h < net ≤ 8h   : 1차 휴게 30분 포함 → raw = net + 30m
    net > 8h        : 2차 휴게까지 60분 포함 → raw = net + 60m
    """
    if net_seconds <= 0:
        return 0
    if net_seconds <= FOUR_HOURS_SECONDS:
        return net_seconds
    if net_seconds <= EIGHT_HOURS_SECONDS:
        return net_seconds + BREAK_SECONDS
    return net_seconds + 2 * BREAK_SECONDS
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_worktime.py -v`
Expected: PASS (기존 + 신규 전부)

- [ ] **Step 5: 커밋**

```bash
git add core/worktime.py tests/test_worktime.py
git commit -m "✨ 계획 순근무 도달 체류시간 역산 함수 추가"
```

---

### Task 2: `plan` 테이블 저장소 접근

날짜별 계획 오버라이드를 저장하는 `plan` 테이블과 접근 메서드를 추가한다.

**Files:**
- Modify: `core/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: 기존 `Storage.__init__`, `self._conn`.
- Produces:
  - `Storage.get_plan(work_date: str) -> int | None`
  - `Storage.set_plan(work_date: str, planned_minutes: int) -> None`
  - `Storage.clear_plan(work_date: str) -> None`
  - `Storage.list_plan_month(year: int, month: int) -> dict[str, int]`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_storage.py` 끝에 추가

```python
def test_plan_set_get_clear(tmp_path):
    from core.storage import Storage
    st = Storage(str(tmp_path / "a.db"))
    assert st.get_plan("2026-07-07") is None
    st.set_plan("2026-07-07", 240)
    assert st.get_plan("2026-07-07") == 240
    st.set_plan("2026-07-07", 360)  # 덮어쓰기
    assert st.get_plan("2026-07-07") == 360
    st.clear_plan("2026-07-07")
    assert st.get_plan("2026-07-07") is None


def test_plan_list_month(tmp_path):
    from core.storage import Storage
    st = Storage(str(tmp_path / "b.db"))
    st.set_plan("2026-07-01", 480)
    st.set_plan("2026-07-15", 240)
    st.set_plan("2026-08-01", 480)  # 다른 달
    got = st.list_plan_month(2026, 7)
    assert got == {"2026-07-01": 480, "2026-07-15": 240}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_storage.py -k plan -v`
Expected: FAIL — `AttributeError: 'Storage' object has no attribute 'set_plan'`

- [ ] **Step 3: 구현** — `core/storage.py`

`_CREATE_SQL` 아래에 새 상수 추가:

```python
_CREATE_PLAN_SQL = """
CREATE TABLE IF NOT EXISTS plan (
    work_date       TEXT PRIMARY KEY,
    planned_minutes INTEGER NOT NULL
)
"""
```

`__init__` 안 `self._conn.execute(_CREATE_SQL)` 다음 줄에 추가:

```python
        self._conn.execute(_CREATE_PLAN_SQL)
```

`close` 메서드 위에 메서드 추가:

```python
    def get_plan(self, work_date: str) -> int | None:
        cur = self._conn.execute(
            "SELECT planned_minutes FROM plan WHERE work_date = ?",
            (work_date,),
        )
        row = cur.fetchone()
        return int(row["planned_minutes"]) if row is not None else None

    def set_plan(self, work_date: str, planned_minutes: int) -> None:
        self._conn.execute(
            "INSERT INTO plan (work_date, planned_minutes) VALUES (?, ?) "
            "ON CONFLICT(work_date) DO UPDATE SET "
            "planned_minutes=excluded.planned_minutes",
            (work_date, planned_minutes),
        )
        self._conn.commit()

    def clear_plan(self, work_date: str) -> None:
        self._conn.execute("DELETE FROM plan WHERE work_date = ?", (work_date,))
        self._conn.commit()

    def list_plan_month(self, year: int, month: int) -> dict[str, int]:
        prefix = f"{year:04d}-{month:02d}-"
        cur = self._conn.execute(
            "SELECT work_date, planned_minutes FROM plan "
            "WHERE work_date LIKE ? ORDER BY work_date",
            (prefix + "%",),
        )
        return {r["work_date"]: int(r["planned_minutes"]) for r in cur.fetchall()}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_storage.py -v`
Expected: PASS (기존 attendance 테스트 포함 전부)

- [ ] **Step 5: 커밋**

```bash
git add core/storage.py tests/test_storage.py
git commit -m "✨ 날짜별 계획 근무시간 plan 테이블 저장소 추가"
```

---

### Task 3: config에 기본 계획분·마지막 모드 추가

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 기존 `config.load_config`, `config.save_config`.
- Produces:
  - `config.get_default_daily_minutes() -> int` (기본 480)
  - `config.set_default_daily_minutes(minutes: int) -> None`
  - `config.get_last_mode() -> str` ("full" | "widget", 기본 "full")
  - `config.set_last_mode(mode: str) -> None`
  - 상수 `DEFAULT_DAILY_MINUTES = 480`, `MODE_FULL = "full"`, `MODE_WIDGET = "widget"`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_config.py` 끝에 추가

```python
def test_default_daily_minutes_roundtrip(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    assert config.get_default_daily_minutes() == config.DEFAULT_DAILY_MINUTES
    config.set_default_daily_minutes(240)
    assert config.get_default_daily_minutes() == 240


def test_last_mode_roundtrip(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    assert config.get_last_mode() == config.MODE_FULL
    config.set_last_mode(config.MODE_WIDGET)
    assert config.get_last_mode() == config.MODE_WIDGET
```

참고: `config` 함수들은 `config_path()`가 `DATA_DIR`를 참조하므로 `monkeypatch.setattr(config, "DATA_DIR", ...)`로 격리한다. 기존 테스트가 다른 패턴을 쓰면 그 패턴을 따른다(먼저 `tests/test_config.py`를 확인할 것).

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_config.py -k "default_daily or last_mode" -v`
Expected: FAIL — `AttributeError: module 'config' has no attribute 'get_default_daily_minutes'`

- [ ] **Step 3: 구현** — `config.py`

`_SERVICE_KEY_ENV` 아래에 상수 추가:

```python
DEFAULT_DAILY_MINUTES = 480  # 평일 기본 계획 순근무(분) = 8h
MODE_FULL = "full"
MODE_WIDGET = "widget"
```

파일 끝에 함수 추가:

```python
def get_default_daily_minutes() -> int:
    value = load_config().get("default_daily_minutes")
    if isinstance(value, int) and value >= 0:
        return value
    return DEFAULT_DAILY_MINUTES


def set_default_daily_minutes(minutes: int) -> None:
    cfg = load_config()
    cfg["default_daily_minutes"] = int(minutes)
    save_config(cfg)


def get_last_mode() -> str:
    mode = load_config().get("last_mode")
    return mode if mode in (MODE_FULL, MODE_WIDGET) else MODE_FULL


def set_last_mode(mode: str) -> None:
    if mode not in (MODE_FULL, MODE_WIDGET):
        raise ValueError(f"알 수 없는 모드: {mode!r}")
    cfg = load_config()
    cfg["last_mode"] = mode
    save_config(cfg)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add config.py tests/test_config.py
git commit -m "🔧 기본 계획 근무분·마지막 모드 설정 추가"
```

---

### Task 4: `PlanService` — 유효 계획분 계산

**Files:**
- Create: `core/plan.py`
- Test: `tests/test_plan.py`

**Interfaces:**
- Consumes: `core.storage.Storage`의 `get_plan`/`set_plan`/`clear_plan`/`list_plan_month` (Task 2), `config.get_default_daily_minutes` (Task 3).
- Produces:
  - `PlanService(storage, default_minutes_getter=config.get_default_daily_minutes)`
  - `.effective_minutes(date: str, holidays: dict[str, str]) -> int`
  - `.month_planned_minutes(year: int, month: int, holidays: dict[str, str]) -> int`
  - `.get_override(date: str) -> int | None`
  - `.set_plan(date: str, minutes: int) -> None`
  - `.clear_plan(date: str) -> None`
  - 상수 `SATURDAY = 5`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_plan.py` 생성

```python
from core.plan import PlanService


class FakeStorage:
    def __init__(self):
        self._plans = {}

    def get_plan(self, d):
        return self._plans.get(d)

    def set_plan(self, d, m):
        self._plans[d] = m

    def clear_plan(self, d):
        self._plans.pop(d, None)

    def list_plan_month(self, y, mo):
        prefix = f"{y:04d}-{mo:02d}-"
        return {d: m for d, m in self._plans.items() if d.startswith(prefix)}


def _svc():
    return PlanService(FakeStorage(), default_minutes_getter=lambda: 480)


def test_weekday_uses_default():
    # 2026-07-01 은 수요일 → 기본 480
    assert _svc().effective_minutes("2026-07-01", {}) == 480


def test_weekend_is_zero():
    # 2026-07-04 토, 2026-07-05 일
    svc = _svc()
    assert svc.effective_minutes("2026-07-04", {}) == 0
    assert svc.effective_minutes("2026-07-05", {}) == 0


def test_holiday_is_zero():
    # 평일이지만 공휴일이면 0
    svc = _svc()
    assert svc.effective_minutes("2026-07-01", {"2026-07-01": "임시공휴일"}) == 0


def test_override_wins_over_everything():
    svc = _svc()
    svc.set_plan("2026-07-04", 240)  # 토요일에도 오버라이드 적용
    assert svc.effective_minutes("2026-07-04", {}) == 240
    svc.set_plan("2026-07-01", 0)  # 평일 0시간 오버라이드(휴가)
    assert svc.effective_minutes("2026-07-01", {}) == 0


def test_month_planned_sums_effective():
    # 2026-07: 평일 수 23일(공휴일 없음 가정) × 480
    svc = _svc()
    total = svc.month_planned_minutes(2026, 7, {})
    assert total == 23 * 480


def test_month_planned_applies_override_and_holiday():
    svc = _svc()
    svc.set_plan("2026-07-01", 240)  # 평일 하루 480→240
    holidays = {"2026-07-17": "제헌절가정"}  # 평일 하루 480→0
    total = svc.month_planned_minutes(2026, 7, holidays)
    # 기준 23*480 에서 (480-240) 및 480 차감
    assert total == 23 * 480 - 240 - 480
```

주의: `2026-07`의 평일 수는 계획 실행 시 `python -c "import calendar; ..."`로 검증하고, 위 `23`이 다르면 실제 값으로 교정한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_plan.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.plan'`

- [ ] **Step 3: 구현** — `core/plan.py` 생성

```python
"""날짜별 계획 근무시간(순근무 분) 도출 서비스."""
from __future__ import annotations

import calendar
import datetime
from typing import Callable

import config

SATURDAY = 5  # date.weekday(): 월=0 ~ 일=6, 토=5 · 일=6


class PlanService:
    def __init__(
        self,
        storage,
        default_minutes_getter: Callable[[], int] = config.get_default_daily_minutes,
    ) -> None:
        self._storage = storage
        self._default_getter = default_minutes_getter

    def get_override(self, date: str) -> int | None:
        return self._storage.get_plan(date)

    def set_plan(self, date: str, minutes: int) -> None:
        self._storage.set_plan(date, minutes)

    def clear_plan(self, date: str) -> None:
        self._storage.clear_plan(date)

    def effective_minutes(self, date: str, holidays: dict[str, str]) -> int:
        """오버라이드가 있으면 그 값, 없으면 주말·공휴일 0, 평일 기본값."""
        override = self._storage.get_plan(date)
        if override is not None:
            return override
        d = datetime.date.fromisoformat(date)
        if d.weekday() >= SATURDAY or date in holidays:
            return 0
        return self._default_getter()

    def month_planned_minutes(
        self, year: int, month: int, holidays: dict[str, str]
    ) -> int:
        last_day = calendar.monthrange(year, month)[1]
        total = 0
        for day in range(1, last_day + 1):
            date = f"{year:04d}-{month:02d}-{day:02d}"
            total += self.effective_minutes(date, holidays)
        return total
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_plan.py -v`
Expected: PASS (평일 수 상수 교정 후)

- [ ] **Step 5: 커밋**

```bash
git add core/plan.py tests/test_plan.py
git commit -m "✨ 유효 계획 근무시간 도출 PlanService 추가"
```

---

### Task 5: 달력 그리드 모델을 core로 이동·계획 반영

기존 `widget/calendar_model.py`(순수 로직)를 `core/calendar_model.py`로 옮기고 `DayCell`에 `planned_minutes`를 추가한다. Qt UI가 순수 모델을 소비하도록 한다.

**Files:**
- Create: `core/calendar_model.py`
- Delete: `widget/calendar_model.py` (이동)
- Modify: `main.py`, `widget/window.py`, `widget/calendar_view.py` (임포트 경로 변경)
- Modify: `tests/test_calendar_model.py` (임포트 경로 변경 + 신규 테스트)

**Interfaces:**
- Consumes: `core.storage.Attendance`, Task 4의 `PlanService.effective_minutes`.
- Produces:
  - `core.calendar_model.DayCell` — 기존 필드 + `planned_minutes: int`
  - `build_month_grid(year, month, today, records, holidays, effective_planned, today_seconds=None) -> list[list[DayCell]]`
    - `effective_planned: Callable[[str], int]` — 날짜→계획분
  - `format_hms(seconds: int | None) -> str` (기존 그대로 이동)
  - `format_hm(minutes: int) -> str` — 신규, 분→"Nh Nm"
  - `required_month_hours(year, month, holidays=None) -> int` (기존 그대로 이동)

- [ ] **Step 1: 파일 이동** — `git mv widget/calendar_model.py core/calendar_model.py`

```bash
git mv widget/calendar_model.py core/calendar_model.py
```

- [ ] **Step 2: 임포트 경로 갱신**

다음 파일들의 임포트를 `widget.calendar_model` → `core.calendar_model` 로 변경:
- `main.py:9-13` — `from widget.calendar_model import (...)` → `from core.calendar_model import (...)`
- `widget/window.py:10` — `from widget.calendar_model import DayCell` → `from core.calendar_model import DayCell`
- `widget/calendar_view.py:8` — `from widget.calendar_model import DayCell, format_hms` → `from core.calendar_model import DayCell, format_hms`
- `tests/test_calendar_model.py` — 상단 임포트 `from widget.calendar_model import ...` → `from core.calendar_model import ...`

- [ ] **Step 3: 실패하는 테스트 작성** — `tests/test_calendar_model.py` 끝에 추가

```python
from core.calendar_model import build_month_grid, format_hm


def test_format_hm():
    assert format_hm(0) == "0h 0m"
    assert format_hm(480) == "8h 0m"
    assert format_hm(150) == "2h 30m"


def test_grid_includes_planned_minutes():
    # effective_planned 콜백이 각 셀 planned_minutes 로 반영되는지
    records = {}
    holidays = {}
    planned = {"2026-07-01": 480, "2026-07-04": 0}
    grid = build_month_grid(
        2026, 7, "2026-07-01", records, holidays,
        effective_planned=lambda d: planned.get(d, 240),
    )
    cells = {c.date: c for week in grid for c in week if c.date}
    assert cells["2026-07-01"].planned_minutes == 480
    assert cells["2026-07-04"].planned_minutes == 0
    assert cells["2026-07-02"].planned_minutes == 240  # 콜백 기본
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `pytest tests/test_calendar_model.py -v`
Expected: FAIL — `format_hm` 없음 / `build_month_grid`에 `effective_planned` 인자 없음

- [ ] **Step 5: `core/calendar_model.py` 수정**

`format_hms` 함수 아래에 추가:

```python
def format_hm(minutes: int) -> str:
    """분을 'Nh Nm' 로 포맷."""
    return f"{minutes // 60}h {minutes % 60}m"
```

`DayCell` 데이터클래스에 필드 추가(맨 끝):

```python
@dataclass
class DayCell:
    day: int
    date: str | None
    is_today: bool
    holiday_name: str | None
    work_seconds: int | None
    is_incomplete: bool
    planned_minutes: int = 0
```

`build_month_grid` 시그니처와 본문 수정:

```python
def build_month_grid(
    year: int,
    month: int,
    today: str,
    records: dict[str, Attendance],
    holidays: dict[str, str],
    effective_planned: "Callable[[str], int] | None" = None,
    today_seconds: int | None = None,
) -> list[list[DayCell]]:
    cal = calendar.Calendar(firstweekday=0)  # 0 = Monday
    grid: list[list[DayCell]] = []
    for week in cal.monthdayscalendar(year, month):
        row: list[DayCell] = []
        for day in week:
            if day == 0:
                row.append(DayCell(0, None, False, None, None, False, 0))
                continue
            date = f"{year:04d}-{month:02d}-{day:02d}"
            rec = records.get(date)
            work_seconds = rec.work_seconds if rec else None
            is_incomplete = rec is not None and rec.clock_out is None
            if date == today and is_incomplete and today_seconds is not None:
                work_seconds = today_seconds
                is_incomplete = False
            planned = effective_planned(date) if effective_planned else 0
            row.append(
                DayCell(
                    day=day,
                    date=date,
                    is_today=(date == today),
                    holiday_name=holidays.get(date),
                    work_seconds=work_seconds,
                    is_incomplete=is_incomplete,
                    planned_minutes=planned,
                )
            )
        grid.append(row)
    return grid
```

상단 임포트에 `Callable` 추가: `from typing import Callable` (파일 상단 임포트 블록).

`main.py`의 `build_month_grid(...)` 호출부(현재 58-60행)는 아직 `effective_planned` 미전달 — 기본 None 이므로 동작 유지(다음 Task에서 교체 예정).

- [ ] **Step 6: 전체 테스트 통과 확인**

Run: `pytest -v`
Expected: PASS (이동·경로변경으로 기존 테스트 포함 전부 통과)

- [ ] **Step 7: 커밋**

```bash
git add -A
git commit -m "♻️ 달력 그리드 모델을 core로 이동하고 계획분 필드 추가"
```

---

### Task 6: `MonthSummary` — 월 현황 집계

status 패널이 소비할 월 계획·실적·진행률·오늘 예상 퇴근을 한 번에 계산한다.

**Files:**
- Create: `core/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: `AttendanceService.month_total_seconds`·`today_in_progress_seconds`, `Storage.get`, `PlanService.effective_minutes`·`month_planned_minutes`, `worktime.raw_seconds_for_net` (Task 1), `timeutil.from_iso`.
- Produces:
  - `@dataclass MonthSummary` 필드: `year:int, month:int, planned_minutes:int, actual_seconds:int, progress_ratio:float|None, expected_clock_out: datetime|None, remaining_seconds:int|None`
  - `build_month_summary(storage, attendance_service, plan_service, year, month, holidays, now) -> MonthSummary`
  - `_MINUTE_SECONDS = 60`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_stats.py` 생성

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from core.stats import build_month_summary

KST = ZoneInfo("Asia/Seoul")


class FakeStorage:
    def __init__(self, rec=None):
        self._rec = rec

    def get(self, date):
        return self._rec


class FakeAttendance:
    def __init__(self, month_seconds=0, in_progress=None):
        self._month = month_seconds
        self._prog = in_progress

    def month_total_seconds(self, y, m):
        return self._month

    def today_in_progress_seconds(self):
        return self._prog


class FakePlan:
    def __init__(self, planned_month, effective):
        self._pm = planned_month
        self._eff = effective

    def month_planned_minutes(self, y, m, holidays):
        return self._pm

    def effective_minutes(self, date, holidays):
        return self._eff


class Rec:
    def __init__(self, clock_in, clock_out=None):
        self.clock_in = clock_in
        self.clock_out = clock_out


def test_actual_includes_in_progress():
    s = build_month_summary(
        FakeStorage(), FakeAttendance(month_seconds=100, in_progress=50),
        FakePlan(9600, 480), 2026, 7, {}, datetime(2026, 7, 1, 12, tzinfo=KST),
    )
    assert s.actual_seconds == 150
    assert s.planned_minutes == 9600


def test_progress_ratio_none_when_planned_zero():
    s = build_month_summary(
        FakeStorage(), FakeAttendance(month_seconds=100),
        FakePlan(0, 0), 2026, 7, {}, datetime(2026, 7, 1, 12, tzinfo=KST),
    )
    assert s.progress_ratio is None


def test_expected_clock_out_from_clock_in_and_plan():
    # 출근 09:00, 계획 480분(8h) → 체류 8h30m → 예상 17:30
    rec = Rec("2026-07-01T09:00:00+09:00", None)
    now = datetime(2026, 7, 1, 12, 0, tzinfo=KST)
    s = build_month_summary(
        FakeStorage(rec), FakeAttendance(in_progress=10800),
        FakePlan(9600, 480), 2026, 7, {}, now,
    )
    assert s.expected_clock_out.hour == 17
    assert s.expected_clock_out.minute == 30
    # 남은시간 = 17:30 - 12:00 = 5h30m
    assert s.remaining_seconds == 5 * 3600 + 30 * 60


def test_expected_none_without_clock_in():
    s = build_month_summary(
        FakeStorage(None), FakeAttendance(),
        FakePlan(9600, 480), 2026, 7, {}, datetime(2026, 7, 1, 12, tzinfo=KST),
    )
    assert s.expected_clock_out is None
    assert s.remaining_seconds is None


def test_expected_none_when_plan_zero():
    rec = Rec("2026-07-04T09:00:00+09:00", None)  # 토요일 계획 0
    s = build_month_summary(
        FakeStorage(rec), FakeAttendance(),
        FakePlan(9600, 0), 2026, 7, {}, datetime(2026, 7, 4, 12, tzinfo=KST),
    )
    assert s.expected_clock_out is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.stats'`

- [ ] **Step 3: 구현** — `core/stats.py` 생성

```python
"""월 근무 현황 집계 (status 패널용)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core import timeutil
from core.worktime import raw_seconds_for_net

_MINUTE_SECONDS = 60


@dataclass
class MonthSummary:
    year: int
    month: int
    planned_minutes: int
    actual_seconds: int
    progress_ratio: float | None
    expected_clock_out: datetime | None
    remaining_seconds: int | None


def build_month_summary(
    storage,
    attendance_service,
    plan_service,
    year: int,
    month: int,
    holidays: dict[str, str],
    now: datetime,
) -> MonthSummary:
    planned_minutes = plan_service.month_planned_minutes(year, month, holidays)
    in_progress = attendance_service.today_in_progress_seconds() or 0
    actual_seconds = attendance_service.month_total_seconds(year, month) + in_progress

    planned_seconds = planned_minutes * _MINUTE_SECONDS
    progress_ratio = (
        actual_seconds / planned_seconds if planned_seconds > 0 else None
    )

    expected, remaining = _today_expectation(
        storage, plan_service, holidays, now
    )
    return MonthSummary(
        year=year,
        month=month,
        planned_minutes=planned_minutes,
        actual_seconds=actual_seconds,
        progress_ratio=progress_ratio,
        expected_clock_out=expected,
        remaining_seconds=remaining,
    )


def _today_expectation(storage, plan_service, holidays, now):
    """오늘 출근 기록+계획이 있으면 (예상 퇴근시각, 남은초) 반환."""
    today = timeutil.today_str(now)
    rec = storage.get(today)
    if rec is None or not rec.clock_in:
        return None, None
    planned_minutes = plan_service.effective_minutes(today, holidays)
    if planned_minutes <= 0:
        return None, None
    clock_in = timeutil.from_iso(rec.clock_in)
    raw = raw_seconds_for_net(planned_minutes * _MINUTE_SECONDS)
    expected = clock_in + timedelta(seconds=raw)
    remaining = int((expected - now).total_seconds())
    return expected, remaining
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_stats.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add core/stats.py tests/test_stats.py
git commit -m "✨ 월 계획·실적·예상 퇴근 집계 MonthSummary 추가"
```

---

### Task 7: PySide6 도입 + Qt 테마 + 앱 스켈레톤

Qt 의존성을 추가하고, 디자인 토큰을 Qt용으로 포팅한 뒤, 빈 전체화면 창을 띄우는 스켈레톤을 만든다.

**Files:**
- Modify: `requirements.txt`
- Create: `ui/__init__.py`, `ui/theme.py`, `ui/app.py`
- Test: 없음(스모크). 단, `ui/theme.py`는 순수 상수라 import 스모크만.

**Interfaces:**
- Produces:
  - `ui/theme.py` — 색상/폰트/치수 상수 (기존 `widget/theme.py` 값 재사용 + Qt 스타일시트 헬퍼)
  - `ui/app.py` — `class AppController` (서비스 조립·모드 전환·refresh·타이머), `def run() -> None`

- [ ] **Step 1: 의존성 추가** — `requirements.txt`

```
requests>=2.31,<3
pytest>=8,<9
PySide6>=6.6,<7
```

설치: `pip install -r requirements.txt`

- [ ] **Step 2: `ui/__init__.py` 생성** (빈 파일)

- [ ] **Step 3: `ui/theme.py` 생성** — 기존 색상 토큰 재사용

```python
"""Qt UI 공통 디자인 토큰 (기존 위젯 팔레트 계승)."""
from __future__ import annotations

# 색상 — 회색 베이스 다크 테마
BG_BASE = "#2b2d31"
BG_ELEVATED = "#3a3d42"
BG_TODAY = "#3b82f6"
BG_HOVER = "#43464c"
BG_PROGRESS = "#4ade80"      # 진행률 바 채움

FG_DATE = "#ffffff"
FG_TIME = "#b6bcc4"
FG_PLANNED = "#8ab4f8"       # 계획 시간 강조 (연파랑)
FG_HOLIDAY = "#ff5a5a"
FG_MUTED = "#9aa0a6"
FG_INCOMPLETE = "#ffd166"
FG_WORKING = "#4ade80"

FONT_FAMILY = "Helvetica"
CELL_MIN_WIDTH = 96
CELL_MIN_HEIGHT = 84

WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 640
STATUS_PANEL_WIDTH = 260


def base_stylesheet() -> str:
    """앱 전역 다크 스타일시트."""
    return f"""
    QWidget {{ background-color: {BG_BASE}; color: {FG_DATE};
               font-family: {FONT_FAMILY}; }}
    QPushButton {{ background-color: {BG_ELEVATED}; border: none;
                   padding: 8px 14px; border-radius: 6px; font-weight: bold; }}
    QPushButton:hover {{ background-color: {BG_HOVER}; }}
    QLabel {{ background: transparent; }}
    """
```

- [ ] **Step 4: `ui/app.py` 스켈레톤 생성**

```python
"""Qt 앱 조립·모드 전환·주기 갱신 컨트롤러."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel

from ui import theme


class AppController:
    def __init__(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyleSheet(theme.base_stylesheet())
        # TODO(Task 11): MainWindow 로 교체
        self._window = QMainWindow()
        self._window.setWindowTitle("근무시간")
        self._window.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)
        self._window.setCentralWidget(QLabel("근무시간 앱 (스켈레톤)"))

    def run(self) -> None:
        self._window.show()
        self._app.exec()


def run() -> None:
    AppController().run()
```

- [ ] **Step 5: 스모크 확인**

Run: `python -c "import ui.theme; import ui.app; print('ok')"`
Expected: `ok` (PySide6 설치 후 import 성공)

수동 확인(선택): `python -c "from ui.app import run; run()"` → 빈 창이 뜨고 닫으면 종료.

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt ui/__init__.py ui/theme.py ui/app.py
git commit -m "🔧 PySide6 도입 및 Qt 테마·앱 스켈레톤 추가"
```

---

### Task 8: status 패널 위젯

월 계획/누적/진행률 바/오늘 예상 퇴근을 표시하는 Qt 위젯.

**Files:**
- Create: `ui/status_panel.py`

**Interfaces:**
- Consumes: `core.stats.MonthSummary`, `core.calendar_model.format_hm`, `core.attendance.WorkStatus`, `ui.theme`.
- Produces:
  - `class StatusPanel(QWidget)`
  - `.update_summary(summary: MonthSummary, status: WorkStatus) -> None`
  - 콜백 인자: `on_clock_out: Callable[[], None]`, `on_cancel_clock_out: Callable[[], None]`

- [ ] **Step 1: `ui/status_panel.py` 생성**

```python
"""캘린더 우측 월 현황 status 패널."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QLabel, QProgressBar, QPushButton, QHBoxLayout,
)

from core.attendance import WorkStatus
from core.calendar_model import format_hm
from core.stats import MonthSummary
from ui import theme

_SECONDS_PER_MINUTE = 60


def _fmt_seconds(seconds: int) -> str:
    minutes = max(seconds, 0) // _SECONDS_PER_MINUTE
    return format_hm(minutes)


class StatusPanel(QWidget):
    def __init__(
        self,
        on_clock_out: Callable[[], None],
        on_cancel_clock_out: Callable[[], None],
    ) -> None:
        super().__init__()
        self.setFixedWidth(theme.STATUS_PANEL_WIDTH)
        self._on_clock_out = on_clock_out
        self._on_cancel_clock_out = on_cancel_clock_out

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._title = QLabel("STATUS")
        self._title.setStyleSheet(f"color:{theme.FG_MUTED}; font-weight:bold;")
        self._planned = QLabel()
        self._actual = QLabel()
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setRange(0, 100)
        self._expected_title = QLabel("오늘 예상 퇴근")
        self._expected_title.setStyleSheet(f"color:{theme.FG_MUTED};")
        self._expected = QLabel()
        self._expected.setStyleSheet(
            f"color:{theme.FG_PLANNED}; font-size:20px; font-weight:bold;"
        )

        for w in (self._title, self._planned, self._actual, self._progress,
                  self._expected_title, self._expected):
            layout.addWidget(w)

        layout.addStretch(1)
        self._buttons = QHBoxLayout()
        layout.addLayout(self._buttons)

    def _clear_buttons(self) -> None:
        while self._buttons.count():
            item = self._buttons.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_buttons(self, status: WorkStatus) -> None:
        self._clear_buttons()
        if status == WorkStatus.CLOCKED_OUT:
            cancel = QPushButton("취소")
            cancel.clicked.connect(lambda: self._on_cancel_clock_out())
            reclock = QPushButton("재퇴근")
            reclock.clicked.connect(lambda: self._on_clock_out())
            self._buttons.addWidget(cancel)
            self._buttons.addWidget(reclock)
        else:
            clock = QPushButton("퇴근")
            clock.clicked.connect(lambda: self._on_clock_out())
            self._buttons.addWidget(clock)

    def update_summary(self, summary: MonthSummary, status: WorkStatus) -> None:
        self._planned.setText(
            f"월 계획   {format_hm(summary.planned_minutes)}"
        )
        self._actual.setText(
            f"월 누적   {_fmt_seconds(summary.actual_seconds)}"
        )
        if summary.progress_ratio is None:
            self._progress.setValue(0)
            self._progress.setFormat("계획 없음")
        else:
            pct = int(summary.progress_ratio * 100)
            self._progress.setValue(min(pct, 100))
            self._progress.setFormat(f"{pct}%")
        if summary.expected_clock_out is None:
            self._expected.setText("-")
        else:
            hhmm = summary.expected_clock_out.strftime("%H:%M")
            remain = summary.remaining_seconds or 0
            suffix = (
                f" ({_fmt_seconds(remain)} 남음)" if remain > 0 else " (초과)"
            )
            self._expected.setText(f"{hhmm}{suffix}")
        self._render_buttons(status)
```

- [ ] **Step 2: 스모크 확인**

Run: `python -c "import ui.status_panel; print('ok')"`
Expected: `ok`

- [ ] **Step 3: 커밋**

```bash
git add ui/status_panel.py
git commit -m "✨ 월 현황 status 패널 위젯 추가"
```

---

### Task 9: 달력 위젯

월 그리드를 Qt로 렌더링하고 셀 클릭 시 날짜 편집 콜백을 호출한다.

**Files:**
- Create: `ui/calendar_widget.py`

**Interfaces:**
- Consumes: `core.calendar_model.DayCell`·`format_hms`·`format_hm`, `ui.theme`.
- Produces:
  - `class CalendarWidget(QWidget)`
  - `.__init__(on_day_click: Callable[[str], None])`
  - `.render_grid(grid: list[list[DayCell]]) -> None`
  - `_WEEKDAYS = ["월","화","수","목","금","토","일"]`, `_SAT_COL = 5`

- [ ] **Step 1: `ui/calendar_widget.py` 생성**

```python
"""월 달력 그리드 Qt 위젯."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QFrame

from core.calendar_model import DayCell, format_hms, format_hm
from ui import theme

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
_SAT_COL = 5


class _DayCellWidget(QFrame):
    def __init__(self, cell: DayCell, on_click: Callable[[str], None]) -> None:
        super().__init__()
        self._date = cell.date
        self._on_click = on_click
        self.setMinimumSize(theme.CELL_MIN_WIDTH, theme.CELL_MIN_HEIGHT)
        is_today = cell.is_today
        bg = theme.BG_TODAY if is_today else theme.BG_ELEVATED
        self.setStyleSheet(
            f"background-color:{bg}; border-radius:6px;"
        )
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)

        date_fg = theme.FG_HOLIDAY if cell.holiday_name else theme.FG_DATE
        date_label = QLabel(str(cell.day))
        date_label.setStyleSheet(
            f"color:{date_fg}; font-size:16px; font-weight:bold;"
        )
        layout.addWidget(date_label)

        if cell.holiday_name:
            name = QLabel(cell.holiday_name)
            name.setStyleSheet(f"color:{theme.FG_HOLIDAY}; font-size:10px;")
            layout.addWidget(name)

        work_text, work_fg = self._work_line(cell)
        if work_text:
            work = QLabel(work_text)
            work.setStyleSheet(f"color:{work_fg}; font-size:11px;")
            layout.addWidget(work)

        if cell.planned_minutes > 0:
            plan = QLabel(f"계획 {format_hm(cell.planned_minutes)}")
            plan.setStyleSheet(f"color:{theme.FG_PLANNED}; font-size:10px;")
            layout.addWidget(plan)

        layout.addStretch(1)

    def _work_line(self, cell: DayCell) -> tuple[str, str]:
        if cell.is_incomplete:
            return "미퇴근", theme.FG_INCOMPLETE
        if cell.work_seconds is None:
            return "", theme.FG_TIME
        return format_hms(cell.work_seconds), theme.FG_TIME

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._date is not None:
            self._on_click(self._date)


class CalendarWidget(QWidget):
    def __init__(self, on_day_click: Callable[[str], None]) -> None:
        super().__init__()
        self._on_day_click = on_day_click
        self._layout = QGridLayout(self)
        self._layout.setSpacing(4)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def render_grid(self, grid: list[list[DayCell]]) -> None:
        self._clear()
        for col, name in enumerate(_WEEKDAYS):
            fg = theme.FG_HOLIDAY if col >= _SAT_COL else theme.FG_MUTED
            head = QLabel(name)
            head.setAlignment(Qt.AlignCenter)
            head.setStyleSheet(f"color:{fg}; font-weight:bold;")
            self._layout.addWidget(head, 0, col)
        for r, week in enumerate(grid, start=1):
            for c, cell in enumerate(week):
                if cell.day == 0:
                    self._layout.addWidget(QWidget(), r, c)
                    continue
                self._layout.addWidget(
                    _DayCellWidget(cell, self._on_day_click), r, c
                )
```

- [ ] **Step 2: 스모크 확인**

Run: `python -c "import ui.calendar_widget; print('ok')"`
Expected: `ok`

- [ ] **Step 3: 커밋**

```bash
git add ui/calendar_widget.py
git commit -m "✨ 월 달력 그리드 Qt 위젯 추가"
```

---

### Task 10: 날짜 편집 다이얼로그 (출퇴근 + 계획)

한 날짜의 계획 근무분과 출퇴근 시각을 함께 편집한다.

**Files:**
- Create: `ui/day_dialog.py`

**Interfaces:**
- Consumes: `widget.edit_dialog.build_iso`(재사용, 순수 함수), `ui.theme`.
- Produces:
  - `open_day_dialog(parent, work_date, clock_in_iso, clock_out_iso, planned_override, default_minutes, on_save_times, on_save_plan) -> None`
    - `on_save_times: Callable[[str, str, str | None], None]` (기존 `edit` 시그니처와 동일)
    - `on_save_plan: Callable[[str, int | None], None]` — `None`이면 오버라이드 해제
  - 상수 `MAX_PLAN_MINUTES = 24 * 60`

- [ ] **Step 1: `ui/day_dialog.py` 생성**

```python
"""날짜별 출퇴근 시각·계획 근무시간 편집 다이얼로그."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QFormLayout,
)

from widget.edit_dialog import build_iso

MAX_PLAN_MINUTES = 24 * 60


def _hhmm_from_iso(iso: Optional[str]) -> str:
    return iso[11:16] if iso else ""


def open_day_dialog(
    parent,
    work_date: str,
    clock_in_iso: Optional[str],
    clock_out_iso: Optional[str],
    planned_override: Optional[int],
    default_minutes: int,
    on_save_times: Callable[[str, str, Optional[str]], None],
    on_save_plan: Callable[[str, Optional[int]], None],
) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{work_date} 편집")
    layout = QVBoxLayout(dlg)

    form = QFormLayout()
    in_edit = QLineEdit(_hhmm_from_iso(clock_in_iso))
    in_edit.setPlaceholderText("HH:MM")
    out_edit = QLineEdit(_hhmm_from_iso(clock_out_iso))
    out_edit.setPlaceholderText("HH:MM (비우면 미퇴근)")
    plan_edit = QLineEdit("" if planned_override is None else str(planned_override))
    plan_edit.setPlaceholderText(f"분 단위 (비우면 기본 {default_minutes}분)")
    form.addRow("출근", in_edit)
    form.addRow("퇴근", out_edit)
    form.addRow("계획(분)", plan_edit)
    layout.addLayout(form)

    buttons = QHBoxLayout()
    cancel = QPushButton("닫기")
    cancel.clicked.connect(dlg.reject)
    save = QPushButton("저장")
    buttons.addWidget(cancel)
    buttons.addWidget(save)
    layout.addLayout(buttons)

    def handle_save() -> None:
        # 1) 계획 저장
        plan_text = plan_edit.text().strip()
        if plan_text == "":
            on_save_plan(work_date, None)  # 오버라이드 해제
        else:
            if not plan_text.isdigit():
                QMessageBox.warning(dlg, "입력 오류", "계획은 0 이상 정수(분)여야 합니다.")
                return
            minutes = int(plan_text)
            if minutes > MAX_PLAN_MINUTES:
                QMessageBox.warning(dlg, "입력 오류", "계획은 하루 24시간을 넘을 수 없습니다.")
                return
            on_save_plan(work_date, minutes)

        # 2) 출퇴근 저장 (출근 입력 시에만)
        in_text = in_edit.text().strip()
        if in_text:
            try:
                clock_in = build_iso(work_date, in_text)
                out_text = out_edit.text().strip()
                clock_out = build_iso(work_date, out_text) if out_text else None
                on_save_times(work_date, clock_in, clock_out)
            except ValueError as exc:
                QMessageBox.warning(dlg, "저장 실패", str(exc))
                return
        dlg.accept()

    save.clicked.connect(handle_save)
    dlg.exec()
```

- [ ] **Step 2: 스모크 확인**

Run: `python -c "import ui.day_dialog; print('ok')"`
Expected: `ok`

- [ ] **Step 3: 커밋**

```bash
git add ui/day_dialog.py
git commit -m "✨ 날짜별 출퇴근·계획 편집 다이얼로그 추가"
```

---

### Task 11: 전체화면 MainWindow + 컨트롤러 배선

캘린더·status·툴바(월 이동·모드 전환)를 조립하고 `AppController`가 서비스와 배선한다.

**Files:**
- Create: `ui/main_window.py`
- Modify: `ui/app.py` (스켈레톤 → 실제 배선)

**Interfaces:**
- Consumes: Task 6~10의 위젯/서비스, `core.attendance.AttendanceService`·`WorkStatus`, `core.plan.PlanService`, `core.stats.build_month_summary`, `core.calendar_model.build_month_grid`, `core.holidays.HolidayClient`, `core.storage.Storage`, `core.timeutil`, `config`.
- Produces:
  - `ui/main_window.py`: `class MainWindow(QMainWindow)` with
    - `.__init__(callbacks: MainWindowCallbacks)`
    - `.render(year, month, status, grid, summary) -> None`
    - `@dataclass MainWindowCallbacks(on_clock_out, on_cancel_clock_out, on_edit_day, on_prev_month, on_next_month, on_switch_mode)`
  - `ui/app.py`: `AppController`에 `_refresh()`, `_tick()`, `_handle_*` 배선 + 분경계 `QTimer`.

- [ ] **Step 1: `ui/main_window.py` 생성**

```python
"""전체화면 메인 윈도우: 캘린더 + status 패널 + 툴바."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QToolBar, QLabel,
)
from PySide6.QtGui import QAction

from core.attendance import WorkStatus
from core.calendar_model import DayCell
from core.stats import MonthSummary
from ui import theme
from ui.calendar_widget import CalendarWidget
from ui.status_panel import StatusPanel

_STATUS_DOT = "●"
_STATUS_COLORS = {
    WorkStatus.WORKING: theme.FG_WORKING,
    WorkStatus.CLOCKED_OUT: theme.FG_MUTED,
    WorkStatus.NOT_CLOCKED_IN: theme.FG_INCOMPLETE,
}


@dataclass
class MainWindowCallbacks:
    on_clock_out: Callable[[], None]
    on_cancel_clock_out: Callable[[], None]
    on_edit_day: Callable[[str], None]
    on_prev_month: Callable[[], None]
    on_next_month: Callable[[], None]
    on_switch_mode: Callable[[], None]


class MainWindow(QMainWindow):
    def __init__(self, callbacks: MainWindowCallbacks) -> None:
        super().__init__()
        self._cb = callbacks
        self.setWindowTitle("근무시간")
        self.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)

        toolbar = QToolBar()
        self.addToolBar(toolbar)
        prev = QAction("◀", self)
        prev.triggered.connect(lambda: self._cb.on_prev_month())
        self._month_label = QLabel("  ")
        nxt = QAction("▶", self)
        nxt.triggered.connect(lambda: self._cb.on_next_month())
        self._status_label = QLabel("")
        switch = QAction("위젯 모드", self)
        switch.triggered.connect(lambda: self._cb.on_switch_mode())
        toolbar.addAction(prev)
        toolbar.addWidget(self._month_label)
        toolbar.addAction(nxt)
        toolbar.addSeparator()
        toolbar.addWidget(self._status_label)
        toolbar.addSeparator()
        toolbar.addAction(switch)

        central = QWidget()
        layout = QHBoxLayout(central)
        self._calendar = CalendarWidget(self._cb.on_edit_day)
        self._status = StatusPanel(
            self._cb.on_clock_out, self._cb.on_cancel_clock_out
        )
        layout.addWidget(self._calendar, stretch=1)
        layout.addWidget(self._status)
        self.setCentralWidget(central)

    def render(
        self,
        year: int,
        month: int,
        status: WorkStatus,
        grid: list[list[DayCell]],
        summary: MonthSummary,
    ) -> None:
        self._month_label.setText(f"  {year}년 {month}월  ")
        self._status_label.setText(f"{_STATUS_DOT} {status.value}")
        self._status_label.setStyleSheet(f"color:{_STATUS_COLORS[status]};")
        self._calendar.render_grid(grid)
        self._status.update_summary(summary, status)
```

- [ ] **Step 2: `ui/app.py` 실제 배선으로 교체**

```python
"""Qt 앱 조립·모드 전환·주기 갱신 컨트롤러."""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import config
from core import timeutil
from core.attendance import AttendanceService
from core.calendar_model import build_month_grid
from core.holidays import HolidayClient
from core.plan import PlanService
from core.stats import build_month_summary
from core.storage import Storage
from ui import theme
from ui.day_dialog import open_day_dialog
from ui.main_window import MainWindow, MainWindowCallbacks

_MINUTE_SECONDS = 60
_SYNC_BUFFER_MS = 100


class AppController:
    def __init__(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyleSheet(theme.base_stylesheet())

        self._storage = Storage(config.db_path())
        self._service = AttendanceService(self._storage)
        self._plans = PlanService(self._storage)
        self._holidays = HolidayClient(
            config.get_service_key(), config.holidays_cache_path()
        )

        now = timeutil.now()
        self._view_year, self._view_month = now.year, now.month

        callbacks = MainWindowCallbacks(
            on_clock_out=self._handle_clock_out,
            on_cancel_clock_out=self._handle_cancel_clock_out,
            on_edit_day=self._handle_edit_day,
            on_prev_month=self._handle_prev_month,
            on_next_month=self._handle_next_month,
            on_switch_mode=self._handle_switch_mode,
        )
        self._window = MainWindow(callbacks)
        self._timer = QTimer(self._window)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)

    # --- 갱신 -----------------------------------------------------------
    def _refresh(self) -> None:
        now = timeutil.now()
        today = timeutil.today_str(now)
        year, month = self._view_year, self._view_month
        records = {r.work_date: r for r in self._storage.list_month(year, month)}
        holidays = self._holidays.get_holidays(year, month)
        is_current = (year, month) == (now.year, now.month)
        today_seconds = (
            self._service.today_in_progress_seconds() if is_current else None
        )
        grid = build_month_grid(
            year, month, today, records, holidays,
            effective_planned=lambda d: self._plans.effective_minutes(d, holidays),
            today_seconds=today_seconds,
        )
        summary = build_month_summary(
            self._storage, self._service, self._plans,
            year, month, holidays, now,
        )
        self._window.render(
            year, month, self._service.today_status(), grid, summary
        )

    def _ms_until_next_minute(self) -> int:
        now = timeutil.now()
        remaining = _MINUTE_SECONDS - now.second - now.microsecond / 1_000_000
        return int(remaining * 1000) + _SYNC_BUFFER_MS

    def _tick(self) -> None:
        self._refresh()
        self._timer.start(self._ms_until_next_minute())

    # --- 핸들러 ---------------------------------------------------------
    def _handle_clock_out(self) -> None:
        try:
            self._service.record_clock_out()
        except ValueError:
            pass
        self._refresh()

    def _handle_cancel_clock_out(self) -> None:
        self._service.cancel_clock_out()
        self._refresh()

    def _handle_prev_month(self) -> None:
        self._view_year, self._view_month = _prev_month(
            self._view_year, self._view_month
        )
        self._refresh()

    def _handle_next_month(self) -> None:
        self._view_year, self._view_month = _next_month(
            self._view_year, self._view_month
        )
        self._refresh()

    def _handle_switch_mode(self) -> None:
        # Task 12 에서 위젯 모드 전환 구현. 지금은 상태만 저장.
        config.set_last_mode(config.MODE_WIDGET)

    def _handle_edit_day(self, date: str) -> None:
        rec = self._storage.get(date)
        open_day_dialog(
            self._window,
            date,
            rec.clock_in if rec else None,
            rec.clock_out if rec else None,
            self._plans.get_override(date),
            config.get_default_daily_minutes(),
            self._handle_save_times,
            self._handle_save_plan,
        )
        self._refresh()

    def _handle_save_times(self, work_date, clock_in_iso, clock_out_iso) -> None:
        self._service.edit(work_date, clock_in_iso, clock_out_iso)

    def _handle_save_plan(self, work_date, minutes) -> None:
        if minutes is None:
            self._plans.clear_plan(work_date)
        else:
            self._plans.set_plan(work_date, minutes)

    # --- 실행 -----------------------------------------------------------
    def run(self) -> None:
        self._service.record_clock_in()  # 부팅 = 자동 출근 (기존 동작 유지)
        self._refresh()
        self._window.show()
        self._timer.start(self._ms_until_next_minute())
        self._app.exec()


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def run() -> None:
    AppController().run()
```

- [ ] **Step 3: 월 이동 헬퍼 단위 테스트** — `tests/test_app_navigation.py` 생성

```python
from ui.app import _prev_month, _next_month


def test_prev_month_wraps_year():
    assert _prev_month(2026, 1) == (2025, 12)
    assert _prev_month(2026, 7) == (2026, 6)


def test_next_month_wraps_year():
    assert _next_month(2026, 12) == (2027, 1)
    assert _next_month(2026, 7) == (2026, 8)
```

Run: `pytest tests/test_app_navigation.py -v`
Expected: PASS

- [ ] **Step 4: 수동 스모크**

Run: `python main.py` (Task 13에서 main.py 배선 후) 또는 임시로 `python -c "from ui.app import run; run()"`
Expected: 전체화면 창에 이번 달 달력 + 우측 status 패널. 날짜 클릭 시 편집 다이얼로그. 월 ◀▶ 이동. 매 분 경계에 오늘 셀·누적 갱신.

- [ ] **Step 5: 커밋**

```bash
git add ui/main_window.py ui/app.py tests/test_app_navigation.py
git commit -m "✨ 전체화면 메인 윈도우·컨트롤러 배선"
```

---

### Task 12: 위젯 모드 + 모드 전환

축약 위젯 창을 Qt로 만들고, 전체화면 ↔ 위젯을 같은 컨트롤러에서 전환한다.

**Files:**
- Create: `ui/widget_window.py`
- Modify: `ui/app.py` (모드 전환 로직)

**Interfaces:**
- Consumes: `core.stats.MonthSummary`, `core.attendance.WorkStatus`, `core.calendar_model.format_hms`, `ui.theme`, `config` 창 위치.
- Produces:
  - `ui/widget_window.py`: `class WidgetWindow(QWidget)` — 프레임리스·always-on-top
    - `.__init__(callbacks: WidgetCallbacks)`
    - `.render(status, header_text, expected_text) -> None`
    - `@dataclass WidgetCallbacks(on_clock_out, on_cancel_clock_out, on_switch_mode, on_close)`
  - `ui/app.py`: `_show_mode(mode)` 로 두 창 전환, 시작 시 `config.get_last_mode()` 반영.

- [ ] **Step 1: `ui/widget_window.py` 생성**

```python
"""축약 위젯 모드 창 (프레임리스·always-on-top)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

import config
from core.attendance import WorkStatus
from ui import theme

_STATUS_DOT = "●"
_STATUS_COLORS = {
    WorkStatus.WORKING: theme.FG_WORKING,
    WorkStatus.CLOCKED_OUT: theme.FG_MUTED,
    WorkStatus.NOT_CLOCKED_IN: theme.FG_INCOMPLETE,
}


@dataclass
class WidgetCallbacks:
    on_clock_out: Callable[[], None]
    on_cancel_clock_out: Callable[[], None]
    on_switch_mode: Callable[[], None]
    on_close: Callable[[], None]


class WidgetWindow(QWidget):
    def __init__(self, callbacks: WidgetCallbacks) -> None:
        super().__init__()
        self._cb = callbacks
        self._drag_offset = QPoint()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setStyleSheet(f"background-color:{theme.BG_BASE}; border-radius:8px;")
        pos = config.get_window_pos()
        if pos:
            self.move(pos[0], pos[1])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        top = QHBoxLayout()
        self._status = QLabel()
        expand = QPushButton("전체")
        expand.clicked.connect(lambda: self._cb.on_switch_mode())
        close = QPushButton("✕")
        close.clicked.connect(lambda: self._cb.on_close())
        top.addWidget(self._status)
        top.addStretch(1)
        top.addWidget(expand)
        top.addWidget(close)
        layout.addLayout(top)

        self._header = QLabel()
        self._expected = QLabel()
        self._expected.setStyleSheet(f"color:{theme.FG_PLANNED};")
        layout.addWidget(self._header)
        layout.addWidget(self._expected)

        self._clock_btn = QPushButton("퇴근")
        self._clock_btn.clicked.connect(lambda: self._cb.on_clock_out())
        layout.addWidget(self._clock_btn)

    def render(self, status: WorkStatus, header_text: str, expected_text: str) -> None:
        self._status.setText(f"{_STATUS_DOT} {status.value}")
        self._status.setStyleSheet(f"color:{_STATUS_COLORS[status]};")
        self._header.setText(header_text)
        self._expected.setText(expected_text)

    # 드래그 이동 + 위치 저장
    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        config.save_window_pos(self.x(), self.y())
```

- [ ] **Step 2: `ui/app.py` 모드 전환 배선**

`AppController.__init__` 끝(타이머 생성 뒤)에 위젯 창 생성 추가:

```python
        from ui.widget_window import WidgetWindow, WidgetCallbacks
        self._widget = WidgetWindow(WidgetCallbacks(
            on_clock_out=self._handle_clock_out,
            on_cancel_clock_out=self._handle_cancel_clock_out,
            on_switch_mode=lambda: self._show_mode(config.MODE_FULL),
            on_close=self._app.quit,
        ))
        self._mode = config.get_last_mode()
```

`_handle_switch_mode` 를 교체:

```python
    def _handle_switch_mode(self) -> None:
        self._show_mode(config.MODE_WIDGET)

    def _show_mode(self, mode: str) -> None:
        self._mode = mode
        config.set_last_mode(mode)
        if mode == config.MODE_WIDGET:
            self._window.hide()
            self._widget.show()
        else:
            self._widget.hide()
            self._window.show()
        self._refresh()
```

`_refresh` 끝에 위젯 렌더 추가(전체화면 render 뒤):

```python
        self._render_widget(summary, self._service.today_status())
```

그리고 메서드 추가:

```python
    def _render_widget(self, summary, status) -> None:
        from core.calendar_model import format_hms
        in_prog = self._service.today_in_progress_seconds()
        header = f"오늘 {format_hms(in_prog)}" if in_prog is not None else "오늘 -"
        if summary.expected_clock_out is None:
            expected = "예상 퇴근 -"
        else:
            expected = f"예상 퇴근 {summary.expected_clock_out.strftime('%H:%M')}"
        self._widget.render(status, header, expected)
```

`run()` 의 `self._window.show()` 를 모드 반영으로 교체:

```python
        self._show_mode(config.get_last_mode())
```
(기존 `self._window.show()` 한 줄 삭제)

- [ ] **Step 3: 스모크 확인**

Run: `python -c "import ui.widget_window; import ui.app; print('ok')"`
Expected: `ok`

수동: 앱 실행 → "위젯 모드" 클릭 → 축약 창으로 전환·드래그 이동·"전체" 클릭 복귀. 재실행 시 마지막 모드 유지.

- [ ] **Step 4: 커밋**

```bash
git add ui/widget_window.py ui/app.py
git commit -m "✨ Qt 위젯 모드 및 전체화면 전환 지원"
```

---

### Task 13: 진입점 전환 + 기존 tkinter 제거

`main.py`를 Qt 앱으로 전환하고, 검증 완료된 tkinter `widget/`을 제거한다.

**Files:**
- Modify: `main.py`
- Delete: `widget/window.py`, `widget/calendar_view.py`, `widget/theme.py`, `widget/__init__.py`
- Keep: `widget/edit_dialog.py`의 `build_iso`는 `ui/day_dialog`가 사용 → **이동** 필요.
- Modify: `README.md` (실행법·의존성 갱신)
- Modify: `tests/test_edit_dialog.py` (임포트 경로 갱신)

**Interfaces:**
- Produces: `main.py:main()` → `ui.app.run()`. `core/timefmt.py`(신규)로 `build_iso` 이동.

- [ ] **Step 1: `build_iso`를 core로 이동** — `core/timefmt.py` 생성

```python
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
```

`ui/day_dialog.py`의 임포트를 `from widget.edit_dialog import build_iso` → `from core.timefmt import build_iso` 로 변경.

`tests/test_edit_dialog.py`의 `build_iso` 임포트를 `from core.timefmt import build_iso` 로 변경(해당 테스트만 남기고 tkinter 의존 테스트가 있으면 제거).

- [ ] **Step 2: `main.py` 교체**

```python
"""근무시간 앱 진입점."""
from __future__ import annotations

from ui.app import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: tkinter 위젯 제거**

```bash
git rm widget/window.py widget/calendar_view.py widget/theme.py widget/edit_dialog.py widget/__init__.py
```

`widget/` 디렉터리가 비면 삭제. (`core/calendar_model.py`는 Task 5에서 이미 이동됨)

- [ ] **Step 4: 전체 테스트 통과 확인**

Run: `pytest -v`
Expected: PASS (tkinter 의존 제거 후 core/ui 순수 테스트 전부 통과)

- [ ] **Step 5: README 갱신**

`README.md`의 실행법을 `python main.py`(PySide6 필요)로, 의존성에 `PySide6` 추가. 위젯/전체화면 모드 전환 안내 한 줄 추가.

- [ ] **Step 6: 수동 스모크 (최종)**

Run: `python main.py`
Expected: 전체화면 앱 실행 → 자동 출근 → 달력·status·계획 편집·예상 퇴근·모드 전환 정상.

- [ ] **Step 7: 커밋**

```bash
git add -A
git commit -m "🔥 tkinter 위젯 제거하고 Qt 앱으로 진입점 전환"
```

---

## 자기 점검 (작성자 확인 완료)

- **스펙 커버리지**: 계획 저장(Task 2·4·10) · 예상 퇴근 산정(Task 1·6·8) · status 패널 지표 4종(Task 6·8) · 모드 전환(Task 11·12) · 자동 출근 유지(Task 11 `run`) 모두 태스크 존재.
- **타입 일관성**: `effective_minutes(date, holidays)`, `build_month_summary(...now)`, `build_month_grid(..., effective_planned=, today_seconds=)`, `MainWindowCallbacks`/`WidgetCallbacks` 시그니처가 소비처와 일치.
- **플레이스홀더**: Task 7·11의 `TODO`는 후속 태스크에서 실제 코드로 대체되도록 명시(잔여 없음).
- **주의점**: Task 4·5의 "평일 수 23"은 실행 시 `calendar`로 검증·교정. Qt UI 태스크는 순수 로직이 아니므로 import 스모크 + 수동 확인으로 검증.
