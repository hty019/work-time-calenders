"""근무시간 앱 진입점.

기본은 GUI 실행이지만, 첫 인자가 'workctl' 이면 workctl CLI 로 위임한다.
패키징(PyInstaller) 앱에는 python 이 없어 AI 연동이 workctl.py 를 직접
실행할 수 없으므로, '<실행파일> workctl ...' 형태로 호출하게 한다.
"""
from __future__ import annotations

import sys

from core.ai_cli import extend_lookup_path

WORKCTL_SUBCOMMAND = "workctl"


def main(argv: list[str] | None = None) -> int | None:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == WORKCTL_SUBCOMMAND:
        # CLI 위임 — GUI(Qt) 를 임포트·기동하지 않는다
        import workctl

        return workctl.main(args[1:])
    # Finder·설치본 실행은 셸 PATH 를 받지 못해 AI CLI(claude·codex)를
    # 찾지 못한다. UI 가 뜨기 전에 잘 알려진 설치 폴더를 PATH 에 보강한다.
    extend_lookup_path()
    from ui.app import run

    run()
    return None


if __name__ == "__main__":
    sys.exit(main())
