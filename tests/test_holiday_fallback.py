from core.holiday_fallback import fixed_holidays


def test_fixed_holidays_returns_month_holidays():
    assert fixed_holidays(2026, 6) == {"2026-06-06": "현충일"}
    assert fixed_holidays(2026, 10) == {
        "2026-10-03": "개천절",
        "2026-10-09": "한글날",
    }


def test_fixed_holidays_empty_for_month_without_fixed_holiday():
    assert fixed_holidays(2026, 7) == {}
    assert fixed_holidays(2026, 11) == {}
