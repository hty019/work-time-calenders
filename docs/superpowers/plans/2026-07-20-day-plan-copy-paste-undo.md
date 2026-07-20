# 일자 계획 복사/붙여넣기 · 통합 Undo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선택 일자의 실계획·(가)계획을 다른 일자에 복사/붙여넣기(Cmd/Ctrl+C·V)하고, 모든 일자 데이터 변경을 마지막 1회 한정 되돌리기(Cmd/Ctrl+Z)한다.

**Architecture:** 되돌리기·복사 로직 전체를 Qt 비의존 `core/day_state.py`(DayState 스냅샷, 복사 버퍼, 순수 헬퍼)로 분리해 TDD 한다. `ui/app.py` 컨트롤러는 `_with_undo` 래퍼로 기존 편집 핸들러를 감싸고, `ui/main_window.py`는 QShortcut 만 등록한다.

**Tech Stack:** Python 3, PySide6/Qt, SQLite(core.storage), pytest.

## Global Constraints

- 실행/테스트는 시스템 python 이 아니라 반드시 `./venv/bin/python`, `./venv/bin/pytest` 사용.
- 매직 넘버 금지 — 상수/기존 도메인 값 사용. 색상·크기는 `ui/theme.py` 토큰.
- core 로직은 TDD. GUI 렌더링은 헤드리스에서 검증 불가 → 로직·임포트 검증까지만, 시각 확인은 사용자 요청.
- 커밋 메시지 한글, prefix 이모지(✨🐛🔧📝♻️🔥, UI 스타일 💄). 한 커밋 = 한 논리 단위.
- 되돌리기는 **단일 단계**(마지막 1회). 붙여넣기는 자기정합적 복제이므로 **재검증 생략**.
- Qt 가 macOS 에서 `QKeySequence("Ctrl+X")` 를 Cmd 키로 매핑함 — 물리 Ctrl 키는 `Qt.MetaModifier` 로 별도 등록.

## File Structure

- Create: `core/day_state.py` — `DayState`, `DayPlanClipboard`, `snapshot_day`, `restore_day`, `paste_targets`, `apply_clipboard` (Qt 비의존).
- Create: `tests/test_day_state.py` — 위 core 로직 단위 테스트.
- Modify: `ui/app.py` — 클립보드/undo 상태, `_with_undo`, copy/paste/undo 핸들러, 기존 5개 편집 핸들러 래핑, 콜백 배선, `QMessageBox` import.
- Modify: `ui/main_window.py` — `MainWindowCallbacks` 필드 3개 추가, Cmd/Ctrl+C·V·Z QShortcut 등록.
- Modify: `ui/help_dialog.py` — "셀 선택 · 단축키" 페이지에 복사/붙여넣기/되돌리기 안내 추가.

---

### Task 1: core/day_state.py — 스냅샷·복사 순수 로직 (TDD)

**Files:**
- Create: `core/day_state.py`
- Test: `tests/test_day_state.py`

**Interfaces:**
- Consumes: `core.storage.Attendance`/`Storage`, `core.plan.PlanService`, `core.recognition.RecognitionRange`/`RecognitionService`, `core.vacation.Vacation`/`VacationService`.
- Produces:
  - `DayState(date: str, record: Attendance | None, plan_override: int | None, recog: RecognitionRange | None, vacation: Vacation | None, memo: str | None)` (frozen dataclass)
  - `DayPlanClipboard(plan_minutes: int, recog: RecognitionRange | None)` (frozen dataclass)
  - `snapshot_day(storage, plans, recog, vacations, date: str) -> DayState`
  - `restore_day(storage, recog, vacations, state: DayState) -> None`
  - `paste_targets(selected_date: str, multi_dates: list[str]) -> list[str]`
  - `apply_clipboard(storage, recog, clipboard: DayPlanClipboard, dates: list[str]) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_day_state.py`:

