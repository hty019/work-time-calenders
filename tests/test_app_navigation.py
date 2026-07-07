from ui.app import _prev_month, _next_month


def test_prev_month_wraps_year():
    assert _prev_month(2026, 1) == (2025, 12)
    assert _prev_month(2026, 7) == (2026, 6)


def test_next_month_wraps_year():
    assert _next_month(2026, 12) == (2027, 1)
    assert _next_month(2026, 7) == (2026, 8)


def test_date_range_forward():
    from ui.app import _date_range

    assert _date_range("2026-07-01", "2026-07-03") == [
        "2026-07-01", "2026-07-02", "2026-07-03",
    ]


def test_date_range_backward_and_single():
    from ui.app import _date_range

    assert _date_range("2026-07-03", "2026-07-01") == [
        "2026-07-03", "2026-07-02", "2026-07-01",
    ]
    assert _date_range("2026-07-05", "2026-07-05") == ["2026-07-05"]


def test_date_range_crosses_month():
    from ui.app import _date_range

    assert _date_range("2026-06-30", "2026-07-02") == [
        "2026-06-30", "2026-07-01", "2026-07-02",
    ]
