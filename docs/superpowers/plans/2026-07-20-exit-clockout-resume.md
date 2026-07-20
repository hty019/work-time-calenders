# 종료 시 자동 퇴근 · 재실행 자동 재개 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 정상 종료 시 진행 중이면 자동 퇴근을 저장하고, 같은 날 재실행하면 그 자동 퇴근만 취소해 근무를 연속 재개한다.

**Architecture:** 판정·기록 로직은 Qt 비의존 `AttendanceService` 에 `auto_clock_out`/`resume_auto_clock_out` 두 메서드로 추가(TDD). 자동/수동 퇴근 구분은 `config.json` 의 `auto_clock_out_date` 마커로 하고, `ui/app.py` 가 `QApplication.aboutToQuit`(종료)와 `run()`(재실행)에 배선한다.

**Tech Stack:** Python 3, PySide6/Qt, SQLite(core.storage), pytest.

## Global Constraints

- 실행/테스트는 시스템 python 이 아니라 반드시 `./venv/bin/python`, `./venv/bin/pytest` 사용.
- 매직 넘버 금지 — 상수/기존 값 사용. 주석 한글 허용. core 로직은 TDD.
- 커밋 메시지 한글, prefix 이모지(✨ 기능, 🔧 설정, 📝 문서, ♻️ 리팩토링). 한 커밋 = 한 논리 단위.
- attendance 테이블 스키마 변경 금지 — 구분은 config 마커로만.
- 자동 퇴근은 **WORKING(출근 O·퇴근 X)** 일 때만. 이미 퇴근(수동 포함)·미출근이면 건드리지 않는다.
- 재개는 **마커 == 오늘** 이고 오늘 퇴근 기록이 있을 때만. 부팅 처리 후 마커는 항상 비운다.
- 간격 포함(연속 누적) — `cancel_clock_out` 기본 동작 그대로. 강제 종료는 비대상.
- GUI/종료 훅은 헤드리스 검증 불가 → import·회귀 테스트까지만, 실제 종료/재실행은 사용자 확인.
- 시각 주입: 테스트는 `AttendanceService(storage, clock=lambda: fixed_dt)` 또는 `svc._clock = lambda: datetime(...)`. 타임존 `KST = ZoneInfo("Asia/Seoul")`.

---

### Task 1: AttendanceService.auto_clock_out / resume_auto_clock_out (TDD)

**Files:**
- Modify: `core/attendance.py` (클래스 `AttendanceService` 에 메서드 2개 추가 — `cancel_clock_out` 정의 아래, `recompute_work` 앞)
- Test: `tests/test_attendance.py` (파일 끝에 테스트 추가)

**Interfaces:**
- Consumes (기존): `self._clock`, `self._storage.get(date)`, `self.record_clock_out()`, `self.cancel_clock_out()`, `core.timeutil.today_str`.
- Produces:
  - `AttendanceService.auto_clock_out(self) -> Attendance | None`
  - `AttendanceService.resume_auto_clock_out(self, marker_date: str | None) -> Attendance | None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_attendance.py` 파일 끝에 추가:

