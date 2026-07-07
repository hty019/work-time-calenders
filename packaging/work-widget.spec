# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 스펙 (Windows 배포용).
#
# 사용법 (저장소 루트에서):
#   pyinstaller packaging/work-widget.spec --noconfirm
#
# 결과: dist/work-widget/work-widget.exe (onedir — Qt 앱은 onefile 보다
# 기동이 빠르고 백신 오탐이 적다)

a = Analysis(
    ["../main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="work-widget",
    debug=False,
    strip=False,
    upx=False,
    console=False,  # GUI 앱 — 콘솔 창 숨김
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="work-widget",
)
