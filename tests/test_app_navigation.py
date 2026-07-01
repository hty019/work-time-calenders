from ui.app import _prev_month, _next_month


def test_prev_month_wraps_year():
    assert _prev_month(2026, 1) == (2025, 12)
    assert _prev_month(2026, 7) == (2026, 6)


def test_next_month_wraps_year():
    assert _next_month(2026, 12) == (2027, 1)
    assert _next_month(2026, 7) == (2026, 8)
