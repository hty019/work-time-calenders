"""Qt UI 공통 디자인 토큰 (기존 위젯 팔레트 계승)."""
from __future__ import annotations

# 색상 — 회색 베이스 다크 테마
BG_BASE = "#2b2d31"
BG_ELEVATED = "#3a3d42"
BG_WEEKEND = "#4a4038"       # 주말 셀 배경 (연한 갈색)
BORDER_TODAY = "#60a5fa"     # 오늘 셀 테두리 (밝은 파랑)
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

WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 640
STATUS_PANEL_WIDTH = 260


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
