# 화살표 날짜 이동 + STATUS 과거 실 계획 표시

## 목적

1. 캘린더에서 화살표 키로 선택 일자를 이동하고, Shift 조합으로 범위 선택을
   확장한다.
2. STATUS 패널에서 과거 일자에도 실 계획 시간을 근무 시간 바로 위에 표시한다.

## Part A — 키보드 방향 이동

### 동작 규칙

- 선택 일자가 있으면 화살표 방향으로 이동: `←` −1일, `→` +1일, `↑` −7일(한 주
  전), `↓` +7일(한 주 후).
- 일요일에서 `→` 는 +1일이므로 다음 주 월요일로 이동(순차 이동).
- **월 경계는 모두 이동 X**: 월말 `→`, 월1일 `←`, 첫 주 `↑`, 마지막 주 `↓` 는
  현재 달을 벗어나므로 no-op. 화살표로는 보는 달이 절대 바뀌지 않는다.
- `Shift+화살표`: 이동하면서 마지막 선택 일자부터 새 위치까지 사이 일자를 모두
  선택(범위 확장, 기존 Shift+클릭과 동일한 union 방식). `Shift+↑/↓` 는 사이 7일
  전부 포함.
- 복수 선택 중이면 마지막으로 선택된 일자(`_selected_date`) 기준으로 이동.
- 월 이동(툴바) 후 선택 일자가 보는 달에 없으면, 화살표 첫 입력은 이동 없이
  기준일만 선택한다. 기준일 = 오늘(보는 달에 있으면) 아니면 그 달 1일.

### 핵심 로직 (신규 `core/calendar_nav.py`, TDD)

Qt 비의존 순수 함수로 분리:

- 방향 델타 상수: `DELTA_LEFT=-1, DELTA_RIGHT=+1, DELTA_UP=-7, DELTA_DOWN=+7`.
- `in_month(date: str, year: int, month: int) -> bool`
- `step_within_month(date, delta_days, year, month) -> str | None`
  결과가 같은 (year, month) 면 ISO 문자열, 아니면 `None`(경계 no-op).
- `resolve_nav_base(selected_date, year, month, today) -> tuple[str, bool]`
  선택 일자가 보는 달이면 `(selected_date, True)`(이동), 아니면
  `(오늘 또는 1일, False)`(첫 입력은 기준일 선택만).

### UI 연결

- `ui/main_window.py`: QShortcut 8개(`←→↑↓`, `Shift+←→↑↓`) 추가 → 콜백
  `on_navigate(delta_days: int, extend: bool)`. 델타 상수는 `core.calendar_nav`
  에서 import. 기존 ESC/Space/Ctrl+E QShortcut 패턴 유지.
- `MainWindowCallbacks` 에 `on_navigate` 추가.
- `ui/app.py` `_handle_navigate(delta_days, extend)`:
  - `base, should_move = resolve_nav_base(_selected_date, y, m, today)`
  - `should_move=False` → `extend` 무시, `base` 단일 선택(멀티 해제).
  - `should_move=True` → `target = step_within_month(base, delta_days, y, m)`;
    `None` 이면 return(경계). `extend` 면 기존 `_select_range_to(target)`,
    아니면 단일 선택(`_multi_dates=[]`, `_selected_date=target`).
  - `_refresh()`.

`_selected_date` 가 이미 "마지막 선택"이므로 복수 선택 기준 이동이 자동 성립하고,
`_select_range_to` 재사용으로 Shift 이동 범위 채움이, `step_within_month` 의 `None`
으로 월 경계 clamp 가 처리된다.

## Part B — STATUS 과거 일자 실 계획

- 순수 함수 `past_plan_line(detail) -> str` 추가:
  `"실 계획: {format_hm(detail.planned_minutes)}"` (future_lines 와 동일 문구).
- `ui/status_panel.py` 에 일반 스타일 전용 라벨 `_past_plan` 신설. 레이아웃상
  `_expected`(퇴근 시각) 과 `_stay`(근무 시간) 사이(= `_expected_sub` 다음)에
  배치해 **근무 시간 바로 위**에 오게 한다. 과거 일자에서만 visible, 그 외 숨김.
- 스타일은 출근/퇴근 라인과 동일한 일반 스타일(강조), muted 아님.

## 테스트

- `tests/test_calendar_nav.py`: in_month, 네 방향 경계 clamp, 일요일→월요일,
  주 단위 상/하 이동, resolve_nav_base 3분기(선택 in-view / 오늘 / 1일).
- `tests/test_app_navigation.py`: `_handle_navigate` 단일 이동, Shift 범위,
  경계 no-op, 기준일 폴백.
- `tests/test_status_panel.py`: `past_plan_line` 포맷.

## 도움말

- `ui/help_dialog.py` 단축키 목록에 화살표/Shift+화살표 항목 추가.
