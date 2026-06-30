"""macOS LaunchAgent 자동 시작 설치/제거."""
from __future__ import annotations

import os
import sys
from xml.sax.saxutils import escape

LABEL = "com.taeyeon.workwidget"
_DATA_DIR = os.path.expanduser("~/.work-widget")

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


def build_plist(python_path: str, main_path: str, label: str = LABEL) -> str:
    return _PLIST_TEMPLATE.format(
        label=escape(label),
        python_path=escape(python_path),
        main_path=escape(main_path),
        log_dir=escape(_DATA_DIR),
    )


def plist_target_path(label: str = LABEL) -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")


def install() -> str:
    python_path = os.path.abspath(sys.executable)
    main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    xml = build_plist(python_path, main_path)
    target = plist_target_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(xml)
    return target


def uninstall() -> None:
    target = plist_target_path()
    if os.path.exists(target):
        os.remove(target)


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if action == "install":
        path = install()
        print(f"설치됨: {path}")
        print(f"활성화: launchctl load {path}")
    elif action == "uninstall":
        uninstall()
        print("제거됨")
    else:
        print("사용법: python install_autostart.py [install|uninstall]")


if __name__ == "__main__":
    main()
