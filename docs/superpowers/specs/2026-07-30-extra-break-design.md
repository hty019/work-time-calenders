# 임의 휴게시간 설계

## 목적

자동 임계-정지 휴게(4h/8h/12h)와 별도로, 날짜별 임의 휴게시간(분)을 입력해
근무 시간에서 추가로 차감한다. 대부분 1h 미만의 값이 저장될 것으로 예상한다.

## 요구사항

- 분 단위 정수로 입력. 비우거나 0이면 해제(미설정)와 동일.
- 근무 시간 집계에서 차감: 자동 휴게 차감 후 값에서 임의 휴게분을 추가 차감
  (하한 0). `worktime.py` 임계 모델 자체는 변경하지 않는다.
- **예상 퇴근·남은 시간 계산에는 반영하지 않는다** (사용자 결정: 표시·집계만).
- 표기 형식: 1h 미만 `45m`, 1h 이상 `1h 30m`, 정시는 0m 생략 `1h`.
- STATUS 패널: 휴게가 설정된 날(null 아님)에만 상태 라인 바로 위에
  `휴게 시간: 45m` 형식으로 표시. 오늘/과거/미래 공통(휴가 라인과 동일 패턴).

## 구조

### 저장 — core/storage.py

새 테이블(기존 부속 테이블 패턴, `CREATE TABLE IF NOT EXISTS` 로 마이그레이션 불필요):

```sql
CREATE TABLE IF NOT EXISTS extra_break (
    work_date TEXT PRIMARY KEY,
    minutes   INTEGER NOT NULL
)
```

메서드: `get_extra_break`, `set_extra_break`, `clear_extra_break`,
`list_extra_break_month` (plan/memo 와 동일한 시그니처 패턴).

### 계산 — core/attendance.py

`AttendanceService._work_seconds` 에서 storage 의 임의 휴게를 읽어
`max(0, 기존 계산 − 휴게분×60)` 반환. 이 메서드는 퇴근 확정·수정·재계산·
진행 중 실시간 계산의 공통 경로이므로 한 곳 수정으로 전 경로에 반영된다.

휴게 저장/변경 시 휴가와 동일하게 `recompute_work(date)` 를 호출해
확정 근무초를 재계산한다 (app 배선).

### 표기 — core/timefmt.py

`format_break(minutes: int) -> str`: `45 → "45m"`, `60 → "1h"`, `90 → "1h 30m"`.

### 입력 — ui/day_dialog.py

- 수정 폼에 "휴게(분)" QLineEdit 추가 (휴가 행 아래). 0 이상 정수 검증,
  상한 24h(1440분). 비우거나 0 → 해제.
- 보기 모드에 "휴게" 행 추가 (`format_break` 값 또는 `-`).
- 새 콜백 `on_save_break(work_date, minutes | None)` → app 에서
  set/clear + `recompute_work` + 화면 갱신.

### STATUS — core/day_detail.py, ui/status_panel.py

- `DayDetail.break_minutes: int | None` 필드 추가, storage 에서 채움.
- `break_line(minutes)` 라인 함수 + `_break` QLabel 을 휴가 라인 아래·상태
  라인 위에 배치. 값이 None 이면 숨김.

## 테스트

- storage: extra_break CRUD·월 목록.
- attendance: `_work_seconds` 차감 경로(퇴근 확정·edit·recompute·진행 중),
  하한 0 경계.
- timefmt: `format_break` 경계값 (0/59/60/61/90/120).
- day_detail: break_minutes 채움/None.
- status_panel: `break_line` 형식.
