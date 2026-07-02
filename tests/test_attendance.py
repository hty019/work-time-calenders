from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core.storage import Storage
from core.attendance import AttendanceService, WorkStatus

KST = ZoneInfo("Asia/Seoul")


def make_service(tmp_path, fixed_dt):
    storage = Storage(str(tmp_path / "att.db"))
    return AttendanceService(storage, clock=lambda: fixed_dt)


def test_clock_in_creates_today_row(tmp_path):
    dt = datetime(2026, 6, 30, 8, 30, tzinfo=KST)
    svc = make_service(tmp_path, dt)
    rec = svc.record_clock_in()
    assert rec.work_date == "2026-06-30"
    assert rec.clock_in == dt.isoformat()
    assert rec.clock_out is None


def test_clock_in_is_immutable_on_rerun(tmp_path):
    dt1 = datetime(2026, 6, 30, 8, 30, tzinfo=KST)
    svc = make_service(tmp_path, dt1)
    svc.record_clock_in()
    # 같은 날 더 늦은 시각으로 재실행해도 최초 기록 유지
    svc._clock = lambda: datetime(2026, 6, 30, 10, 0, tzinfo=KST)
    rec = svc.record_clock_in()
    assert rec.clock_in == dt1.isoformat()


def test_clock_out_computes_work_seconds(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    rec = svc.record_clock_out()
    assert rec.clock_out == datetime(2026, 6, 30, 18, 0, tzinfo=KST).isoformat()
    assert rec.work_seconds == 8 * 3600  # 9시간 - 60분


def test_clock_out_without_row_raises(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 18, 0, tzinfo=KST))
    with pytest.raises(ValueError):
        svc.record_clock_out()