```python
from core.day_state import (
    DayPlanClipboard,
    apply_clipboard,
    paste_targets,
    restore_day,
    snapshot_day,
)
from core.plan import PlanService
from core.recognition import RecognitionRange, RecognitionService
from core.storage import Attendance, Storage
from core.vacation import Vacation, VacationService


def make_services(tmp_path):
    storage = Storage(str(tmp_path / "db.db"))
    plans = PlanService(storage, default_minutes_getter=lambda: 480)
    recog = RecognitionService(storage)
    vacations = VacationService(storage)
    return storage, plans, recog, vacations


def test_paste_targets_single_uses_selected():
    assert paste_targets("2026-07-10", []) == ["2026-07-10"]


def test_paste_targets_multi_uses_full_list():
    dates = ["2026-07-10", "2026-07-11", "2026-07-12"]
    assert paste_targets("2026-07-12", dates) == dates


def test_apply_clipboard_sets_plan_and_recog(tmp_path):
    storage, _plans, recog, _vac = make_services(tmp_path)
    clip = DayPlanClipboard(plan_minutes=420, recog=RecognitionRange(540, 1080))
    apply_clipboard(storage, recog, clip, ["2026-07-10", "2026-07-11"])
    assert storage.get_plan("2026-07-10") == 420
    assert recog.get("2026-07-11") == RecognitionRange(540, 1080)


def test_apply_clipboard_clears_recog_when_none(tmp_path):
    storage, _plans, recog, _vac = make_services(tmp_path)
    recog.set("2026-07-10", RecognitionRange(540, 1080))
    clip = DayPlanClipboard(plan_minutes=480, recog=None)
    apply_clipboard(storage, recog, clip, ["2026-07-10"])
    assert storage.get_plan("2026-07-10") == 480
    assert recog.get("2026-07-10") is None


def test_snapshot_captures_all_facets(tmp_path):
    storage, plans, recog, vacations = make_services(tmp_path)
    storage.upsert(Attendance(
        "2026-07-10", "2026-07-10T09:00:00", "2026-07-10T18:00:00", 28800))
    storage.set_plan("2026-07-10", 420)
    recog.set("2026-07-10", RecognitionRange(540, 1080))
    vacations.set("2026-07-10", Vacation(120, 600, 720))
    storage.set_memo("2026-07-10", "메모")
    snap = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    assert snap.record.work_seconds == 28800
    assert snap.plan_override == 420
    assert snap.recog == RecognitionRange(540, 1080)
    assert snap.vacation == Vacation(120, 600, 720)
    assert snap.memo == "메모"


def test_restore_roundtrip_recovers_original(tmp_path):
    storage, plans, recog, vacations = make_services(tmp_path)
    storage.set_plan("2026-07-10", 420)
    recog.set("2026-07-10", RecognitionRange(540, 1080))
    before = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    storage.set_plan("2026-07-10", 480)
    recog.clear("2026-07-10")
    after = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    assert after != before
    restore_day(storage, recog, vacations, before)
    assert snapshot_day(storage, plans, recog, vacations, "2026-07-10") == before


def test_restore_recovers_empty_state(tmp_path):
    storage, plans, recog, vacations = make_services(tmp_path)
    before = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    storage.set_plan("2026-07-10", 480)
    recog.set("2026-07-10", RecognitionRange(540, 1080))
    vacations.set("2026-07-10", Vacation(480))
    storage.set_memo("2026-07-10", "x")
    restore_day(storage, recog, vacations, before)
    restored = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    assert restored == before
    assert restored.plan_override is None
    assert restored.recog is None
    assert restored.vacation is None
    assert restored.memo is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `./venv/bin/pytest tests/test_day_state.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.day_state'`

- [ ] **Step 3: 최소 구현 작성**

`core/day_state.py`:

