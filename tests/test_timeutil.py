from datetime import datetime
from core import timeutil


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
