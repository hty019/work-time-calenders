# STATUS 메모 드래그 자동 복사 설계

## 목적

STATUS 패널 메모 박스에서 마우스로 텍스트를 드래그 선택하면 자동으로
클립보드에 복사하고, 복사되었음을 사용자에게 알린다.

## 요구사항

- 마우스 버튼을 뗄 때(드래그·더블클릭 선택 종료) 선택 텍스트가 있으면
  선택 내용을 그대로 클립보드에 복사한다. 선택이 없으면 아무 일도 없다.
- `selectionChanged` 는 드래그 중 연속 발화하므로 사용하지 않고,
  `mouseReleaseEvent` 시점 1회 복사로 구현한다.
- 복사 직후 메모 박스 바로 아래에 `✓ 클립보드에 복사됨` 안내를 1.5초간
  표시 후 자동 숨김. 연속 복사 시 타이머를 재시작한다.

## 구조 — ui/status_panel.py

- `_CopyOnSelectMemo(QTextEdit)`: `mouseReleaseEvent` 재정의. 선택 텍스트가
  있으면 `QGuiApplication.clipboard().setText(선택)` 후 `on_copied()` 콜백.
- `StatusPanel`: `_memo_box` 를 위 서브클래스로 교체 (스타일·읽기 전용 유지).
  muted 소형 라벨 `_copy_notice` 를 메모 박스 아래 배치, 기본 숨김.
  단발 QTimer(`_COPY_NOTICE_MS = 1500`)로 표시/숨김 제어.

## 테스트

- Qt UI 동작이라 헤드리스 자동검증 불가 — 전체 pytest·임포트 검증까지
  수행하고, 동작 확인은 위젯 재시작 후 사용자에게 요청한다.
