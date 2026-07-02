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


def test_plan_set_get_clear(tmp_path):
    from core.storage import Storage
    st = Storage(str(tmp_path / "a.db"))
    assert st.get_plan("2026-07-07") is None
    st.set_plan("2026-07-07", 240)
    assert st.get_plan("2026-07-07") == 240
    st.set_plan("2026-07-07", 360)  # 덮어쓰기
    assert st.get_plan("2026-07-07") == 360
    st.clear_plan("2026-07-07")
    assert st.get_plan("2026-07-07") is None


def test_plan_list_month(tmp_path):
    from core.storage import Storage
    st = Storage(str(tmp_path / "b.db"))
    st.set_plan("2026-07-01", 480)
    st.set_plan("2026-07-15", 240)
    st.set_plan("2026-08-01", 480)  # 다른 달
    got = st.list_plan_month(2026, 7)
    assert got == {"2026-07-01": 480, "2026-07-15": 240}


def test_recognition_set_get_clear(tmp_path):
    st = make_storage(tmp_path)
    assert st.get_recognition("2026-07-07") is None
    st.set_recognition("2026-07-07", 540, 900)  # 09:00~15:00
    assert st.get_recognition("2026-07-07") == (540, 900)
    st.set_recognition("2026-07-07", 480, 1080)  # 덮어쓰기 08:00~18:00
    assert st.get_recognition("2026-07-07") == (480, 1080)
    st.clear_recognition("2026-07-07")
    assert st.get_recognition("2026-07-07") is None


def test_recognition_list_month(tmp_path):
    st = make_storage(tmp_path)
    st.set_recognition("2026-07-01", 540, 900)
    st.set_recognition("2026-08-01", 540, 900)  # 다른 달
    got = st.list_recognition_month(2026, 7)
    assert got == {"2026-07-01": (540, 900)}