```python
def test_auto_clock_out_saves_when_working(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    rec = svc.auto_clock_out()
    assert rec is not None
    assert rec.clock_out == datetime(2026, 6, 30, 18, 0, tzinfo=KST).isoformat()
    assert rec.work_seconds == 8 * 3600
    assert svc.today_status() is WorkStatus.CLOCKED_OUT


def test_auto_clock_out_noop_when_not_clocked_in(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 18, 0, tzinfo=KST))
    assert svc.auto_clock_out() is None
    assert svc._storage.get("2026-06-30") is None  # 기록 생성 안 함


def test_auto_clock_out_noop_when_already_clocked_out(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 17, 0, tzinfo=KST)
    svc.record_clock_out()  # 수동 퇴근 17:00
    svc._clock = lambda: datetime(2026, 6, 30, 19, 0, tzinfo=KST)
    assert svc.auto_clock_out() is None
    # 기존 퇴근 시각을 덮어쓰지 않는다
    assert svc._storage.get("2026-06-30").clock_out == datetime(
        2026, 6, 30, 17, 0, tzinfo=KST
    ).isoformat()


def test_resume_cancels_when_marker_is_today(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    svc.auto_clock_out()
    svc._clock = lambda: datetime(2026, 6, 30, 19, 0, tzinfo=KST)
    rec = svc.resume_auto_clock_out("2026-06-30")
    assert rec is not None
    assert rec.clock_out is None
    assert svc.today_status() is WorkStatus.WORKING


def test_resume_noop_when_no_clock_out(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()  # 진행 중, 퇴근 없음
    assert svc.resume_auto_clock_out("2026-06-30") is None
    assert svc.today_status() is WorkStatus.WORKING


def test_resume_noop_when_marker_other_day(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    svc.auto_clock_out()
    # 마커가 어제라면 오늘 퇴근을 재개하지 않는다
    assert svc.resume_auto_clock_out("2026-06-29") is None
    assert svc.today_status() is WorkStatus.CLOCKED_OUT


def test_resume_noop_when_marker_none(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 18, 0, tzinfo=KST))
    svc.record_clock_in()
    assert svc.resume_auto_clock_out(None) is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `./venv/bin/pytest tests/test_attendance.py -q -k "auto_clock_out or resume"`
Expected: FAIL — `AttributeError: 'AttendanceService' object has no attribute 'auto_clock_out'`

- [ ] **Step 3: 최소 구현 작성**

`core/attendance.py` — `cancel_clock_out` 메서드 정의 직후(라인 74 뒤), `edit` 앞에 추가:

```python
    def auto_clock_out(self) -> Attendance | None:
        """진행 중(WORKING)일 때만 현재 시각으로 퇴근 저장. 그 외 None.

        미출근(기록 없음)·이미 퇴근(수동 포함)이면 건드리지 않는다.
        정상 종료 훅에서 호출해 근무 기록이 진행 중인 채 방치되지 않게 한다.
        """
        now = self._clock()
        date = timeutil.today_str(now)
        existing = self._storage.get(date)
        if existing is None or existing.clock_out is not None:
            return None
        return self.record_clock_out()

    def resume_auto_clock_out(self, marker_date: str | None) -> Attendance | None:
        """marker_date 가 오늘이고 오늘 퇴근 기록이 있으면 취소해 재개.

        그 외(마커 없음·다른 날·이미 진행 중)에는 아무것도 하지 않고 None.
        자동 종료로 저장된 퇴근만 되돌리기 위해 호출측이 마커를 전달한다.
        """
        now = self._clock()
        date = timeutil.today_str(now)
        if marker_date != date:
            return None
        return self.cancel_clock_out()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `./venv/bin/pytest tests/test_attendance.py -q`
Expected: PASS (기존 + 신규 7개 모두)

- [ ] **Step 5: 전체 테스트 · 커밋**

Run: `./venv/bin/pytest -q`
Expected: 전체 PASS

```bash
git add core/attendance.py tests/test_attendance.py
git commit -m "✨ 진행 중 자동 퇴근·자동 퇴근 재개 서비스 메서드 추가"
```

---

### Task 2: config 자동 퇴근 마커 get/set (TDD)

**Files:**
- Modify: `config.py` (`set_last_mode` 정의 아래에 함수 2개 추가)
- Test: `tests/test_config.py` (파일 끝에 테스트 추가)

**Interfaces:**
- Consumes (기존): `load_config()`, `save_config(cfg)`.
- Produces:
  - `config.get_auto_clock_out_date() -> str | None`
  - `config.set_auto_clock_out_date(date: str | None) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_config.py` 파일 끝에 추가:

```python
def test_auto_clock_out_date_roundtrip(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    assert cfg.get_auto_clock_out_date() is None  # 기본 없음
    cfg.set_auto_clock_out_date("2026-06-30")
    assert cfg.get_auto_clock_out_date() == "2026-06-30"


def test_auto_clock_out_date_none_removes_key(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    cfg.set_auto_clock_out_date("2026-06-30")
    cfg.set_auto_clock_out_date(None)
    assert cfg.get_auto_clock_out_date() is None
    assert "auto_clock_out_date" not in cfg.load_config()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `./venv/bin/pytest tests/test_config.py -q -k auto_clock_out_date`
Expected: FAIL — `AttributeError: module 'config' has no attribute 'get_auto_clock_out_date'`

- [ ] **Step 3: 최소 구현 작성**

`config.py` — `set_last_mode` 함수 정의 아래에 추가:

```python
def get_auto_clock_out_date() -> str | None:
    """정상 종료 시 자동 저장한 퇴근의 날짜(YYYY-MM-DD). 없으면 None."""
    return load_config().get("auto_clock_out_date")


def set_auto_clock_out_date(date: str | None) -> None:
    """자동 종료 퇴근 마커를 기록/해제한다. None 이면 키를 제거한다."""
    cfg = load_config()
    if date is None:
        cfg.pop("auto_clock_out_date", None)
    else:
        cfg["auto_clock_out_date"] = date
    save_config(cfg)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `./venv/bin/pytest tests/test_config.py -q`
Expected: PASS (기존 + 신규 2개)

- [ ] **Step 5: 전체 테스트 · 커밋**

Run: `./venv/bin/pytest -q`
Expected: 전체 PASS

```bash
git add config.py tests/test_config.py
git commit -m "🔧 자동 종료 퇴근 마커 config get/set 추가"
```

---

