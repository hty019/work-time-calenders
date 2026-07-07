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


def test_delete_removes_row(tmp_path):
    s = make_storage(tmp_path)
    s.upsert(Attendance("2026-06-30", "2026-06-30T09:00:00+09:00", None, None))
    s.delete("2026-06-30")
    assert s.get("2026-06-30") is None


def test_delete_missing_is_noop(tmp_path):
    s = make_storage(tmp_path)
    s.delete("2026-06-30")  # 없어도 오류 없이 통과
    assert s.get("2026-06-30") is None


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


def test_vacation_set_get_clear(tmp_path):
    st = make_storage(tmp_path)
    assert st.get_vacation("2026-07-07") is None
    st.set_vacation("2026-07-07", 120, 900, 1020)  # 2h, 15:00~17:00
    assert st.get_vacation("2026-07-07") == (120, 900, 1020)
    st.set_vacation("2026-07-07", 480, None, None)  # 1day 덮어쓰기
    assert st.get_vacation("2026-07-07") == (480, None, None)
    st.clear_vacation("2026-07-07")
    assert st.get_vacation("2026-07-07") is None


def test_vacation_list_month(tmp_path):
    st = make_storage(tmp_path)
    st.set_vacation("2026-07-01", 120, 900, 1020)
    st.set_vacation("2026-08-01", 480, None, None)  # 다른 달
    got = st.list_vacation_month(2026, 7)
    assert got == {"2026-07-01": (120, 900, 1020)}


def test_memo_set_get_overwrite(tmp_path):
    st = make_storage(tmp_path)
    assert st.get_memo("2026-07-07") is None
    st.set_memo("2026-07-07", "주간 회의\n배포 준비")
    assert st.get_memo("2026-07-07") == "주간 회의\n배포 준비"
    st.set_memo("2026-07-07", "회고")  # 덮어쓰기
    assert st.get_memo("2026-07-07") == "회고"


def test_memo_empty_content_deletes(tmp_path):
    st = make_storage(tmp_path)
    st.set_memo("2026-07-07", "메모")
    st.set_memo("2026-07-07", "   ")  # 공백만 → 삭제와 동일
    assert st.get_memo("2026-07-07") is None


def test_memo_list_month(tmp_path):
    st = make_storage(tmp_path)
    st.set_memo("2026-07-01", "안건 A")
    st.set_memo("2026-07-15", "안건 B")
    st.set_memo("2026-08-01", "다른 달")
    assert st.list_memo_month(2026, 7) == {
        "2026-07-01": "안건 A",
        "2026-07-15": "안건 B",
    }


def test_annual_leave_set_get(tmp_path):
    st = make_storage(tmp_path)
    assert st.get_annual_leave(2026) is None
    st.set_annual_leave(2026, 15 * 480)
    assert st.get_annual_leave(2026) == 15 * 480
    st.set_annual_leave(2026, 16 * 480)  # 덮어쓰기
    assert st.get_annual_leave(2026) == 16 * 480
    assert st.get_annual_leave(2025) is None  # 연도별 독립


def test_vacation_list_year(tmp_path):
    st = make_storage(tmp_path)
    st.set_vacation("2026-01-05", 480, None, None)
    st.set_vacation("2026-07-01", 120, 900, 1020)
    st.set_vacation("2025-12-31", 480, None, None)  # 다른 해
    got = st.list_vacation_year(2026)
    assert got == {
        "2026-01-05": (480, None, None),
        "2026-07-01": (120, 900, 1020),
    }
