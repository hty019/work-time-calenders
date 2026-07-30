# 임의 휴게시간 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) 구문으로 추적한다.

**Goal:** 날짜별 임의 휴게시간(분)을 저장·차감·표시한다. 자동 임계-정지 휴게에 가산되는 별도 차감이며, 예상 퇴근 계산에는 반영하지 않는다.

**Architecture:** 기존 부속 테이블 패턴(plan/memo/vacation)을 그대로 따른다. storage 에 `extra_break` 테이블 → `AttendanceService._work_seconds` 공통 경로에서 차감 → `DayDetail` 로 STATUS 패널에 노출 → 편집 다이얼로그에 입력 필드.

**Tech Stack:** Python 3 / PySide6 / SQLite / pytest. 반드시 `./venv/bin/pytest` 사용.

## Global Constraints

- 표기: 1h 미만 `45m`, 1h 이상 `1h 30m`, 정시 0m 생략 `1h` (스펙 확정).
- 예상 퇴근·남은 시간에는 반영하지 않는다 (표시·집계만).
- 차감 하한 0 (`max(0, ...)`).
- 다이얼로그 입력: 0 이상 정수(분), 상한 1440분(24h). 비우거나 0 → 해제.
- 커밋 메시지는 한글 + 이모지 prefix (✨🐛🔧📝♻️🔥💄).
- UI(Qt 위젯) 시각 확인은 헤드리스에서 불가 — 로직·임포트 검증까지만.

---

### Task 1: storage — extra_break 테이블·CRUD

**Files:**
- Modify: `core/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces: `Storage.get_extra_break(work_date: str) -> int | None`,
  `Storage.set_extra_break(work_date: str, minutes: int) -> None`,
  `Storage.clear_extra_break(work_date: str) -> None`,
  `Storage.list_extra_break_month(year: int, month: int) -> dict[str, int]`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_storage.py` 끝에 추가 (기존 fixture 패턴 확인 후 동일하게):

```python
def test_extra_break_crud(storage):
    assert storage.get_extra_break("2026-07-30") is None
    storage.set_extra_break("2026-07-30", 45)
    assert storage.get_extra_break("2026-07-30") == 45
    storage.set_extra_break("2026-07-30", 90)  # upsert 갱신
    assert storage.get_extra_break("2026-07-30") == 90
    storage.clear_extra_break("2026-07-30")
    assert storage.get_extra_break("2026-07-30") is None
    storage.clear_extra_break("2026-07-30")  # 없는 날짜 clear 는 무해


def test_extra_break_list_month(storage):
    storage.set_extra_break("2026-07-05", 30)
    storage.set_extra_break("2026-07-20", 60)
    storage.set_extra_break("2026-08-01", 15)  # 다른 달 제외 확인
    assert storage.list_extra_break_month(2026, 7) == {
        "2026-07-05": 30,
        "2026-07-20": 60,
    }
```

(기존 test_storage.py 의 storage fixture 이름·생성 방식과 다르면 그에 맞춘다.)

- [ ] **Step 2: 실패 확인** — `./venv/bin/pytest tests/test_storage.py -q` → AttributeError 로 FAIL
- [ ] **Step 3: 구현** — `core/storage.py`:

`_CREATE_MEMO_SQL` 아래에 추가:

```python
_CREATE_EXTRA_BREAK_SQL = """
CREATE TABLE IF NOT EXISTS extra_break (
    work_date TEXT PRIMARY KEY,
    minutes   INTEGER NOT NULL
)
"""
```

`__init__` 의 execute 목록에 `self._conn.execute(_CREATE_EXTRA_BREAK_SQL)` 추가 (commit 이전).

메서드 (memo/plan 패턴, `get_memo` 근처에 배치):

```python
    def get_extra_break(self, work_date: str) -> int | None:
        """해당 날짜의 임의 휴게(분). 없으면 None."""
        cur = self._conn.execute(
            "SELECT minutes FROM extra_break WHERE work_date = ?",
            (work_date,),
        )
        row = cur.fetchone()
        return int(row["minutes"]) if row is not None else None

    def set_extra_break(self, work_date: str, minutes: int) -> None:
        self._conn.execute(
            "INSERT INTO extra_break (work_date, minutes) VALUES (?, ?) "
            "ON CONFLICT(work_date) DO UPDATE SET minutes=excluded.minutes",
            (work_date, minutes),
        )
        self._conn.commit()

    def clear_extra_break(self, work_date: str) -> None:
        self._conn.execute(
            "DELETE FROM extra_break WHERE work_date = ?", (work_date,)
        )
        self._conn.commit()

    def list_extra_break_month(self, year: int, month: int) -> dict[str, int]:
        prefix = f"{year:04d}-{month:02d}-"
        cur = self._conn.execute(
            "SELECT work_date, minutes FROM extra_break "
            "WHERE work_date LIKE ? ORDER BY work_date",
            (prefix + "%",),
        )
        return {r["work_date"]: int(r["minutes"]) for r in cur.fetchall()}
```

