# 일자 계획 복사/붙여넣기 · 통합 Undo 설계

작성일: 2026-07-20

## 목적

캘린더에서 선택한 일자의 **실계획**과 **(가)계획**을 다른 일자에 복사/붙여넣기
(Cmd+C·Cmd+V / Ctrl+C·Ctrl+V) 하고, **모든 일자 데이터 변경 작업**을 마지막 1회
한정으로 되돌리기(Cmd+Z / Ctrl+Z) 할 수 있게 한다.

## 요구사항

1. **복사 (Cmd+C / Ctrl+C)**
   - **단일 선택 상태에서만** 동작. 다중 선택(2일 이상) 중 복사 시 경고
     `"복수 일자는 복사할 수 없습니다."` 를 출력하고 클립보드는 변경하지 않는다.
   - 선택 일자의 **실계획**(effective minutes — 오버라이드가 없으면 그 날의
     기본값)과 **(가)계획 범위**(`RecognitionRange | None`)를 메모리 클립보드에
     저장한다.

2. **붙여넣기 (Cmd+V / Ctrl+V)**
   - 클립보드가 비어 있으면 무시.
   - 대상: **다중 선택이면 선택된 모든 일자, 아니면 단일 선택 일자**.
   - 각 대상에 원본을 **그대로 복제(덮어쓰기)**:
     - 실계획 → `set_plan(date, plan_minutes)` (항상 오버라이드로 설정)
     - (가)계획 → 원본에 있으면 `set(date, rng)`, 없으면 `clear(date)`
   - 원본은 저장 시 이미 (가)계획 폭 ≥ 필요 체류 검증을 통과했고 실계획·(가)계획을
     함께 복제하므로 대상도 자기정합적 → **붙여넣기 시 재검증 생략**.

3. **되돌리기 (Cmd+Z / Ctrl+Z)** — 통합 단일 단계 Undo
   - 아래 5종 + 붙여넣기 작업 각각을, 실행 직전 영향 일자의 **전체 상태
     (DayState)** 스냅샷으로 감싸 두고, 실제 변경이 있었을 때만 Undo 슬롯에
     저장한다. Cmd+Z 는 그 스냅샷대로 해당 일자들만 복원한다.
   - **단일 단계**: 마지막 작업 1회만 되돌린다. 복원 후 슬롯을 비워 재-undo 불가.
   - Undo 대상 작업:
     1. 단일 수정 다이얼로그 (`_handle_edit_selected` 단일 경로)
     2. 다중 일괄 수정 (`_open_bulk_plan_edit_dialog`)
     3. 요일 일괄 수정 (`_handle_edit_weekday`)
     4. 퇴근 (`_handle_clock_out`)
     5. 퇴근 취소 (`_handle_cancel_clock_out`)
     6. 붙여넣기 (`_handle_paste_day`)
   - 제외: 툴바 "휴가 관리"(연차 총량, 연 단위), 공휴일 API 키 등 per-day
     데이터가 아닌 작업.

## 데이터 모델 (core/day_state.py, Qt 비의존)

```python
@dataclass(frozen=True)
class DayState:
    """한 일자의 되돌리기 가능한 전체 상태 스냅샷."""
    date: str
    record: Attendance | None       # 출/퇴근 기록 (work_seconds 포함, 정확 복원)
    plan_override: int | None       # 실계획 오버라이드 (None = 없음)
    recog: RecognitionRange | None  # (가)계획
    vacation: Vacation | None       # 휴가
    memo: str | None

@dataclass(frozen=True)
class DayPlanClipboard:
    """복사 버퍼: 실계획(분) + (가)계획 범위."""
    plan_minutes: int
    recog: RecognitionRange | None
```

### 순수/서비스 헬퍼 (core/day_state.py)

```python
def snapshot_day(storage, plans, recog, vacations, date) -> DayState: ...
def restore_day(storage, recog, vacations, state: DayState) -> None: ...
def paste_targets(selected_date, multi_dates) -> list[str]: ...
def apply_clipboard(storage, recog, clipboard, dates) -> None: ...
```

- `snapshot_day`: `storage.get`, `plans.get_override`, `recog.get`,
  `vacations.get`, `storage.get_memo` 로 전체 상태를 모은다.
- `restore_day` (facet별 정확 복원):
  - record: `None → storage.delete(date)`, 아니면 `storage.upsert(record)`
    (저장된 work_seconds 그대로 복원, 재계산 없음)
  - plan_override: `None → storage.clear_plan`, 아니면 `storage.set_plan`
  - recog: `None → recog.clear`, 아니면 `recog.set`
  - vacation: `None → vacations.clear`, 아니면 `vacations.set`
  - memo: `storage.set_memo(date, memo or "")` (빈 문자열 = 삭제 = None 복원)
- `paste_targets`: `multi_dates` 가 2일 이상이면 그 목록, 아니면
  `[selected_date]`.
