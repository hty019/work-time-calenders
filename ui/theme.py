"""Qt UI 공통 디자인 토큰 (기존 위젯 팔레트 계승)."""
from __future__ import annotations

# 색상 — 회색 베이스 다크 테마
BG_BASE = "#2b2d31"
BG_ELEVATED = "#3a3d42"
BG_TODAY = "#3b82f6"
BG_HOVER = "#43464c"
BG_PROGRESS = "#4ade80"      # 진행률 바 채움

FG_DATE = "#ffffff"
FG_TIME = "#b6bcc4"
FG_PLANNED = "#8ab4f8"       # 계획 시간 강조 (연파랑)
FG_HOLIDAY = "#ff5a5a"
FG_MUTED = "#9aa0a6"
FG_INCOMPLETE = "#ffd166"
FG_WORKING = "#4ade80"

FONT_FAMILY = "Helvetica"
CELL_MIN_WIDTH = 96
CELL_MIN_HEIGHT = 84

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