- [ ] **Step 4: 통과 확인** — `./venv/bin/pytest tests/test_storage.py -q` → PASS
- [ ] **Step 5: 커밋** — `git add core/storage.py tests/test_storage.py && git commit -m "✨ 임의 휴게 extra_break 테이블·CRUD 추가"`

---

### Task 2: timefmt — format_break 표기 함수

**Files:**
- Modify: `core/timefmt.py`
- Test: `tests/test_timeutil.py` (timefmt 테스트가 별도 파일이면 그 파일; 없으면 `tests/test_timeutil.py` 에 추가)

**Interfaces:**
- Produces: `format_break(minutes: int) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**:

```python
import pytest

from core.timefmt import format_break


@pytest.mark.parametrize(
    "minutes,expected",
    [
        (0, "0m"),
        (45, "45m"),
        (59, "59m"),
        (60, "1h"),
        (61, "1h 1m"),
        (90, "1h 30m"),
        (120, "2h"),
    ],
)
def test_format_break(minutes, expected):
    assert format_break(minutes) == expected
```

- [ ] **Step 2: 실패 확인** — `./venv/bin/pytest tests/test_timeutil.py -q` → ImportError 로 FAIL
- [ ] **Step 3: 구현** — `core/timefmt.py` 에 추가:

```python
_MINUTES_PER_HOUR = 60


def format_break(minutes: int) -> str:
    """임의 휴게 표기. 1h 미만 '45m', 1h 이상 '1h 30m', 정시는 '1h'."""
    if minutes < _MINUTES_PER_HOUR:
        return f"{minutes}m"
    hours, rest = divmod(minutes, _MINUTES_PER_HOUR)
    if rest == 0:
        return f"{hours}h"
    return f"{hours}h {rest}m"
```

- [ ] **Step 4: 통과 확인** — PASS
- [ ] **Step 5: 커밋** — `git commit -m "✨ 임의 휴게 표기 format_break 추가"`

---

### Task 3: attendance — 근무초 차감

**Files:**
- Modify: `core/attendance.py` (`_work_seconds`)
- Test: `tests/test_attendance.py`

**Interfaces:**
- Consumes: `Storage.get_extra_break` (Task 1)
- Produces: `_work_seconds` 결과가 임의 휴게분만큼 감소 (모든 쓰기 경로 + `today_in_progress_seconds` 공통)

- [ ] **Step 1: 실패하는 테스트 작성** — 기존 test_attendance.py 의 fixture(가짜 clock, 임시 storage) 패턴을 따라:

```python
def test_clock_out_deducts_extra_break(...):
    # 09:00 출근, 12:00 퇴근 → raw 3h (자동 휴게 없음)
    # 임의 휴게 30분 설정 → 근무 2h 30m
    storage.set_extra_break(date, 30)
    ...
    assert rec.work_seconds == 3 * 3600 - 30 * 60


def test_extra_break_floor_zero(...):
    # raw 10분, 임의 휴게 30분 → 0 (음수 금지)
    storage.set_extra_break(date, 30)
    ...
    assert rec.work_seconds == 0
```

(record_clock_out 경로로 검증. edit/recompute/in-progress 는 동일 `_work_seconds` 공유 — recompute_work 경로 1건 추가 검증.)

- [ ] **Step 2: 실패 확인** — FAIL (차감 없음)
- [ ] **Step 3: 구현** — `core/attendance.py` `_work_seconds` 를:

```python
    def _work_seconds(self, date: str, clock_in, clock_out) -> int:
        """휴가·임의 휴게를 반영한 근무 초 (모든 쓰기 경로 공통).

        1day 휴가일은 출퇴근을 무시하고 근로 0 (인정은 휴가 8h 로 고정).
        시간제 휴가는 겹치는 구간을 제외한다. 임의 휴게는 자동 임계-정지
        휴게와 별도로 추가 차감한다 (하한 0).
        """
        base = self._base_work_seconds(date, clock_in, clock_out)
        extra_minutes = self._storage.get_extra_break(date) or 0
        return max(0, base - extra_minutes * 60)

    def _base_work_seconds(self, date: str, clock_in, clock_out) -> int:
        row = self._storage.get_vacation(date)
        if row is None:
            return effective_work_seconds(clock_in, clock_out)
        minutes, start_min, end_min = row
        if minutes >= FULL_DAY_MINUTES:
            return 0
        return effective_work_seconds(clock_in, clock_out, start_min, end_min)
