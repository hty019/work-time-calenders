# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 스펙 (Windows·macOS 공용).
#
# 사용법 (저장소 루트에서):
#   pyinstaller packaging/work-widget.spec --noconfirm
#
# 결과:
#   Windows — dist/work-widget/work-widget.exe (onedir — Qt 앱은 onefile 보다
#             기동이 빠르고 백신 오탐이 적다)
#   macOS   — dist/work-widget.app (ad-hoc 서명 앱 번들)
import sys

a = Analysis(
    ["../main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    # zoneinfo 가 tzdata 를 동적 임포트하므로 정적 분석에 잡히지 않는다.
    # 명시해 두면 hooks-contrib 의 tzdata 훅이 존 데이터 파일까지 수집한다.
    # workctl 은 main.py 의 함수 내부 임포트라 명시해 확실히 포함시킨다
    # ('<실행파일> workctl ...' 서브커맨드용).
    hiddenimports=["tzdata", "workctl"],
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

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="work-widget.app",
        icon=None,
        bundle_identifier="com.taeyeon.work-widget",
        info_plist={
            "CFBundleDisplayName": "work-widget",
            "NSHighResolutionCapable": True,
        },
    )
