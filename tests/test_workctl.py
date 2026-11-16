import importlib
import io
import json
import sys

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


def test_set_plan_range_with_weekday_filter(workctl, capsys):
    """--from/--to + --weekday: 해당 요일만 일괄 적용."""
    assert workctl.main([
        "set-plan", "--from", "2026-07-01", "--to", "2026-07-31",
        "--weekday", "월", "720",
    ]) == 0
    capsys.readouterr()
    assert _show(workctl, capsys, "2026-07-06")["plan_override"] == 720
    assert _show(workctl, capsys, "2026-07-13")["plan_override"] == 720
    assert _show(workctl, capsys, "2026-07-07")["plan_override"] is None


def test_set_plan_range_skips_holidays(workctl, capsys):
    """--skip-holidays: 공휴일(오프라인 고정 공휴일 포함) 제외."""
    assert workctl.main([
        "set-plan", "--from", "2026-05-04", "--to", "2026-05-06",
        "--skip-holidays", "600",
    ]) == 0
    capsys.readouterr()
    assert _show(workctl, capsys, "2026-05-04")["plan_override"] == 600
    # 5/5 어린이날은 제외되어야 한다
    assert _show(workctl, capsys, "2026-05-05")["plan_override"] is None
    assert _show(workctl, capsys, "2026-05-06")["plan_override"] == 600


def test_set_recog_range(workctl, capsys):
    assert workctl.main([
        "set-recog", "--from", "2026-07-06", "--to", "2026-07-07",
        "08:00", "21:50",
    ]) == 0
    capsys.readouterr()
    assert _show(workctl, capsys, "2026-07-06")["recognition"] == "08:00~21:50"
    assert _show(workctl, capsys, "2026-07-07")["recognition"] == "08:00~21:50"


def test_range_requires_both_ends(workctl):
    assert workctl.main(["set-plan", "--from", "2026-07-01", "480"]) != 0


def test_single_date_with_range_is_rejected(workctl):
    rc = workctl.main([
        "clear-plan", "2026-07-06", "--from", "2026-07-01",
        "--to", "2026-07-31",
    ])
    assert rc != 0


def test_show_includes_holiday_name(workctl, capsys):
    assert _show(workctl, capsys, "2026-05-05")["holiday"] == "어린이날"
    assert _show(workctl, capsys, "2026-05-04")["holiday"] is None


def test_clear_plan_only_holidays(workctl, capsys):
    workctl.main([
        "set-plan", "--from", "2026-05-04", "--to", "2026-05-06", "600",
    ])
    capsys.readouterr()
    assert workctl.main([
        "clear-plan", "--from", "2026-05-04", "--to", "2026-05-06",
        "--only-holidays",
    ]) == 0
    capsys.readouterr()
    assert _show(workctl, capsys, "2026-05-04")["plan_override"] == 600
    assert _show(workctl, capsys, "2026-05-05")["plan_override"] is None
    assert _show(workctl, capsys, "2026-05-06")["plan_override"] == 600


def test_skip_and_only_holidays_are_mutually_exclusive(workctl):
    rc = workctl.main([
        "clear-plan", "--from", "2026-05-01", "--to", "2026-05-31",
        "--skip-holidays", "--only-holidays",
    ])
    assert rc != 0


def _cp949_stream() -> io.TextIOWrapper:
    """Windows 한국어 로캘에서 파이프로 연결된 stdout 을 흉내낸다."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp949")


def test_output_is_utf8_even_with_cp949_locale_stream(workctl, monkeypatch):
    # AI CLI 는 workctl 출력을 UTF-8 로 해석하므로 로캘 인코딩과 무관해야 한다
    stream = _cp949_stream()
    monkeypatch.setattr(sys, "stdout", stream)
    assert workctl.main(["set-memo", "2026-07-02", "주간 회의"]) == 0
    stream.flush()
    assert "메모 저장" in stream.buffer.getvalue().decode("utf-8")


def test_error_output_is_utf8_even_with_cp949_locale_stream(
    workctl, monkeypatch
):
    stream = _cp949_stream()
    monkeypatch.setattr(sys, "stderr", stream)
    assert workctl.main(["set-plan", "2026-07-02", "9999"]) != 0
    stream.flush()
    assert "오류" in stream.buffer.getvalue().decode("utf-8")


def test_missing_stdio_does_not_crash(workctl, monkeypatch):
    # 콘솔 없는 GUI 실행 파일(pythonw·windowed exe)은 sys.stdout 이 None 이다
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert workctl.main(["clear-memo", "2026-07-02"]) == 0
