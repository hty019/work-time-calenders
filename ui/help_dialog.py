"""도움말 다이얼로그 — 페이지 단위로 넘겨 보는 사용 안내."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout,
    QWidget,
)

from ui import theme

# (페이지 제목, 본문 HTML). 본문은 QLabel 리치 텍스트로 렌더링된다.
_PAGES: list[tuple[str, str]] = [
    (
        "기본 사용",
        """
        <ul>
        <li><b>자동 출근</b> — 앱을 실행(부팅)하면 당일 출근이 자동
            기록됩니다.</li>
        <li><b>캘린더</b> — 날짜 셀을 클릭하면 STATUS 패널에 해당 일자
            상세가 표시되고, 더블 클릭하면 수정 다이얼로그가 열립니다.</li>
        <li><b>STATUS 패널</b> — 월 요약(법정 기준·최대 가능·실 계획·월
            누적·연차)과 선택 일자 상세, [수정]·[퇴근]·[오늘] 버튼을
            제공합니다.</li>
        <li><b>위젯 모드</b> — 항상 위 소형 창으로 당일 출근·퇴근
            예정·체류·남은 시간·상태를 보여줍니다. 드래그로 이동하며
            위치는 저장됩니다.</li>
        <li><b>공휴일</b> — 공휴일 API 키를 등록하면 대체·음력 공휴일까지
            캘린더에 반영됩니다(미등록 시 양력 고정 공휴일만).</li>
        </ul>
        """,
    ),
    (
        "법정 기준 · 최대 가능",
        """
        <p>월 근로 한도 지표 두 가지는 다음과 같이 계산합니다.</p>
        <ul>
        <li><b>법정 기준</b> = (말일 ÷ 7 × 40h) 내림 − 평일 공휴일 수 × 8h</li>
        <li><b>최대 가능</b> = (말일 ÷ 7 × 52h) 내림 — 공휴일 차감 없음</li>
        </ul>
        <p>진행률 바는 월 누적 근로(휴가 인정 포함) 기준 4단계로
        표시됩니다.</p>
        <ul>
        <li><b>녹색</b> — 법정 기준 이내 (바 최대 = 법정 기준)</li>
        <li><b>노랑</b> — 법정 초과 ~ +20h (바 최대 = 최대 가능)</li>
        <li><b>주황</b> — 법정 +20h 초과</li>
        <li><b>빨강</b> — 최대 가능 초과</li>
        </ul>
        """,
    ),
    (
        "근무 시간 계산",
        """
        <p><b>휴게 임계-정지 모델</b> — 누적 순근로가 임계에 닿을 때마다
        30분씩 휴게로 카운트가 멈춥니다.</p>
        <ul>
        <li>누적 4h 도달 → 30분 정지</li>
        <li>누적 8h 도달 → 추가 30분 정지</li>
        <li>누적 12h 도달 → 추가 30분 정지</li>
        </ul>
        <p><b>예상 퇴근</b>은 계획 순근무를 채우는 데 필요한 체류시간을
        역산합니다: 계획 ≤4h 휴게 없음 · &lt;8h +30분 · &lt;12h +60분 ·
        ≥12h +90분.</p>
        <p><b>휴가</b> — 2h/4h/6h/8h(1day), 하루 1건. 휴가분은 근로 인정으로
        월 누적에 합산됩니다. 시간제 휴가 구간이 실 근로와 겹치면 근로에서
        제외해 이중 집계를 막고, 1day 휴가일은 출퇴근과 무관하게
        근로 0 + 휴가 8h로 고정됩니다.</p>
        """,
    ),
    (
        "계획 · (가)계획",
        """
        <ul>
        <li><b>실 계획</b> — 날짜별 순근무 목표(분). 비우면 기본값(설정
            가능, 기본 480분)이며 주말·공휴일은 0입니다.</li>
        <li><b>(가)계획</b> — 사전 정의한 출근 인정 시각 범위입니다. 실
            근로가 범위를 벗어나면 <b>경고 표시만</b> 하고 근무 시간 계산은
            바꾸지 않습니다.</li>
        <li>저장 시 (가)계획 범위 폭이 실 계획을 채우는 데 필요한
            체류시간(휴게 포함)보다 좁으면 저장이 차단됩니다.</li>
        <li><b>요일 헤더 클릭</b> — 해당 요일 전체(과거·퇴근 완료일 제외)에
            계획·(가)계획을 일괄 적용합니다.</li>
        </ul>
        """,
    ),
    (
        "상태 판정",
        """
        <p>STATUS·위젯의 상태 라인은 아래 우선순위로 판정됩니다.</p>
        <ul>
        <li><b>미출근</b> — 출근 기록 없음 (회색)</li>
        <li><b>조기 퇴근 / 정상 퇴근 / 퇴근 완료</b> — 퇴근 기록 완료.
            예상 퇴근보다 이르면 조기(주황), 아니면 정상(녹색)</li>
        <li><b>⚠ 계획 시간 범위 초과!!</b> — (가)계획 종료 시각을 실제로
            지남 (노랑 강조)</li>
        <li><b>⚠ 계획 범위 초과 예상</b> — 예상 퇴근이 (가)계획 범위를
            벗어날 것으로 예상 (노랑)</li>
        <li><b>금일 근무 달성 · 퇴근 가능</b> — 남은 시간 0 (녹색 강조)</li>
        <li><b>정상 근무중</b> — 위에 해당 없음 (녹색)</li>
        </ul>
        """,
    ),
    (
        "셀 선택 · 단축키",
        """
        <p><b>날짜 셀 선택</b></p>
        <ul>
        <li>클릭 — 단일 선택 (STATUS 표시)</li>
        <li>더블 클릭 — 수정 다이얼로그 바로 열기</li>
        <li><b>Cmd+클릭</b> — 다중 선택 추가/제거 토글</li>
        <li><b>Shift+클릭</b> — 마지막 선택부터 연속 범위 선택</li>
        <li>다중 선택 시 [ (N) 수정 ] — 실 계획·(가)계획·휴가를 일괄
            수정 (출퇴근·메모 제외)</li>
        </ul>
        <p><b>단축키</b></p>
        <ul>
        <li><b>Cmd+E</b> — 선택 일자 수정 ([수정] 버튼과 동일)</li>
        <li><b>Space</b> — 오늘 날짜·현재 월로 복귀</li>
        <li><b>ESC</b> — 다중 선택 해제</li>
        </ul>
        """,
    ),
]


def open_help_dialog(parent) -> None:
    """페이지 넘김([이전]/[다음]) 방식의 도움말을 연다."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("도움말")
    dlg.setMinimumSize(
        theme.HELP_DIALOG_MIN_WIDTH, theme.HELP_DIALOG_MIN_HEIGHT
    )
    layout = QVBoxLayout(dlg)

    title = QLabel()
    title.setStyleSheet("font-weight:bold; font-size:16px;")
    layout.addWidget(title)

    stack = QStackedWidget()
    for _title, body in _PAGES:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(body)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        page_layout.addWidget(label)
        page_layout.addStretch(1)
        stack.addWidget(page)
    layout.addWidget(stack, stretch=1)

    nav = QHBoxLayout()
    prev_btn = QPushButton("◀ 이전")
    page_label = QLabel()
    page_label.setAlignment(Qt.AlignCenter)
    next_btn = QPushButton("다음 ▶")
    close_btn = QPushButton("닫기")
    close_btn.clicked.connect(dlg.accept)
    nav.addWidget(prev_btn)
    nav.addWidget(page_label, stretch=1)
    nav.addWidget(next_btn)
    nav.addWidget(close_btn)
    layout.addLayout(nav)

    def _show_page(index: int) -> None:
        stack.setCurrentIndex(index)
        title.setText(_PAGES[index][0])
        page_label.setText(f"{index + 1} / {len(_PAGES)}")
        prev_btn.setEnabled(index > 0)
        next_btn.setEnabled(index < len(_PAGES) - 1)

    prev_btn.clicked.connect(lambda: _show_page(stack.currentIndex() - 1))
    next_btn.clicked.connect(lambda: _show_page(stack.currentIndex() + 1))
    _show_page(0)
    dlg.exec()
