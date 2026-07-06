import pytest

from core.timefmt import build_iso


def test_build_iso_ok():
    assert build_iso("2026-06-30", "09:05") == "2026-06-30T09:05:00+09:00"


def test_build_iso_invalid_raises():
    with pytest.raises(ValueError):
        build_iso("2026-06-30", "9시")


def test_parse_recognition_inputs_both_empty_is_none():
    from ui.day_dialog import parse_recognition_inputs
    assert parse_recognition_inputs("", "  ") is None


def test_parse_recognition_inputs_returns_range():
    from core.recognition import RecognitionRange
    from ui.day_dialog import parse_recognition_inputs
    assert parse_recognition_inputs("09:00", "15:00") == RecognitionRange(540, 900)


def test_parse_recognition_inputs_partial_raises():
    from ui.day_dialog import parse_recognition_inputs
    with pytest.raises(ValueError):
        parse_recognition_inputs("09:00", "")
    with pytest.raises(ValueError):
        parse_recognition_inputs("", "15:00")


# --- 보기(read-only) 모드 표시 텍스트 --------------------------------------


def test_time_display_dash_when_empty():
    from ui.day_dialog import time_display
    assert time_display("09:05") == "09:05"
    assert time_display("") == "-"


def test_plan_display_override_or_default():
    from ui.day_dialog import plan_display
    assert plan_display(300, 480) == "300분"
    assert plan_display(None, 480) == "기본 480분"


def test_recognition_display_range_or_dash():
    from core.recognition import RecognitionRange
    from ui.day_dialog import recognition_display
    assert recognition_display(RecognitionRange(540, 900)) == "09:00 ~ 15:00"
    assert recognition_display(None) == "-"


def test_vacation_display_variants():
    from core.vacation import build_vacation
    from ui.day_dialog import vacation_display
    assert vacation_display(None) == "없음"
    assert vacation_display(build_vacation(480)) == "8h (1day)"
    assert vacation_display(build_vacation(120, start_min=900)) == (
        "2h (15:00 ~ 17:00)"
    )
