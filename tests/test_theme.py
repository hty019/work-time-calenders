from ui.theme import font_family_for


def test_windows_uses_korean_system_font():
    # Windows 에는 Helvetica 가 없어 한글이 임의 대체 폰트로 렌더링된다
    assert font_family_for("win32") == "Malgun Gothic"


def test_macos_keeps_helvetica():
    assert font_family_for("darwin") == "Helvetica"
