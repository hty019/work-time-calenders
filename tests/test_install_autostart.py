from install_autostart import (
    RUN_VALUE_NAME,
    build_plist,
    build_run_command,
    plist_target_path,
)


def test_build_plist_contains_paths_and_runatload():
    xml = build_plist("/venv/bin/python", "/home/u/work-widget/main.py", "com.x.y")
    assert "/venv/bin/python" in xml
    assert "/home/u/work-widget/main.py" in xml
    assert "<key>RunAtLoad</key>" in xml
    assert "<true/>" in xml
    assert "com.x.y" in xml


def test_plist_target_path_uses_label():
    path = plist_target_path("com.x.y")
    assert path.endswith("Library/LaunchAgents/com.x.y.plist")


def test_build_plist_escapes_xml_special_chars():
    xml = build_plist("/a & b/python", "/home/test/main.py", "com.x.y")
    assert "/a &amp; b/python" in xml
    assert "/a & b/python" not in xml


# --- Windows (HKCU Run 키) ---------------------------------------------------


def test_windows_run_command_uses_pythonw_to_hide_console():
    cmd = build_run_command(
        r"C:\ww\venv\Scripts\python.exe", r"C:\ww\main.py"
    )
    assert cmd == r'"C:\ww\venv\Scripts\pythonw.exe" "C:\ww\main.py"'


def test_windows_run_command_quotes_paths_with_spaces():
    cmd = build_run_command(
        r"C:\My Apps\venv\Scripts\pythonw.exe", r"C:\My Apps\main.py"
    )
    assert cmd == r'"C:\My Apps\venv\Scripts\pythonw.exe" "C:\My Apps\main.py"'


def test_windows_run_value_name_matches_installer():
    # 설치 프로그램(installer.iss)과 같은 이름이어야 중복 자동 실행되지 않는다
    assert RUN_VALUE_NAME == "work-widget"
