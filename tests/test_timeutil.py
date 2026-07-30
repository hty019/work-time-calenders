from datetime import datetime
from core import timeutil
from core.timefmt import format_break


def test_now_is_kst_aware():
    dt = timeutil.now()
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 9 * 3600


def test_today_str_format():
    dt = datetime(2026, 6, 30, 8, 5, tzinfo=timeutil.KST)
    assert timeutil.today_str(dt) == "2026-06-30"


def test_iso_roundtrip():
    dt = datetime(2026, 6, 30, 9, 0, tzinfo=timeutil.KST)
    assert timeutil.from_iso(timeutil.to_iso(dt)) == dt


def test_hhmm_extracts_hour_minute():
    assert timeutil.hhmm("2026-06-30T09:05:00+09:00") == "09:05"
    assert timeutil.hhmm("2026-06-30T18:00:00+09:00") == "18:00"


def test_hhmm_empty_for_none_or_blank():
    assert timeutil.hhmm(None) == ""
    assert timeutil.hhmm("") == ""


def test_format_break_under_one_hour():
    assert format_break(0) == "0m"
    assert format_break(45) == "45m"
    assert format_break(59) == "59m"


def test_format_break_exact_hours_omit_zero_minutes():
    assert format_break(60) == "1h"
    assert format_break(120) == "2h"


def test_format_break_hours_and_minutes():
    assert format_break(61) == "1h 1m"
    assert format_break(90) == "1h 30m"