- `apply_clipboard`: 각 date 에 `storage.set_plan(date, plan_minutes)` +
  clipboard.recog `None → recog.clear` / 아니면 `recog.set`.

## 컨트롤러 배선 (ui/app.py)

### 상태
```python
self._clipboard: DayPlanClipboard | None = None
self._undo: list[DayState] | None = None
```

### Undo 래퍼 (핵심)
```python
def _with_undo(self, dates: list[str], operation: Callable[[], None]) -> None:
    before = [snapshot_day(self._storage, self._plans, self._recog,
                           self._vacations, d) for d in dates]
    operation()                       # 모달 다이얼로그 exec / 붙여넣기 / 일괄적용
    after = [snapshot_day(...) for d in dates]
    if after != before:               # 실제 변경 시에만 undo 등록 (취소 무시)
        self._undo = before
```
두 다이얼로그(`open_day_dialog`, `open_bulk_plan_dialog`)는 모두 `.exec()`
모달(블로킹)이라, 한 다이얼로그가 여러 facet(출퇴근/실계획/(가)계획/휴가/메모)을
저장해도 **다이얼로그 1회 = 스냅샷 1개**로 코얼레싱된다.

### 핸들러
- `_handle_copy_day`:
  - `len(self._multi_dates) >= 2` → 경고창 `"복수 일자는 복사할 수 없습니다."`,
    return.
  - 아니면 선택 일자의 `holidays`(선택 일자 연/월)로 `effective_minutes` 계산 +
    `recog.get` → `self._clipboard` 저장.
- `_handle_paste_day`:
  - `self._clipboard is None` → return.
  - `dates = paste_targets(self._selected_date, self._multi_dates)`.
  - `self._with_undo(dates, lambda: apply_clipboard(...))` → `_refresh()`.
- `_handle_undo`:
  - `self._undo is None` → return.
  - 각 스냅샷 `restore_day(...)`, `self._undo = None`, `_refresh()`.
- 기존 핸들러를 `_with_undo` 로 감싼다:
  - `_handle_edit_selected` (단일 경로): `dates=[self._selected_date]`,
    operation = `open_day_dialog(...)`. (다중 경로는 아래 일괄로 위임)
  - `_open_bulk_plan_edit_dialog`: `dates=sorted(self._multi_dates)`,
    operation = `open_bulk_plan_dialog(...)`.
  - `_handle_edit_weekday`: `dates=target_dates`, operation = 다이얼로그.
  - `_handle_clock_out` / `_handle_cancel_clock_out`: `dates=[today]`,
    operation = 서비스 호출.

### 단축키 (ui/main_window.py)
`MainWindowCallbacks` 에 `on_copy_day`, `on_paste_day`, `on_undo` 추가.
각 동작마다 두 시퀀스 등록 — Qt 가 mac 에서 `Ctrl` 를 Cmd 로 매핑하므로
`"Ctrl+C"` 는 Cmd+C, 물리 Ctrl 키는 `Qt.MetaModifier | Key_C` 로 별도 등록:
- 복사: `"Ctrl+C"` + `Qt.MetaModifier|Qt.Key_C`
- 붙여넣기: `"Ctrl+V"` + `Qt.MetaModifier|Qt.Key_V`
- 되돌리기: `"Ctrl+Z"` + `Qt.MetaModifier|Qt.Key_Z`

모달 다이얼로그가 열려 있으면 메인 윈도우 단축키는 발화하지 않아 텍스트 입력과
충돌하지 않는다.

## 도움말 반영
`ui/help_dialog.py` 단축키 안내에 복사/붙여넣기/되돌리기 3줄을 추가한다.

## 테스트 (tests/, core TDD)

Qt 비의존 core 로직을 인메모리 `Storage` 로 단위 테스트한다
(`test_day_state.py` 신설):

1. `snapshot_day` 가 5개 facet 을 모두 담는다.
2. `restore_day` 왕복: 임의 상태 → 변경 → 복원 시 원상태와 동일.
   - 각 facet 의 None ↔ 값 경계 (오버라이드 없음, 휴가 없음, 메모 없음, 미기록).
3. `paste_targets`: 단일 → `[selected]`, 다중(2일 이상) → 전체 목록.
4. `apply_clipboard`: 실계획 오버라이드 설정, recog `None → clear` /
   값 → `set`.
5. "변경 없으면 undo 미등록" 판정을 위한 `DayState` 동등성(변경 전후 비교).

Qt 모달·단축키·경고창·시각 동작은 사용자 확인.

## 비목표 (YAGNI)

- 다단계 Undo 히스토리 / Redo — 단일 단계로 충분.
- 붙여넣기 시 재검증 — 자기정합적 복제이므로 생략.
- OS 시스템 클립보드 연동 — 앱 내 메모리 버퍼로 충분.
