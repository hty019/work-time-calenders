"""Qt UI 공통 디자인 토큰 (기존 위젯 팔레트 계승)."""
from __future__ import annotations

# 색상 — 회색 베이스 다크 테마
BG_BASE = "#2b2d31"
BG_ELEVATED = "#3a3d42"
BG_WEEKEND = "#4a4038"       # 주말 셀 배경 (연한 갈색)
BORDER_TODAY = "#60a5fa"     # 오늘 셀 테두리 (밝은 파랑)
BORDER_HOVER = "#fb923c"     # 셀 호버 테두리 (주황)
BG_HOVER = "#43464c"
BG_PROGRESS = "#4ade80"       # 진행률 바 채움 (법정 기준 이내, 녹색)
BG_PROGRESS_OVER = "#facc15"  # 법정 기준 초과 ~ +20h (노랑)
BG_PROGRESS_CRIT = "#fb923c"  # 법정 기준 +20h 초과 (주황)
BG_PROGRESS_MAX = "#ef4444"   # 최대 근로 가능시간 초과 (빨강)

FG_DATE = "#ffffff"
FG_TIME = "#b6bcc4"
FG_PLANNED = "#8ab4f8"       # 계획 시간 강조 (연파랑)
FG_HOLIDAY = "#ff5a5a"
FG_MUTED = "#9aa0a6"
FG_INCOMPLETE = "#ffd166"
FG_WORKING = "#4ade80"
FG_ACTUAL_DONE = "#4ade80"    # 퇴근 완료일 실 근로시간 강조 (연두)
FG_RANGE_WARN = "#ffd166"     # 인정 범위 이탈 경고 (노랑)
FG_VACATION = "#c084fc"       # 휴가 표시 (연보라)
FG_DONE_TODAY = "#4ade80"     # 금일 근로 시간 달성 (녹색)
FG_OVERDUE = "#fb923c"        # 계획 퇴근 초과·미퇴근 경고 (주황)

FONT_FAMILY = "Helvetica"
CELL_MIN_WIDTH = 96
CELL_MIN_HEIGHT = 84

# 캘린더 셀 폰트 크기(px)
CELL_WORK_FONT_PX = 11        # 일반 근로시간/미퇴근 표시
CELL_PLAN_FONT_PX = 10        # 계획 시간 표시
CELL_ACTUAL_DONE_FONT_PX = 14  # 퇴근 완료일 실 근로시간 강조(조금 크게)

# 좌상단 날짜가 차지하는 높이(px). 하단 대칭 여백에 사용해
# 계획/근로 시간 블록이 셀 전체 기준 가운데로 보이도록 보정한다.
CELL_DATE_ROW_PX = 20

WEEKDAY_HEADER_PAD_PX = 10   # 요일 헤더 상하 패딩 (헤더 높이 확보)

WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 640
STATUS_PANEL_WIDTH = 260

# 휴가 관리 다이얼로그 최소 크기
VACATION_DIALOG_MIN_WIDTH = 460
VACATION_DIALOG_MIN_HEIGHT = 380

# 날짜 편집 다이얼로그 최소 크기 (입력란 잘림 방지)
DAY_DIALOG_MIN_WIDTH = 300
DAY_DIALOG_MIN_HEIGHT = 160  # 내용보다 크면 잔여 여백이 생기므로 낮게 유지
DAY_DIALOG_FONT_PT = 17  # 시스템 기본(13pt)보다 4pt 크게
DAY_DIALOG_MEMO_HEIGHT = 110  # 메모 박스 높이 (넘치면 휠 스크롤)

# STATUS 패널 메모 박스
STATUS_MEMO_MAX_HEIGHT = 140  # 넘치면 스크롤 (스크롤바는 숨김)


def memo_box_style() -> str:
    """메모 영역 공통 스타일: 둥근 테두리 사각형 (STATUS·다이얼로그 공용)."""
    return (
        f"border: 1px solid {FG_MUTED}; border-radius: 6px;"
        "background: transparent; padding: 6px;"
    )


def base_stylesheet() -> str:
    """앱 전역 다크 스타일시트."""
    return f"""
    QWidget {{ background-color: {BG_BASE}; color: {FG_DATE};
               font-family: {FONT_FAMILY}; }}
    QPushButton {{ background-color: {BG_ELEVATED}; border: none;
                   padding: 8px 14px; border-radius: 6px; font-weight: bold; }}
    QPushButton:hover {{ background-color: {BG_HOVER}; }}
    QLabel {{ background: transparent; }}
    """
