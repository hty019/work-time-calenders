# 근무시간 데스크탑 위젯 (work-widget) 설계

작성일: 2026-06-30

## 1. 목적

macOS 부팅(로그인) 시 자동 실행되어 바탕화면에 항상 떠 있는 달력 위젯.
출근 시간을 자동 기록하고, '퇴근' 버튼으로 근무 시간을 확정하며,
월간 누적 근무시간과 한국 공휴일을 달력 형태로 보여준다. 모든 시간은 KST 기준.

## 2. 기술 스택 & 환경

- **언어/런타임**: Python 3 (가상환경 `venv`)
- **UI**: `tkinter` — 테두리 없는(borderless) always-on-top 창, 드래그로 이동, 위치 기억
- **저장소**: `sqlite3` (표준 라이브러리, 외부 의존 없음)
- **공휴일 API**: 공공데이터포털 특일정보 API (`requests`로 호출, 월별 결과 로컬 캐시)
- **시간대**: `zoneinfo`의 `Asia/Seoul` 고정 (KST)
- **자동 시작**: macOS LaunchAgent (`~/Library/LaunchAgents/*.plist`)
- **프로젝트 위치**: `~/work-widget/`
- **외부 의존성**: `requests` 한 개로 최소화

## 3. 컴포넌트 구조

```
work-widget/
├── main.py                # 앱 진입점, 생명주기
├── widget/
│   ├── window.py          # tkinter 창 (always-on-top, 드래그)
│   ├── calendar_view.py   # 월 달력 렌더링 (오늘 강조/공휴일/일별 근무시간), 날짜 클릭 처리
│   └── edit_dialog.py     # 일자 클릭 시 출근/퇴근 시각 수정 다이얼로그
├── core/
│   ├── attendance.py      # 출근 기록/퇴근 처리 로직
│   ├── storage.py         # SQLite 접근 (레코드 CRUD)
│   └── holidays.py        # 공휴일 API 호출 + 캐시
├── config.py              # 설정(서비스 키, 창 위치) 로드/저장
├── install_autostart.py   # LaunchAgent 설치/제거 스크립트
└── tests/                 # 단위 테스트
```

각 모듈은 단일 책임을 갖고, `storage`/`holidays`는 인터페이스를 통해 테스트 시 모킹 가능하게 둔다.

## 4. 데이터 모델 (SQLite)

`attendance` 테이블 (하루 1행):

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `work_date` | TEXT (PK) | `YYYY-MM-DD` (KST 기준) |
| `clock_in` | TEXT | 출근 시각 ISO8601 |
| `clock_out` | TEXT \| NULL | 퇴근 시각 (미퇴근 시 NULL) |
| `work_seconds` | INTEGER \| NULL | 퇴근 시 계산된 근무 초 (점심 차감 반영) |

월간 총 근무시간 = 해당 월 `work_seconds` 합계.

DB 파일 위치: `~/.work-widget/attendance.db` (설정/캐시와 같은 디렉터리). 공휴일 캐시는
`~/.work-widget/holidays_cache.json`.

## 5. 핵심 동작 흐름

- **부팅/실행 시**: LaunchAgent가 앱 실행 → 오늘 행이 없으면 현재 시각을 `clock_in`으로
  기록(이미 있으면 유지, 재부팅·재실행해도 불변) → 이번 달 공휴일 로드(캐시 우선) → 달력 렌더.
- **'퇴근' 버튼 클릭**: `clock_out` 기록 + `work_seconds` 계산 후 저장 →
  달력/월간 합계 즉시 갱신. (그날 기록 확정)
- **위젯 표시**: 이번 달 달력에 ①오늘 강조 ②공휴일 빨강 표시 ③일자별 근무시간 표기,
  상단에 오늘 출근시각·이번 달 누적 근무시간 표시.
- **일자 클릭(수동 수정)**: 달력의 날짜 셀을 클릭하면 수정 다이얼로그가 열려
  그날의 출근/퇴근 시각을 직접 입력·변경할 수 있다. 저장하면 `work_seconds`를
  점심 차감 규칙(6장)대로 재계산하고 달력·월간 합계를 갱신한다.
  - 기록이 없는 날: 출근/퇴근 시각을 새로 입력해 행 생성 가능.
  - 퇴근 시각을 비우면 "미퇴근" 상태로 되돌림(`clock_out`/`work_seconds` NULL).
  - 검증: 퇴근 시각은 출근 시각보다 이후여야 하며, 위반 시 저장 거부하고 경고 표시.

## 6. 근무시간 계산 (점심 자동 차감)

원시 구간 `raw = clock_out - clock_in` (초) 기준:

- `raw < 9시간` → 30분(1800초) 차감
- `raw >= 9시간` → 60분(3600초) 차감
- `work_seconds = max(0, raw - 차감)` (음수 방지)

상수로 정의:
- `LUNCH_THRESHOLD_SECONDS = 9 * 3600`
- `LUNCH_DEDUCT_SHORT_SECONDS = 30 * 60`
- `LUNCH_DEDUCT_LONG_SECONDS = 60 * 60`

## 7. 엣지 케이스 처리

- **퇴근 누른 뒤 재부팅**: 그날 기록 확정 상태이므로 출근시각 유지(재오픈 안 함).
- **퇴근 안 누르고 종료한 날**: `clock_out` NULL로 남음 → 달력에 "미퇴근" 표시,
  월간 합계에서 제외. (자동 보정 없음)
- **API 키 미설정/네트워크 실패**: 공휴일 없이 달력은 정상 표시, 캐시 있으면 캐시 사용.
- **시간대**: 모든 날짜 경계는 KST로 계산.

## 8. 테스트 전략

- `core/` 로직 단위 테스트(pytest):
  - 출근 최초 기록 유지 (재실행 시 불변)
  - 퇴근 시각 기록 및 `work_seconds` 계산
  - 점심 차감 경계값(9시간 미만/이상, 음수 보정)
  - 월간 합계 (미퇴근 제외)
  - 수동 수정: 출근/퇴근 시각 변경 시 재계산, 기록 없는 날 생성,
    퇴근 비우기(미퇴근 전환), 퇴근<출근 검증 거부
- `holidays`는 API 응답 모킹.
- UI(tkinter)는 수동 확인 + 렌더 보조 순수 함수만 단위 테스트.
- 목표 커버리지: core 로직 80% 이상.

## 9. 보안 / 설정

- 공공데이터포털 서비스 키는 코드에 하드코딩하지 않고 설정 파일
  (`~/.work-widget/config.json` 또는 환경변수)에서 로드.
- 설정 파일은 git에 커밋하지 않음(`.gitignore`).