```python
"""일자 데이터의 되돌리기 스냅샷과 복사/붙여넣기 버퍼 (Qt 비의존)."""
from __future__ import annotations

from dataclasses import dataclass

from core.recognition import RecognitionRange
from core.storage import Attendance
from core.vacation import Vacation

_MULTI_MIN = 2  # 다중 선택으로 간주하는 최소 일수


@dataclass(frozen=True)
class DayState:
    """한 일자의 되돌리기 가능한 전체 상태 스냅샷.

    equality 로 변경 여부를 판정한다(hash 는 사용하지 않음).
    """

    date: str
    record: Attendance | None
    plan_override: int | None
    recog: RecognitionRange | None
    vacation: Vacation | None
    memo: str | None


@dataclass(frozen=True)
class DayPlanClipboard:
    """복사 버퍼: 실계획(분)과 (가)계획 범위."""

    plan_minutes: int
    recog: RecognitionRange | None


def snapshot_day(storage, plans, recog, vacations, date: str) -> DayState:
    """해당 일자의 전체 상태를 스냅샷한다."""
    return DayState(
        date=date,
        record=storage.get(date),
        plan_override=plans.get_override(date),
        recog=recog.get(date),
        vacation=vacations.get(date),
        memo=storage.get_memo(date),
    )


def restore_day(storage, recog, vacations, state: DayState) -> None:
    """스냅샷대로 해당 일자의 전체 상태를 정확히 복원한다."""
    date = state.date
    if state.record is None:
        storage.delete(date)
    else:
        storage.upsert(state.record)
    if state.plan_override is None:
        storage.clear_plan(date)
    else:
        storage.set_plan(date, state.plan_override)
    if state.recog is None:
        recog.clear(date)
    else:
        recog.set(date, state.recog)
    if state.vacation is None:
        vacations.clear(date)
    else:
        vacations.set(date, state.vacation)
    storage.set_memo(date, state.memo or "")


def paste_targets(selected_date: str, multi_dates: list[str]) -> list[str]:
    """붙여넣기 대상: 다중(2일 이상)이면 전체, 아니면 단일 선택 일자."""
    if len(multi_dates) >= _MULTI_MIN:
        return list(multi_dates)
    return [selected_date]


def apply_clipboard(
    storage, recog, clipboard: DayPlanClipboard, dates: list[str]
) -> None:
    """대상 일자들에 클립보드(실계획+(가)계획)를 그대로 복제한다."""
    for date in dates:
        storage.set_plan(date, clipboard.plan_minutes)
        if clipboard.recog is None:
            recog.clear(date)
        else:
            recog.set(date, clipboard.recog)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `./venv/bin/pytest tests/test_day_state.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: 전체 테스트 · 커밋**

Run: `./venv/bin/pytest -q`
Expected: 전체 PASS

```bash
git add core/day_state.py tests/test_day_state.py
git commit -m "✨ 일자 상태 스냅샷·복사 버퍼 core 로직 추가"
```

---

### Task 2: 통합 Undo 배선 — 기존 편집 5종 래핑 + Cmd/Ctrl+Z

**Files:**
- Modify: `ui/main_window.py` (콜백 필드 `on_undo`, Z 단축키)
- Modify: `ui/app.py` (undo 상태·`_with_undo`·`_handle_undo`, 5개 핸들러 래핑, 콜백 배선)

**Interfaces:**
- Consumes: `core.day_state.snapshot_day`, `restore_day`, `DayState`.
- Produces (app.py 컨트롤러 내부):
  - `self._undo: list[DayState] | None`
  - `_with_undo(self, dates: list[str], operation: Callable[[], None]) -> None`
  - `_handle_undo(self) -> None`
- Produces (main_window.py): `MainWindowCallbacks.on_undo: Callable[[], None]`

- [ ] **Step 1: main_window 콜백 필드 추가**

`ui/main_window.py` — `MainWindowCallbacks` 에 필드 추가 (`on_open_ai` 아래):

```python
    on_open_ai: Callable[[], None]
    on_undo: Callable[[], None]
```

- [ ] **Step 2: main_window Cmd/Ctrl+Z 단축키 등록**

`ui/main_window.py` — Space 단축키 등록 블록(`QShortcut(QKeySequence(Qt.Key_Space) ...)`) 바로 아래에 추가:

```python
        # Cmd+Z / Ctrl+Z = 마지막 일자 변경 되돌리기 (단일 단계)
        for seq in (
            QKeySequence("Ctrl+Z"),
            QKeySequence(Qt.MetaModifier | Qt.Key_Z),
        ):
            QShortcut(seq, self, activated=lambda: self._cb.on_undo())
```

- [ ] **Step 3: app.py import·상태·헬퍼 추가**

`ui/app.py` — import 추가 (`from ui.day_dialog import open_day_dialog` 부근 core import 그룹에):