def test_edit_recomputes(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    rec = svc.edit(
        "2026-06-29",
        "2026-06-29T09:00:00+09:00",
        "2026-06-29T17:00:00+09:00",
    )
    assert rec.work_seconds == 7 * 3600 + 30 * 60  # 8시간 - 30분


def test_edit_clear_clock_out_sets_incomplete(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    rec = svc.edit("2026-06-29", "2026-06-29T09:00:00+09:00", "")
    assert rec.clock_out is None
    assert rec.work_seconds is None


def test_edit_clock_out_before_in_raises(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    with pytest.raises(ValueError):
        svc.edit(
            "2026-06-29",
            "2026-06-29T18:00:00+09:00",
            "2026-06-29T09:00:00+09:00",
        )


def test_month_total_excludes_incomplete(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.edit("2026-06-01", "2026-06-01T09:00:00+09:00", "2026-06-01T18:00:00+09:00")
    svc.edit("2026-06-02", "2026-06-02T09:00:00+09:00", "")  # 미퇴근
    assert svc.month_total_seconds(2026, 6) == 8 * 3600


def test_today_in_progress_seconds_while_clocked_in(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    # 2시간 경과 → 첫 4시간 이내라 그대로 누적
    svc._clock = lambda: datetime(2026, 6, 30, 11, 0, tzinfo=KST)
    assert svc.today_in_progress_seconds() == 2 * 3600


def test_cancel_clock_out_reverts_to_in_progress(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    svc.record_clock_out()
    # 취소 → 미퇴근으로 복귀, 출근 시각은 보존
    rec = svc.cancel_clock_out()
    assert rec.clock_out is None
    assert rec.work_seconds is None
    assert rec.clock_in == datetime(2026, 6, 30, 9, 0, tzinfo=KST).isoformat()
    # 취소 후 다시 진행 중 근무초가 집계된다
    svc._clock = lambda: datetime(2026, 6, 30, 19, 0, tzinfo=KST)
    assert svc.today_in_progress_seconds() is not None


def test_cancel_clock_out_noop_without_clock_out(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()  # 미퇴근 상태
    assert svc.cancel_clock_out() is None


def test_reclock_out_updates_time(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    first = svc.record_clock_out()
    assert first.work_seconds == 8 * 3600  # 9h - 60m
    # 퇴근 상태에서 다시 퇴근 → 더 늦은 시각으로 갱신, 누적 재계산
    svc._clock = lambda: datetime(2026, 6, 30, 19, 0, tzinfo=KST)
    second = svc.record_clock_out()
    assert second.clock_out == datetime(2026, 6, 30, 19, 0, tzinfo=KST).isoformat()
    assert second.work_seconds == 9 * 3600  # 10h - 60m


def test_clock_out_subtracts_vacation_overlap(tmp_path):
    # 출근 08:00, 퇴근 15:50, 휴가 15:00~17:00 → 겹침 50m 제외 → 6h30m
    svc = make_service(tmp_path, datetime(2026, 6, 30, 8, 0, tzinfo=KST))
    svc._storage.set_vacation("2026-06-30", 120, 900, 1020)
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 15, 50, tzinfo=KST)
    rec = svc.record_clock_out()
    assert rec.work_seconds == 6 * 3600 + 30 * 60


def test_edit_subtracts_vacation_overlap(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc._storage.set_vacation("2026-06-29", 120, 540, 660)  # 09:00~11:00
    rec = svc.edit(
        "2026-06-29",
        "2026-06-29T08:00:00+09:00",
        "2026-06-29T17:00:00+09:00",
    )
    # raw 9h − 겹침 2h = 7h → 휴게 30m → 6h30m
    assert rec.work_seconds == 6 * 3600 + 30 * 60


def test_in_progress_subtracts_vacation(tmp_path):
    # 아침 휴가 09:00~11:00, 출근 08:00, 현재 14:00 → raw 6h − 2h = 4h
    svc = make_service(tmp_path, datetime(2026, 6, 30, 8, 0, tzinfo=KST))
    svc._storage.set_vacation("2026-06-30", 120, 540, 660)
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 14, 0, tzinfo=KST)
    assert svc.today_in_progress_seconds() == 4 * 3600


def test_recompute_work_applies_vacation_after_clock_out(tmp_path):
    # 퇴근 확정 후 휴가를 입력하면 recompute_work 로 저장값이 갱신된다
    svc = make_service(tmp_path, datetime(2026, 6, 30, 8, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 15, 50, tzinfo=KST)
    assert svc.record_clock_out().work_seconds == 7 * 3600 + 20 * 60
    svc._storage.set_vacation("2026-06-30", 120, 900, 1020)
    rec = svc.recompute_work("2026-06-30")
    assert rec.work_seconds == 6 * 3600 + 30 * 60


def test_full_day_vacation_does_not_clip_work(tmp_path):
    # 8h(1day) 휴가는 구간이 없어 근로 차감 없이 그대로 (합산 정책)
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc._storage.set_vacation("2026-06-30", 480, None, None)
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    assert svc.record_clock_out().work_seconds == 8 * 3600


def test_today_status_not_clocked_in(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    assert svc.today_status() is WorkStatus.NOT_CLOCKED_IN


def test_today_status_working_after_clock_in(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    assert svc.today_status() is WorkStatus.WORKING


def test_today_status_clocked_out(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    svc.record_clock_out()
    assert svc.today_status() is WorkStatus.CLOCKED_OUT


def test_today_status_working_again_after_cancel(tmp_path):
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    svc.record_clock_out()
    svc.cancel_clock_out()
    assert svc.today_status() is WorkStatus.WORKING


def test_today_in_progress_seconds_none_when_not_active(tmp_path):
    # 미출근
    svc = make_service(tmp_path, datetime(2026, 6, 30, 9, 0, tzinfo=KST))
    assert svc.today_in_progress_seconds() is None
    # 퇴근 완료 후에도 None
    svc.record_clock_in()
    svc._clock = lambda: datetime(2026, 6, 30, 18, 0, tzinfo=KST)
    svc.record_clock_out()
    assert svc.today_in_progress_seconds() is None
