from core.storage import Storage, Attendance


def make_storage(tmp_path):
    return Storage(str(tmp_path / "att.db"))


def test_get_missing_returns_none(tmp_path):
    s = make_storage(tmp_path)
    assert s.get("2026-06-30") is None


def test_upsert_then_get(tmp_path):
    s = make_storage(tmp_path)
    rec = Attendance("2026-06-30", "2026-06-30T09:00:00+09:00", None, None)
    s.upsert(rec)
    got = s.get("2026-06-30")
    assert got == rec


def test_upsert_overwrites_same_date(tmp_path):
    s = make_storage(tmp_path)
    s.upsert(Attendance("2026-06-30", "2026-06-30T09:00:00+09:00", None, None))
    s.upsert(
        Attendance(
            "2026-06-30",
            "2026-06-30T09:00:00+09:00",
            "2026-06-30T18:00:00+09:00",
            8 * 3600,
        )
    )
    got = s.get("2026-06-30")
    assert got.clock_out == "2026-06-30T18:00:00+09:00"
    assert got.work_seconds == 8 * 3600


def test_list_month_filters_by_month(tmp_path):
    s = make_storage(tmp_path)
    s.upsert(Attendance("2026-06-01", "2026-06-01T09:00:00+09:00", None, None))
    s.upsert(Attendance("2026-06-30", "2026-06-30T09:00:00+09:00", None, None))
    s.upsert(Attendance("2026-07-01", "2026-07-01T09:00:00+09:00", None, None))
    rows = s.list_month(2026, 6)
    dates = sorted(r.work_date for r in rows)
    assert dates == ["2026-06-01", "2026-06-30"]
