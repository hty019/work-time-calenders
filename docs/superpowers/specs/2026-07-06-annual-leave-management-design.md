# 휴가(연차) 관리 기능 설계

2026-07-06 승인됨.

## 목적

우측 상단에서 올해 총 연차·소진·잔여 개수와 각 휴가의 사용 일자를 확인하고,
연도별 총 연차를 설정할 수 있게 한다.

## 결정 사항

- 총 연차는 **연도별**로 관리한다 (예: 2026년 15일).
- 시간제 휴가(2h/4h/6h)는 8h=1일 기준 **비례 환산** (2h=0.25일, 4h=0.5일, 6h=0.75일).
- UI는 **툴바 우측 요약 버튼**(예: `휴가 12.5/15`) + 클릭 시 **상세 다이얼로그**.
- 다이얼로그 기능 범위: 요약 + 올해 휴가 목록 **조회** + **총 연차 수정**.
  휴가 등록/삭제는 기존 날짜 셀 다이얼로그에서만 수행한다 (중복 없음).
- 다이얼로그 기준 연도는 캘린더 표시 월이 아닌 **시스템 올해**.

## 저장

- SQLite 새 테이블 `annual_leave(year INTEGER PRIMARY KEY, total_minutes INTEGER)`.
- 총 연차는 **분 단위 정수**로 저장 (15일 = 7200분). 0.25일 단위 입력을
  부동소수점 없이 표현하고, 소진량(vacation.minutes 합계)과 단위가 같다.
- 입력·표시는 일 단위 문자열로 변환 (7320분 → `15.25`).

## 구성

- `core/storage.py`: `get_annual_leave(year)`, `set_annual_leave(year, total_minutes)`,
  `list_vacation_year(year)` 추가.
- `core/vacation.py`: `YearLeaveSummary`(총·소진·잔여 분, 휴가 목록)와
  `VacationService.year_summary(year)`, `minutes_to_days_str` 추가.
  잔여 = 총 − 소진, 총 미설정 시 None.
- `ui/main_window.py`: 툴바에 휴가 요약 버튼 + `on_manage_vacation` 콜백,
  `render` 에서 요약 텍스트 갱신 (총 미설정 시 `휴가 관리`).
- `ui/vacation_dialog.py`(신규): 요약 라벨, 올해 휴가 목록 테이블
  (날짜·유형·구간·환산 일수), 총 연차(일) 입력 + 저장.
- `ui/app.py`: 핸들러에서 summary 구성, 저장 시 `set_annual_leave` 후 갱신.

## 테스트

core 는 TDD: storage 신규 메서드, year_summary 집계(빈 연도·시간제 환산·총
미설정), 일수 포맷 경계값. UI 는 임포트·로직 검증까지, 시각 확인은 사용자 요청.
