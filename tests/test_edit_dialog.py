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