```python
from core.day_state import (
    DayPlanClipboard,
    DayState,
    apply_clipboard,
    paste_targets,
    restore_day,
    snapshot_day,
)
```

`__init__` 의 `self._multi_dates: list[str] = []` 바로 아래에 상태 추가:

```python
        # 복사 버퍼(단일 일자) · 마지막 변경 되돌리기 스냅샷(단일 단계)
        self._clipboard: DayPlanClipboard | None = None
        self._undo: list[DayState] | None = None
```

`MainWindowCallbacks(...)` 생성부에 `on_open_ai=self._handle_open_ai,` 아래 추가:

```python
            on_undo=self._handle_undo,
```

`# --- 핸들러 ---` 주석 아래(첫 핸들러 `_handle_clock_out` 위)에 헬퍼 추가:

```python
    def _snapshot(self, dates: list[str]) -> list[DayState]:
        return [
            snapshot_day(
                self._storage, self._plans, self._recog, self._vacations, d
            )
            for d in dates
        ]

    def _with_undo(self, dates, operation) -> None:
        """작업 전후 스냅샷을 비교해 실제 변경이 있으면 undo 슬롯에 저장."""
        before = self._snapshot(dates)
        operation()
        if self._snapshot(dates) != before:
            self._undo = before

    def _handle_undo(self) -> None:
        """Cmd/Ctrl+Z: 마지막 변경을 그 대상 일자에 한해 원복(단일 단계)."""
        if self._undo is None:
            return
        for state in self._undo:
            restore_day(self._storage, self._recog, self._vacations, state)
        self._undo = None
        self._refresh()
```

- [ ] **Step 4: 퇴근/퇴근취소 핸들러 래핑**

`ui/app.py` — `_handle_clock_out` / `_handle_cancel_clock_out` 를 다음으로 교체:

```python
    def _handle_clock_out(self) -> None:
        today = timeutil.today_str(timeutil.now())

        def op() -> None:
            try:
                self._service.record_clock_out()
            except ValueError:
                pass

        self._with_undo([today], op)
        self._refresh()

    def _handle_cancel_clock_out(self) -> None:
        today = timeutil.today_str(timeutil.now())
        self._with_undo([today], lambda: self._service.cancel_clock_out())
        self._refresh()
```

- [ ] **Step 5: 단일 수정 다이얼로그 핸들러 래핑**

`ui/app.py` — `_handle_edit_selected` 의 단일 경로에서 `open_day_dialog(...)` 호출을 `_with_undo` 로 감싼다. 다중 분기·`rec`·`holidays` 준비는 그대로 두고, 다이얼로그 호출만 교체:

```python
    def _handle_edit_selected(self) -> None:
        """[수정]: 단일 선택은 상세 다이얼로그, 다중 선택은 일괄 수정."""
        if len(self._multi_dates) >= 2:
            self._open_bulk_plan_edit_dialog()
            return
        date = self._selected_date
        rec = self._storage.get(date)
        holidays = self._holidays.get_holidays(self._view_year, self._view_month)
        self._with_undo([date], lambda: open_day_dialog(
            self._window,
            date,
            rec.clock_in if rec else None,
            rec.clock_out if rec else None,
            self._plans.get_override(date),
            config.get_default_daily_minutes(),
            self._handle_save_times,
            self._handle_save_plan,
            recog_range=self._recog.get(date),
            baseline_minutes=self._plans.baseline_minutes(date, holidays),
            on_save_recognition=self._handle_save_recognition,
            vacation=self._vacations.get(date),
            on_save_vacation=self._handle_save_vacation,
            memo=self._storage.get_memo(date),
            on_save_memo=self._storage.set_memo,
            start_in_edit=True,
        ))
        self._refresh()
```

- [ ] **Step 6: 요일 일괄 · 다중 일괄 핸들러 래핑**

`ui/app.py` — `_handle_edit_weekday` 의 `open_bulk_plan_dialog(...)` 호출을 `_with_undo(target_dates, lambda: open_bulk_plan_dialog(...))` 로 감싼다 (인자는 기존과 동일):

