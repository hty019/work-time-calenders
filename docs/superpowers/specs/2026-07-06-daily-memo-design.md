# 일자별 메모 기능 설계

2026-07-06 승인됨.

## 목적

날짜 다이얼로그에서 근무 기록 외에 그날의 근무 내용·주요 안건 등을
자유 텍스트로 기록·확인할 수 있게 한다.

## 결정 사항

- 메모가 있는 날짜는 캘린더 셀에 📝 아이콘을 표시한다.
- 메모는 자유 텍스트(여러 줄), 길이 제한·검증 없음.
- 빈 문자열 저장은 메모 삭제와 같다.

## 저장

- SQLite 새 테이블 `memo(work_date TEXT PRIMARY KEY, content TEXT NOT NULL)`.
- `get_memo(date)` → str | None, `set_memo(date, content)` (공백 정리 후
  빈 값이면 행 삭제), `list_memo_month(year, month)` → 날짜→내용 dict.

## 구성

- `core/storage.py`: 위 3개 메서드 추가.
- `core/calendar_model.py`: `DayCell.has_memo: bool` 추가,
  `build_month_grid` 에 memo 조회 콜백 추가.
- `ui/calendar_widget.py`: `has_memo` 셀에 📝 표시 (날짜 숫자 옆).
- `ui/day_dialog.py`: 보기 모드 '메모' 행(전문, word wrap, 없으면 '-'),
  수정 모드 QTextEdit. 저장 시 strip 후 `on_save_memo(date, content)`,
  취소 시 원복.
- `ui/app.py`: 다이얼로그 오픈 시 메모 전달, 저장 콜백 연결,
  그리드 빌드에 memo 조회 연결.

## 테스트

storage CRUD·월 목록, DayCell.has_memo, 보기 모드 표시 텍스트를 TDD.
QTextEdit 등 GUI 동작은 시각 확인 요청.
