import importlib
import json

import pytest


@pytest.fixture
def workctl(tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_WIDGET_HOME", str(tmp_path))
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    import config

    importlib.reload(config)
    import workctl as workctl_mod

    importlib.reload(workctl_mod)
    return workctl_mod


def _show(workctl, capsys, date):
    assert workctl.main(["show", date]) == 0
    return json.loads(capsys.readouterr().out)[date]


def test_set_plan_roundtrip(workctl, capsys):
    assert workctl.main(["set-plan", "2026-07-02", "360"]) == 0
    capsys.readouterr()
    assert _show(workctl, capsys, "2026-07-02")["plan_override"] == 360


def test_set_recog_too_narrow_is_blocked(workctl, capsys):
    assert workctl.main(["set-plan", "2026-07-02", "480"]) == 0
    # 480분 계획은 휴게 포함 8.5h 체류가 필요 — 1시간 폭은 차단
    assert workctl.main(["set-recog", "2026-07-02", "09:00", "10:00"]) != 0
    assert workctl.main(["set-recog", "2026-07-02", "09:00", "20:00"]) == 0
    capsys.readouterr()
    detail = _show(workctl, capsys, "2026-07-02")
    assert detail["recognition"] == "09:00~20:00"


def test_set_vacation_with_start(workctl, capsys):
    assert workctl.main(
        ["set-vacation", "2026-07-02", "240", "--start", "14:00"]
    ) == 0
    capsys.readouterr()
    detail = _show(workctl, capsys, "2026-07-02")
    assert detail["vacation_minutes"] == 240


def test_memo_roundtrip(workctl, capsys):
    assert workctl.main(["set-memo", "2026-07-02", "주간 회의"]) == 0
    capsys.readouterr()
    assert _show(workctl, capsys, "2026-07-02")["memo"] == "주간 회의"
    assert workctl.main(["clear-memo", "2026-07-02"]) == 0
    capsys.readouterr()
    assert _show(workctl, capsys, "2026-07-02")["memo"] is None


def test_clock_edit_command_not_available(workctl):
    with pytest.raises(SystemExit):
        workctl.main(["set-clock-in", "2026-07-02", "09:00"])
