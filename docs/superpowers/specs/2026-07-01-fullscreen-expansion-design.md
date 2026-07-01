# 근무시간 앱 — 전체 화면 프로그램 확장 설계

- 작성일: 2026-07-01
- 상태: 승인됨 (구현 대기)
- 이전 스펙: `2026-06-30-work-widget-design.md` (위젯 초기 설계)

## 1. 배경 / 목표

기존은 tkinter 기반 테두리 없는 데스크탑 **위젯**이다. 이를 본격적인 **전체 화면
프로그램**으로 확장하되, 경우에 따라 **위젯 모드**도 지원한다.

신규 핵심 요구사항:

1. **날짜별 계획 근무 시간**을 미리 저장할 수 있다.
2. 해당 일자에 출근이 기록되고 계획이 있으면 **예상 퇴근시각을 자동 산정·안내**한다.
3. 캘린더 우측에 **status 영역**을 두어 월 계획/누적/진행률/오늘 예상 퇴근을 한눈에 본다.

## 2. 확정된 결정 사항

| 항목 | 결정 |
|---|---|
| UI 기술 | **PySide6/Qt** 전환. `core/` 순수 로직 재사용, UI는 재작성 |
| 모드 | **단일 앱**에서 전체화면 ↔ 위젯 **모드 전환**. 서비스 인스턴스 공유 |
| 계획 입력 | **평일 기본값 + 날짜별 오버라이드** |
| 계획/예상퇴근 의미 | **순 근무시간 기준**(휴게 제외). `worktime` 역산으로 산정 |
| status 지표 | 월 계획 합계, 월 실제 누적, **월 계획 대비 진행률 바**, **오늘 예상 퇴근시각** |
| 출근 방식 | **앱 부팅 = 자동 출근** 유지(기존 동작). 시각 상이 시 편집 다이얼로그로 수정 |
| 계획 데이터 모델 | **A안** — config 단일 평일 기본값 + `plan` 오버라이드 테이블 |

## 3. 아키텍처 / 프로젝트 구조

원칙: `core/`는 Qt 비의존 순수 도메인 로직(단위 테스트 대상), `ui/`는 얇은 Qt 표현 계층.

```
core/                         # 순수 로직 (Qt 의존 없음)
  storage.py                  # attendance(기존) + plan 테이블 접근 추가
  attendance.py               # 출퇴근 서비스 (기존)
  worktime.py                 # + raw_seconds_for_net() 역산 추가
  plan.py                     # 신규 PlanService: 유효 계획분 / 월 계획 합계
  stats.py                    # 신규 MonthSummary: 누적·진행률·예상 퇴근 집계
  holidays.py, timeutil.py    # 기존
config.py                     # + default_daily_minutes, 마지막 모드 저장

ui/                           # 신규 Qt(PySide6) 계층
  app.py                      # QApplication 조립 + 분경계 QTimer
  main_window.py              # 전체화면: 캘린더(좌) + status 패널(우)
  widget_window.py            # 위젯 모드: 축약 뷰
  calendar_widget.py          # 월 그리드
  status_panel.py             # 월 계획/누적/진행률바/예상 퇴근
  day_dialog.py               # 날짜별 출퇴근 + 계획 편집
  theme.py                    # Qt 스타일 (기존 widget/theme.py 포팅)

main.py                       # 진입점 (ui.app 호출)
widget/                       # 기존 tkinter — 검증 완료 후 제거
```

- **모드 전환**: 단일 `QApplication`이 `MainWindow`/`WidgetWindow`를 소유하고
  같은 서비스 인스턴스(`Storage`/`AttendanceService`/`PlanService`/`MonthSummary`)를
  공유한다. 툴바 버튼·단축키로 전환하며 마지막 모드를 config에 저장한다.
- 기존 tkinter `widget/`는 로직 참고용으로 남겼다가 Qt UI 검증 완료 후 제거(`🔥`).

## 4. 데이터 모델 & 계산 로직

### 4.1 `plan` 테이블 (신규)

```sql
CREATE TABLE IF NOT EXISTS plan (
    work_date       TEXT PRIMARY KEY,   -- 'YYYY-MM-DD'
    planned_minutes INTEGER NOT NULL    -- 순 근무 계획(분)
)
```

- 기존 `attendance` 테이블 무변경. `plan`은 **오버라이드만** 저장(예외 없는 날은 행 없음).
- attendance 없이도 미래 날짜 계획 저장 가능.
- `CREATE IF NOT EXISTS`로 기존 DB 무손상 마이그레이션.

### 4.2 `PlanService` (core/plan.py)

```
effective_minutes(date, holidays) -> int
    override 있으면 그 값,
    없으면: 주말이거나 공휴일 → 0, 그 외 평일 → config.default_daily_minutes
month_planned_minutes(year, month, holidays) -> int   # 월 전체 유효 계획 합
set_plan(date, minutes) / clear_plan(date)            # 오버라이드 설정/해제
```

- 공휴일 판정은 `HolidayClient` 결과를 주입받아 사용(순수 유지).
- `default_daily_minutes` 기본 480(8h), `config.json` 저장.

### 4.3 예상 퇴근시각 — `worktime.raw_seconds_for_net()`

`compute_work_seconds`(raw→순근무)의 역함수. 목표 순근무 `net`에 도달하는
최소 체류시간 `raw`:

| 목표 순근무 net | 필요 체류 raw |
|---|---|
| net ≤ 4h | net (휴게 없음) |
| 4h < net ≤ 8h | net + 30m (1차 휴게) |
| net > 8h | net + 60m (2차 휴게) |

- 예: 계획 8h → raw 8h30m → 예상 퇴근 = 출근 + 8h30m. 계획 9h → 출근 + 10h.
- forward↔inverse 경계 일관성을 단위 테스트로 고정.

### 4.4 `MonthSummary` (core/stats.py)

`Storage` + `PlanService` + `AttendanceService`를 조합한 순수 집계:

```
month_planned_minutes        # 월 계획 합계
month_actual_seconds         # 확정 근무 합 + 오늘 진행 중
progress_ratio               # actual / planned (0~1, planned=0이면 None)
today_expected_clock_out     # 오늘 출근O + 계획O → 출근 + raw_seconds_for_net(계획)
                             #   없으면 None
today_remaining              # 예상 퇴근까지 남은 시간 (지났으면 0/음수 처리)
```

## 5. UI / 화면 흐름

### 5.1 전체화면 레이아웃 (`MainWindow`)

```
┌────────────────────────────────────────────────────────┐
│  [◀ 2026년 7월 ▶]        상태 ● 근무중      [위젯모드][⚙]│  ← 툴바
├──────────────────────────────────┬─────────────────────┤
│  월  화  수  목  금  토  일        │   STATUS            │
│  각 셀: 날짜 / 실제근무 / 계획     │  월 계획   160h     │
│  (오늘 셀 강조, 진행중 실시간)     │  월 누적    92h     │
│                                   │  [███████░░░] 58%   │
│                                   │  오늘 예상 퇴근      │
│                                   │   18:30 (2h12m 남음)│
│                                   │  [출근] / [퇴근]     │
└──────────────────────────────────┴─────────────────────┘
```

- **캘린더 셀**: 날짜 · 실제 근무(`work_seconds`, 오늘은 진행 중 실시간) ·
  계획(`effective_minutes`, 오버라이드는 강조). 공휴일·오늘·미완료(퇴근 안함) 시각 구분.
  클릭 → `day_dialog`.
- **status 패널**: 월 계획 / 월 누적 / 진행률 바 / 오늘 예상 퇴근·남은시간. 우측 고정.
- **출근/퇴근 컨트롤**: status 하단. 퇴근 상태면 `[취소][재퇴근]`(기존 동작 유지).

### 5.2 날짜 편집 다이얼로그 (`day_dialog`)

한 날짜에 대해:

- **계획 근무 시간**(분/시간 입력, 비우면 오버라이드 해제 → 기본값 복귀)
- **출근/퇴근 시각**(기존 `edit_dialog` 기능 이관)

### 5.3 위젯 모드 (`WidgetWindow`)

기존 위젯 축약 뷰 유지 + **예상 퇴근시각 한 줄 추가**. 프레임리스·always-on-top·
드래그 이동·위치 저장(기존 동작 포팅). 툴바/트레이에서 전체화면으로 복귀.

### 5.4 실시간 갱신

기존 분경계 동기화 로직을 `QTimer`로 포팅 — 매 분 경계에 오늘 셀·월 누적·진행률·
예상 퇴근 남은시간을 갱신(전체 재렌더 없이 해당 위젯만).

### 5.5 출근 방식

**앱 부팅 = 자동 출근** 유지(양 모드 공통, 기존 동작). 출근 시각이 실제와 다르면
`day_dialog`에서 직접 수정. 별도 옵션 없음.

## 6. 에러 처리

- **계획 입력 검증**: 음수·비수치·과대값(>24h) 거부, 다이얼로그 인라인 메시지.
  빈 값 = 오버라이드 해제(정상 경로).
- **출퇴근 정합성**: 퇴근 ≤ 출근 거부(기존 `edit`의 `ValueError` 유지, UI 메시지 변환).
- **공휴일 API 실패**: 기존 `holiday_fallback`·캐시 폴백 유지. 공휴일 정보 없으면
  평일=근무일 간주로 진행.
- **DB**: `plan` 테이블 `CREATE IF NOT EXISTS` 마이그레이션. 쓰기는 기존처럼 커밋.
- **UI 예외**: 서비스 호출은 핸들러에서 잡아 상태바/다이얼로그로 안내, 조용히
  삼키지 않음.

## 7. 테스트 전략

순수 `core/`에 집중(기존 pytest 자산 활용, 커버리지 80%+ 유지):

- `test_worktime.py`: **`raw_seconds_for_net` 신규** — 경계값(4h/8h 전후),
  forward↔inverse 왕복 일관성.
- `test_plan.py`(신규): `effective_minutes`(평일/주말/공휴일/오버라이드),
  `month_planned_minutes`.
- `test_stats.py`(신규): 월 누적(확정+진행중), 진행률(planned=0 시 None),
  예상 퇴근시각.
- `test_storage.py`: `plan` upsert/get/clear, 기존 attendance 회귀.
- `test_config.py`: `default_daily_minutes` 로드/기본값.
- **Qt UI**: 얇게 유지, 로직은 core에 두어 단위 테스트로 커버. UI는 수동 스모크,
  향후 pytest-qt 여지 남김.

## 8. 범위 밖 (YAGNI)

- 요일별 개별 기본값(B안), 반복 규칙 엔진(C안) — 추후 확장 여지.
- 시스템 트레이 아이콘 상주(위젯 모드로 대체).
- 데이터 내보내기/리포트, 다중 사용자.
