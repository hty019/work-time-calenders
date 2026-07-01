import pytest

from core.timefmt import build_iso


def test_build_iso_ok():
    assert build_iso("2026-06-30", "09:05") == "2026-06-30T09:05:00+09:00"


def test_build_iso_invalid_raises():
    with pytest.raises(ValueError):
        build_iso("2026-06-30", "9시")
