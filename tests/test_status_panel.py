from core.stats import ProgressLevel
from ui.status_panel import progress_caption


def test_caption_normal_shows_percent():
    # 법정 기준 이내: 진행도 퍼센트 표시
    text = progress_caption(
        56, ProgressLevel.NORMAL, 100 * 3600, 177 * 60
    )
    assert text == "근로 시간 진행도: 56%"


def test_caption_over_shows_exceeded_hours():
    # 법정 기준 초과: +초과시간(h) 표시 (분 버림)
    text = progress_caption(
        78, ProgressLevel.OVER, 180 * 3600 + 30 * 60, 177 * 60
    )
    assert text == "초과 근로 진행: +3h"


def test_caption_critical_and_exceeded_also_show_hours():
    assert progress_caption(
        86, ProgressLevel.CRITICAL, 198 * 3600, 177 * 60
    ) == "초과 근로 진행: +21h"
    assert progress_caption(
        100, ProgressLevel.EXCEEDED, 231 * 3600, 177 * 60
    ) == "초과 근로 진행: +54h"