```python
        self._with_undo(target_dates, lambda: open_bulk_plan_dialog(
            self._window,
            f"{name} 계획 일괄 수정",
            info,
            config.get_default_daily_minutes(),
            apply,
            self._validate_bulk_range(target_dates),
        ))
        self._refresh()
```

`_open_bulk_plan_edit_dialog` 는 반환값(`applied`)이 필요하므로 리스트에 담아 래핑:

```python
        applied: list[bool] = []

        def op() -> None:
            applied.append(open_bulk_plan_dialog(
                self._window,
                "선택 일자 계획 일괄 수정",
                f"선택한 {len(dates)}일에 일괄 적용됩니다.",
                config.get_default_daily_minutes(),
                apply,
                self._validate_bulk_range(dates),
                on_apply_vacation=apply_vacation,
            ))

        self._with_undo(dates, op)
        if applied and applied[0]:
            self._multi_dates = []  # 적용 완료 → 단일 선택으로 복귀
        self._refresh()
```

- [ ] **Step 7: 임포트·전체 테스트 확인**

Run: `./venv/bin/python -c "import ui.app"`
Expected: 에러 없음
Run: `./venv/bin/pytest -q`
Expected: 전체 PASS

- [ ] **Step 8: 커밋**

```bash
git add ui/app.py ui/main_window.py
git commit -m "✨ 일자 편집 5종에 Cmd/Ctrl+Z 단일 단계 되돌리기 추가"
```

- [ ] **Step 9: 앱 재시작 후 사용자 시각 확인 요청**

Run: `./run.sh stop && ./run.sh`
사용자에게 확인 요청: 셀 수정/퇴근/일괄 수정 후 Cmd+Z(및 물리 Ctrl+Z) 로 직전 변경이 원복되는지.

---

### Task 3: 복사/붙여넣기 — Cmd/Ctrl+C·V + 도움말

**Files:**
- Modify: `ui/main_window.py` (콜백 `on_copy_day`/`on_paste_day`, C·V 단축키)
- Modify: `ui/app.py` (`QMessageBox` import, `_handle_copy_day`/`_handle_paste_day`, 콜백 배선)
- Modify: `ui/help_dialog.py` ("셀 선택 · 단축키" 페이지 안내 추가)

**Interfaces:**
- Consumes: `core.day_state.DayPlanClipboard`, `paste_targets`, `apply_clipboard`; 컨트롤러의 `_with_undo`(Task 2).
- Produces: `MainWindowCallbacks.on_copy_day`, `on_paste_day`; `_handle_copy_day`, `_handle_paste_day`.

- [ ] **Step 1: main_window 콜백 필드 추가**

`ui/main_window.py` — `MainWindowCallbacks` 에 (Task 2 의 `on_undo` 아래) 추가:

```python
    on_copy_day: Callable[[], None]
    on_paste_day: Callable[[], None]
```

- [ ] **Step 2: main_window Cmd/Ctrl+C·V 단축키 등록**

`ui/main_window.py` — Task 2 의 Z 단축키 블록 아래에 추가:

```python
        # Cmd/Ctrl+C = 단일 일자 복사, Cmd/Ctrl+V = 붙여넣기
        for seq in (
            QKeySequence("Ctrl+C"),
            QKeySequence(Qt.MetaModifier | Qt.Key_C),
        ):
            QShortcut(seq, self, activated=lambda: self._cb.on_copy_day())
        for seq in (
            QKeySequence("Ctrl+V"),
            QKeySequence(Qt.MetaModifier | Qt.Key_V),
        ):
            QShortcut(seq, self, activated=lambda: self._cb.on_paste_day())
```

- [ ] **Step 3: app.py QMessageBox import·콜백 배선**

`ui/app.py` — 상단 import 교체:

```python
from PySide6.QtWidgets import QApplication, QMessageBox
```

`MainWindowCallbacks(...)` 생성부 `on_undo=self._handle_undo,` 아래 추가:

```python
            on_copy_day=self._handle_copy_day,
            on_paste_day=self._handle_paste_day,
```

- [ ] **Step 4: 복사/붙여넣기 핸들러 추가**

`ui/app.py` — `_handle_undo` 아래에 추가:

```python
    def _handle_copy_day(self) -> None:
        """Cmd/Ctrl+C: 단일 선택 일자의 실계획·(가)계획을 복사 버퍼에 저장.

        다중 선택 중에는 복사할 수 없다.
        """
        if len(self._multi_dates) >= 2:
            QMessageBox.warning(
                self._window, "복사", "복수 일자는 복사할 수 없습니다."
            )
            return
        date = self._selected_date
        year, month = int(date[:4]), int(date[5:7])
        holidays = self._holidays.get_holidays(year, month)
        self._clipboard = DayPlanClipboard(
            plan_minutes=self._plans.effective_minutes(date, holidays),
            recog=self._recog.get(date),
        )

    def _handle_paste_day(self) -> None:
        """Cmd/Ctrl+V: 복사 버퍼를 대상 일자(단일/다중)에 그대로 붙여넣기."""
        if self._clipboard is None:
            return
        clipboard = self._clipboard
        dates = paste_targets(self._selected_date, self._multi_dates)
        self._with_undo(dates, lambda: apply_clipboard(
            self._storage, self._recog, clipboard, dates
        ))
        self._refresh()
```

- [ ] **Step 5: 도움말 안내 추가**

`ui/help_dialog.py` — "셀 선택 · 단축키" 페이지의 단축키 `<ul>` 에서 `ESC` 항목 아래에 추가:

```python
        <li><b>Cmd/Ctrl+C</b> — 단일 선택 일자의 실 계획·(가)계획 복사</li>
        <li><b>Cmd/Ctrl+V</b> — 복사한 계획을 선택 일자(단일·다중)에 붙여넣기</li>
        <li><b>Cmd/Ctrl+Z</b> — 마지막 일자 변경 되돌리기(단일 단계)</li>
```

- [ ] **Step 6: 임포트·전체 테스트 확인**

Run: `./venv/bin/python -c "import ui.app; import ui.main_window; import ui.help_dialog"`
Expected: 에러 없음
Run: `./venv/bin/pytest -q`
Expected: 전체 PASS

- [ ] **Step 7: 커밋**

```bash
git add ui/app.py ui/main_window.py ui/help_dialog.py
git commit -m "✨ 일자 실계획·(가)계획 복사/붙여넣기(Cmd/Ctrl+C·V) 추가"
```

- [ ] **Step 8: 앱 재시작 후 사용자 시각 확인 요청**

Run: `./run.sh stop && ./run.sh`
사용자에게 확인 요청:
1. 단일 일자 선택 후 Cmd+C → 다른 일자 선택 후 Cmd+V 로 실계획·(가)계획이 복제되는지.
2. 다중 선택(범위/Cmd+클릭) 대상에 Cmd+V 로 일괄 붙여넣기되는지.
3. 다중 선택 상태에서 Cmd+C 시 "복수 일자는 복사할 수 없습니다." 경고가 뜨는지.
4. 붙여넣기 직후 Cmd+Z 로 원복되는지.

---

## Self-Review

**Spec coverage:**
- 복사(단일 제한·경고) → Task 3 Step 4. ✓
- 붙여넣기(단일·다중, 그대로 복제, 재검증 생략) → Task 1 `apply_clipboard`, Task 3 Step 4. ✓
- 통합 Undo 5종+붙여넣기 → Task 2(5종)·Task 3(붙여넣기, `_with_undo` 재사용). ✓
- DayState 전체 facet 스냅샷·복원 → Task 1. ✓
- 단축키 Cmd/Ctrl 양쪽 → Task 2·3. ✓
- 도움말 → Task 3 Step 5. ✓
- 제외(휴가 관리/API 키) → 해당 핸들러 미래핑으로 자동 제외. ✓

**Placeholder scan:** 모든 코드 스텝에 실제 코드 포함. TBD/TODO 없음. ✓

**Type consistency:** `DayState`/`DayPlanClipboard` 필드·`snapshot_day`/`restore_day`/`paste_targets`/`apply_clipboard` 시그니처가 Task 1 정의와 Task 2·3 사용처에서 일치. `_with_undo(dates, operation)`·`_handle_undo`·`_clipboard`/`_undo` 명칭 일관. ✓
