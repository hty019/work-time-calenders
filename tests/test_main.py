"""main 진입점의 workctl 서브커맨드 디스패치 검증.

패키징 앱에서 AI 가 실행하는 '<실행파일> workctl ...' 이 GUI 를 띄우지
않고 workctl CLI 로 위임되는지 확인한다.
"""
import main as entry
import workctl


def test_main_dispatches_workctl_subcommand(monkeypatch):
    seen = {}

    def fake_workctl_main(argv):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(workctl, "main", fake_workctl_main)
    assert entry.main(["workctl", "show", "2026-07-08"]) == 0
    assert seen["argv"] == ["show", "2026-07-08"]
