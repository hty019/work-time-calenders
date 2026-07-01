"""위젯 공통 디자인 토큰 (색상·폰트·치수).

모든 뷰가 이 값을 참조하여 일관된 모던 반투명 스타일을 유지한다.
"""
from __future__ import annotations

# 반투명 정도 (0.0 완전 투명 ~ 1.0 불투명) — 회색 베이스를 살짝 비춘다
WINDOW_ALPHA = 0.92

# 색상 — 회색 베이스 반투명 위에 흰색 텍스트를 얹는 구성
BG_BASE = "#2b2d31"        # 위젯 전체 배경 (회색 베이스)
BG_ELEVATED = "#3a3d42"    # 헤더·버튼 등 한 단계 띄운 표면
BG_TODAY = "#3b82f6"       # 오늘 강조 (파란색)
BG_HOVER = "#43464c"       # 마우스 오버 시 셀 배경

FG_DATE = "#ffffff"        # 일자 — 흰색 (크고 굵게)
FG_TIME = "#b6bcc4"        # 근무시간 — 흐린 흰색 (작고 가늘게, 일자와 구분)
FG_TIME_TODAY = "#e8f0ff"  # 오늘 셀의 근무시간 (파란 배경 위 대비 확보)
FG_HOLIDAY = "#ff5a5a"     # 공휴일·주말 일자 — 빨간색
FG_MUTED = "#9aa0a6"       # 요일 헤더 등 보조 텍스트
FG_INCOMPLETE = "#ffd166"  # 미퇴근 강조 (노란색)

# 폰트 — 일자는 크고 굵게, 시간은 작고 가늘게 하여 시각적으로 분리
FONT_FAMILY = "Helvetica"
FONT_HEADER = (FONT_FAMILY, 12, "bold")
FONT_WEEKDAY = (FONT_FAMILY, 10, "bold")
FONT_DATE = (FONT_FAMILY, 14, "bold")
FONT_TIME = (FONT_FAMILY, 9, "normal")
FONT_BUTTON = (FONT_FAMILY, 11, "bold")

# 셀 치수 (px) — 모든 날짜 칸을 동일 크기로 고정
CELL_WIDTH = 46
CELL_HEIGHT = 42
