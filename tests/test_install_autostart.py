from install_autostart import build_plist, plist_target_path


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
