"""근무시간 앱 진입점."""
from __future__ import annotations

from core.ai_cli import extend_lookup_path
from ui.app import run


def main() -> None:
    # Finder·설치본 실행은 셸 PATH 를 받지 못해 AI CLI(claude·codex)를
    # 찾지 못한다. UI 가 뜨기 전에 잘 알려진 설치 폴더를 PATH 에 보강한다.
    extend_lookup_path()
    run()


if __name__ == "__main__":
    main()
