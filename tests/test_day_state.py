from core.day_state import (
    DayPlanClipboard,
    apply_clipboard,
    paste_targets,
    restore_day,
    snapshot_day,
)
from core.plan import PlanService
from core.recognition import RecognitionRange, RecognitionService
from core.storage import Attendance, Storage
from core.vacation import Vacation, VacationService


def make_services(tmp_path):
    storage = Storage(str(tmp_path / "db.db"))
    plans = PlanService(storage, default_minutes_getter=lambda: 480)
    recog = RecognitionService(storage)
    vacations = VacationService(storage)
    return storage, plans, recog, vacations


def test_paste_targets_single_uses_selected():
    assert paste_targets("2026-07-10", []) == ["2026-07-10"]


def test_paste_targets_multi_uses_full_list():
    dates = ["2026-07-10", "2026-07-11", "2026-07-12"]
    assert paste_targets("2026-07-12", dates) == dates


def test_apply_clipboard_sets_plan_and_recog(tmp_path):
    storage, _plans, recog, _vac = make_services(tmp_path)
    clip = DayPlanClipboard(plan_minutes=420, recog=RecognitionRange(540, 1080))
    apply_clipboard(storage, recog, clip, ["2026-07-10", "2026-07-11"])
    assert storage.get_plan("2026-07-10") == 420
    assert recog.get("2026-07-11") == RecognitionRange(540, 1080)


def test_apply_clipboard_clears_recog_when_none(tmp_path):
    storage, _plans, recog, _vac = make_services(tmp_path)
    recog.set("2026-07-10", RecognitionRange(540, 1080))
    clip = DayPlanClipboard(plan_minutes=480, recog=None)
    apply_clipboard(storage, recog, clip, ["2026-07-10"])
    assert storage.get_plan("2026-07-10") == 480
    assert recog.get("2026-07-10") is None


def test_snapshot_captures_all_facets(tmp_path):
    storage, plans, recog, vacations = make_services(tmp_path)
    storage.upsert(Attendance(
        "2026-07-10", "2026-07-10T09:00:00", "2026-07-10T18:00:00", 28800))
    storage.set_plan("2026-07-10", 420)
    recog.set("2026-07-10", RecognitionRange(540, 1080))
    vacations.set("2026-07-10", Vacation(120, 600, 720))
    storage.set_memo("2026-07-10", "메모")
    snap = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    assert snap.record.work_seconds == 28800
    assert snap.plan_override == 420
    assert snap.recog == RecognitionRange(540, 1080)
    assert snap.vacation == Vacation(120, 600, 720)
    assert snap.memo == "메모"


def test_restore_roundtrip_recovers_original(tmp_path):
    storage, plans, recog, vacations = make_services(tmp_path)
    storage.set_plan("2026-07-10", 420)
    recog.set("2026-07-10", RecognitionRange(540, 1080))
    before = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    storage.set_plan("2026-07-10", 480)
    recog.clear("2026-07-10")
    after = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    assert after != before
    restore_day(storage, recog, vacations, before)
    assert snapshot_day(storage, plans, recog, vacations, "2026-07-10") == before


def test_restore_recovers_empty_state(tmp_path):
    storage, plans, recog, vacations = make_services(tmp_path)
    before = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    storage.set_plan("2026-07-10", 480)
    recog.set("2026-07-10", RecognitionRange(540, 1080))
    vacations.set("2026-07-10", Vacation(480))
    storage.set_memo("2026-07-10", "x")
    restore_day(storage, recog, vacations, before)
    restored = snapshot_day(storage, plans, recog, vacations, "2026-07-10")
    assert restored == before
    assert restored.plan_override is None
    assert restored.recog is None
    assert restored.vacation is None
    assert restored.memo is None
