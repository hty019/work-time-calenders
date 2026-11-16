"""로그인 시 자동 시작 설치/제거 (개발 실행용).

- macOS: LaunchAgent plist (~/Library/LaunchAgents)
- Windows: HKCU Run 레지스트리 값 (설치 프로그램과 같은 이름을 써서
  설치본과 개발 실행이 동시에 자동 시작되지 않게 한다)
"""
from __future__ import annotations

import ntpath
import os
import sys
from xml.sax.saxutils import escape

LABEL = "com.taeyeon.workwidget"
_DATA_DIR = os.path.expanduser("~/.work-widget")

# packaging/installer.iss 의 [Registry] ValueName 과 일치해야 한다
RUN_VALUE_NAME = "work-widget"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_CONSOLE_PYTHON = "python.exe"
_WINDOWED_PYTHON = "pythonw.exe"  # 콘솔 창 없이 실행

_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{main_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/workwidget.out.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/workwidget.err.log</string>
</dict>
</plist>
"""


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def build_plist(python_path: str, main_path: str, label: str = LABEL) -> str:
    return _PLIST_TEMPLATE.format(
        label=escape(label),
        python_path=escape(python_path),
        main_path=escape(main_path),
        log_dir=escape(_DATA_DIR),
    )


def plist_target_path(label: str = LABEL) -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")


def build_run_command(python_path: str, main_path: str) -> str:
    """HKCU Run 값으로 쓸 명령줄. 콘솔 python 은 pythonw 로 바꾼다."""
    folder, name = ntpath.split(python_path)
    if name.lower() == _CONSOLE_PYTHON:
        python_path = ntpath.join(folder, _WINDOWED_PYTHON)
    return f'"{python_path}" "{main_path}"'


def _main_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")


def _install_windows() -> str:
    import winreg

    command = build_run_command(os.path.abspath(sys.executable), _main_path())
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command)
    return rf"HKCU\{_RUN_KEY}\{RUN_VALUE_NAME}"


def _uninstall_windows() -> None:
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        try:
            winreg.DeleteValue(key, RUN_VALUE_NAME)
        except FileNotFoundError:
            pass  # 이미 없음


def install() -> str:
    if _is_windows():
        return _install_windows()
    python_path = os.path.abspath(sys.executable)
    xml = build_plist(python_path, _main_path())
    target = plist_target_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(xml)
    return target


def uninstall() -> None:
    if _is_windows():
        _uninstall_windows()
        return
    target = plist_target_path()
    if os.path.exists(target):
        os.remove(target)


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if action == "install":
        path = install()
        print(f"설치됨: {path}")
        if not _is_windows():
            print(f"활성화: launchctl load {path}")
    elif action == "uninstall":
        uninstall()
        print("제거됨")
    else:
        print("사용법: python install_autostart.py [install|uninstall]")


if __name__ == "__main__":
    main()