```

- [ ] **Step 4: 전체 테스트 통과 확인** — `./venv/bin/pytest -q`
- [ ] **Step 5: 커밋** — `git commit -m "✨ 근무초 계산에 임의 휴게 차감 반영"`

---

### Task 4: day_detail — break_minutes 필드

**Files:**
- Modify: `core/day_detail.py`
- Test: `tests/test_day_detail.py`

**Interfaces:**
- Consumes: `Storage.get_extra_break` (Task 1)
- Produces: `DayDetail.break_minutes: int | None` (기본 None)

- [ ] **Step 1: 실패하는 테스트 작성** — 기존 build_day_detail 헬퍼 패턴으로:

```python
def test_day_detail_break_minutes(...):
    storage.set_extra_break(date, 45)
    detail = ...  # 기존 헬퍼 호출
    assert detail.break_minutes == 45


def test_day_detail_break_minutes_none(...):
    detail = ...
    assert detail.break_minutes is None
```

- [ ] **Step 2: 실패 확인** — FAIL
- [ ] **Step 3: 구현** — `DayDetail` 에 `break_minutes: int | None = None` 필드 추가 (`work_seconds` 아래), `build_day_detail` 반환에 `break_minutes=storage.get_extra_break(date),` 추가.
- [ ] **Step 4: 통과 확인** — PASS
- [ ] **Step 5: 커밋** — `git commit -m "✨ DayDetail 에 임의 휴게 분 필드 추가"`

---

### Task 5: status_panel — 휴게 라인 표시

**Files:**
- Modify: `ui/status_panel.py`
- Test: `tests/test_status_panel.py`

**Interfaces:**
- Consumes: `DayDetail.break_minutes` (Task 4), `format_break` (Task 2)
- Produces: `break_line(detail: DayDetail) -> str | None` — None 이면 숨김

- [ ] **Step 1: 실패하는 테스트 작성** — 기존 test_status_panel.py 의 라인 함수 테스트 패턴으로 (DayDetail 생성 헬퍼 재사용):

```python
def test_break_line_none():
    assert break_line(_detail(break_minutes=None)) is None


def test_break_line_minutes_only():
    assert break_line(_detail(break_minutes=45)) == "휴게 시간: 45m"


def test_break_line_hours():
    assert break_line(_detail(break_minutes=90)) == "휴게 시간: 1h 30m"
```

- [ ] **Step 2: 실패 확인** — FAIL
- [ ] **Step 3: 구현** — `ui/status_panel.py`:

`vacation_line` 아래에:

```python
def break_line(detail: DayDetail) -> str | None:
    """임의 휴게 라인. 미설정이면 None(숨김)."""
    if detail.break_minutes is None:
        return None
    return f"휴게 시간: {format_break(detail.break_minutes)}"
```

임포트: `from core.timefmt import format_break`

`StatusPanel.__init__` 에 `_vacation` 라벨 아래:

```python
        self._break = QLabel()      # 임의 휴게 라인 (없으면 숨김)
        self._break.setVisible(False)
```

위젯 순서 튜플에서 `self._vacation` 과 `self._state` 사이에 `self._break` 삽입 (상태 라인 바로 위).

`update_summary` 의 vacation 처리 아래:

```python
        brk_text = break_line(detail) if detail is not None else None
        self._break.setText(brk_text or "")
        self._break.setVisible(bool(brk_text))
```

- [ ] **Step 4: 통과 확인** — `./venv/bin/pytest -q`
- [ ] **Step 5: 커밋** — `git commit -m "✨ STATUS 에 임의 휴게 라인 표시"`

---

### Task 6: day_dialog — 휴게(분) 입력 + app 배선

**Files:**
- Modify: `ui/day_dialog.py`, `ui/app.py`
- Test: `tests/test_edit_dialog.py` (파싱 헬퍼만; Qt 렌더링 검증 제외)

**Interfaces:**
- Consumes: `format_break` (Task 2), `Storage.set/clear_extra_break` (Task 1), `AttendanceService.recompute_work`
- Produces: `parse_break_input(text: str) -> int | None` (ValueError 발생 가능),
  `open_day_dialog(..., break_minutes: Optional[int] = None, on_save_break: Optional[Callable[[str, Optional[int]], None]] = None)` 파라미터,
  `App._handle_save_break(work_date: str, minutes: int | None)`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_edit_dialog.py`:

```python
import pytest

from ui.day_dialog import parse_break_input


def test_parse_break_empty_is_none():
    assert parse_break_input("") is None
    assert parse_break_input("  ") is None


def test_parse_break_zero_is_none():
    assert parse_break_input("0") is None


def test_parse_break_minutes():
    assert parse_break_input("45") == 45


def test_parse_break_invalid():
    with pytest.raises(ValueError):
        parse_break_input("abc")
    with pytest.raises(ValueError):
        parse_break_input("-5")
    with pytest.raises(ValueError):
        parse_break_input("1441")
```

- [ ] **Step 2: 실패 확인** — FAIL
- [ ] **Step 3: 구현** — `ui/day_dialog.py`:

상수: `MAX_BREAK_MINUTES = 24 * 60` (기존 `MAX_PLAN_MINUTES` 근처).

```python
def parse_break_input(text: str) -> Optional[int]:
    """휴게(분) 입력 파싱. 비우거나 0 이면 None(해제), 오류 시 ValueError."""
    text = text.strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError("휴게는 0 이상 정수(분)여야 합니다.")
    minutes = int(text)
    if minutes > MAX_BREAK_MINUTES:
        raise ValueError("휴게는 하루 24시간을 넘을 수 없습니다.")
    return minutes if minutes > 0 else None
```

보기 모드 표시 함수 (`vacation_display` 아래):

```python
def break_display(minutes: Optional[int]) -> str:
    """보기 모드 휴게 텍스트. 미설정이면 '-'."""
    return format_break(minutes) if minutes is not None else "-"
```

임포트: `from core.timefmt import build_iso, format_break` 로 병합.

`open_day_dialog` 파라미터 추가 (memo 앞):
`break_minutes: Optional[int] = None, on_save_break: Optional[Callable[[str, Optional[int]], None]] = None,`

- 초기값: `initial_break_text = "" if break_minutes is None else str(break_minutes)`
- 보기 폼: `view_form.addRow("휴게", QLabel(break_display(break_minutes)))` — 휴가 행 아래
- 수정 폼: 휴가 시작 행 아래

```python
    break_edit = QLineEdit(initial_break_text)
    break_edit.setPlaceholderText("분 단위 (비우면 없음)")
    form.addRow("휴게(분)", break_edit)
```

- `handle_save` 3)과 4) 사이에 파싱·검증:

```python
        # 3.5) 임의 휴게 파싱 (비우거나 0 → 해제)
        try:
            new_break = parse_break_input(break_edit.text())
        except ValueError as exc:
            QMessageBox.warning(dlg, "입력 오류", str(exc))
            return
```

- 4) 저장 블록에 (`on_save_memo` 근처):

```python
        if on_save_break is not None:
            on_save_break(work_date, new_break)
```

`ui/app.py`:

- `_handle_edit_selected` 의 open_day_dialog 호출에 `break_minutes=self._storage.get_extra_break(date),` `on_save_break=self._handle_save_break,` 추가.
- `_handle_save_vacation` 아래 핸들러 추가:

```python
    def _handle_save_break(self, work_date: str, minutes: int | None) -> None:
        if minutes is None:
            self._storage.clear_extra_break(work_date)
        else:
            self._storage.set_extra_break(work_date, minutes)
        # 휴게 변경은 저장된 근무초에 영향 → 즉시 재계산
        self._service.recompute_work(work_date)
```

- [ ] **Step 4: 전체 테스트 통과 + 임포트 검증** — `./venv/bin/pytest -q` 및 `./venv/bin/python -c "import ui.app, ui.day_dialog, ui.status_panel"`
- [ ] **Step 5: 커밋** — `git commit -m "✨ 편집 다이얼로그 휴게(분) 입력·저장 배선"`

---

### Task 7: 마무리 — 위젯 재시작·시각 확인 요청

- [ ] **Step 1:** `./venv/bin/pytest -q` 전체 통과 재확인
- [ ] **Step 2:** `./run.sh stop && ./run.sh` 로 위젯 재시작
- [ ] **Step 3:** 사용자에게 STATUS 휴게 라인·다이얼로그 필드 시각 확인 요청