### Task 3: ui/app.py 배선 — 종료 훅 + 재실행 재개

**Files:**
- Modify: `ui/app.py` (`__init__` 에 `aboutToQuit` 연결, `_handle_app_exit` 핸들러 추가, `run()` 에 재개+마커 비움 추가)

**Interfaces:**
- Consumes: `self._service.auto_clock_out()`, `self._service.resume_auto_clock_out(marker)`, `config.get_auto_clock_out_date()`, `config.set_auto_clock_out_date(date)`, `self._app.aboutToQuit`.
- Produces: `AppController._handle_app_exit(self) -> None` (내부 배선용, 외부 의존 없음).

- [ ] **Step 1: 종료 훅 연결 추가**

`ui/app.py` `AppController.__init__` 에서 `self._mode = config.get_last_mode()` 아래(생성자 끝)에 추가:

```python
        # 정상 종료 시 진행 중이면 자동 퇴근 저장 (강제 종료는 대상 아님)
        self._app.aboutToQuit.connect(self._handle_app_exit)
```

- [ ] **Step 2: 종료 핸들러 추가**

`ui/app.py` — `run()` 메서드 정의 바로 위(`# --- 실행 ---` 주석 아래)에 추가:

```python
    def _handle_app_exit(self) -> None:
        """정상 종료 훅: 진행 중이면 자동 퇴근하고 재개용 마커를 남긴다."""
        rec = self._service.auto_clock_out()
        if rec is not None:
            config.set_auto_clock_out_date(rec.work_date)
```

- [ ] **Step 3: run() 에 재실행 재개 추가**

`ui/app.py` `run()` 의 `self._service.record_clock_in()` 줄 아래에 추가(기존 주석 유지):

```python
    def run(self) -> None:
        self._service.record_clock_in()  # 부팅 = 자동 출근 (기존 동작 유지)
        # 직전 정상 종료가 자동 저장한 오늘 퇴근이면 취소해 근무 연속 재개
        self._service.resume_auto_clock_out(config.get_auto_clock_out_date())
        config.set_auto_clock_out_date(None)  # 마커 소비/무효화
        self._refresh()
        self._show_mode(config.get_last_mode())
        self._timer.start(self._ms_until_next_minute())
        self._app.exec()
```

- [ ] **Step 4: 임포트·전체 테스트 확인**

Run: `./venv/bin/python -c "import ui.app"`
Expected: 에러 없음
Run: `./venv/bin/pytest -q`
Expected: 전체 PASS (회귀 없음)

- [ ] **Step 5: 커밋**

```bash
git add ui/app.py
git commit -m "✨ 정상 종료 시 자동 퇴근·재실행 시 자동 재개 배선"
```

- [ ] **Step 6: 앱 재시작 후 사용자 확인 요청**

Run: `./run.sh stop && ./run.sh`
사용자에게 확인 요청:
1. 근무 중 위젯 [닫기](정상 종료) 후 다시 실행 → 퇴근이 취소되고 근무가 이어지는지(체류/근무 시간이 종료 전 기준으로 연속되는지).
2. 위젯 [퇴근] 버튼으로 수동 퇴근 → 종료 → 재실행 시 퇴근이 유지되는지(재개 안 됨).
3. 종료만 하고 재실행하지 않은 채 다음 날 실행하면 어제는 퇴근 마감 상태로 유지되는지.

---

## Self-Review

**Spec coverage:**
- 정상 종료 자동 퇴근(WORKING 한정) → Task 1 `auto_clock_out` + Task 3 Step 1·2. ✅
- 자동 퇴근만 재개(수동 보존) → Task 1 `resume_auto_clock_out`(마커 기반) + config 마커 Task 2 + Task 3 배선. ✅
- 마커==오늘 & 퇴근 있음일 때만 재개, 다른 날/None 무시 → Task 1 테스트 4~7. ✅
- 부팅 후 마커 항상 비움 → Task 3 Step 3 `set_auto_clock_out_date(None)`. ✅
- 간격 포함(연속 누적) → `cancel_clock_out` 재사용, Task 1 `test_resume_cancels_when_marker_is_today` 가 clock_out None 복귀 검증. ✅
- 스키마 변경 없음 → config 마커만 사용. ✅
- 강제 종료 비대상 → 별도 처리 없음(비목표). ✅

**Placeholder scan:** 모든 코드 스텝에 실제 코드 포함. TBD/TODO 없음. ✅

**Type consistency:** `auto_clock_out() -> Attendance | None`, `resume_auto_clock_out(marker_date: str | None) -> Attendance | None`, `get/set_auto_clock_out_date`, `_handle_app_exit` 시그니처가 Task 1·2 정의와 Task 3 사용처에서 일치. config 키 문자열 `"auto_clock_out_date"` 일관. ✅
