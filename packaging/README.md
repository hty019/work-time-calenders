# 패키징 (Windows·macOS)

Windows 설치 프로그램(`work-widget-setup-<버전>.exe`)과 macOS 디스크
이미지(`work-widget-<버전>.dmg`)를 만드는 구성이다. 사용자는 파일 하나만
받아 설치하면 되고, Python 설치가 필요 없다.

## 구성 요소

| 파일 | 역할 |
|------|------|
| `work-widget.spec` | PyInstaller 스펙 (공용) — Windows 는 `dist/work-widget/`, macOS 는 `dist/work-widget.app` 생성 |
| `installer.iss` | Inno Setup 스크립트 — 시작 메뉴·바탕화면 바로가기, 로그인 자동 시작(선택), 언인스톨러 |
| `../.github/workflows/build.yml` | CI 빌드 — windows·macos 잡 후 태그 빌드면 Release 에 두 산출물 첨부 |

## 배포 절차 (CI)

```bash
git tag v1.0.0 && git push origin v1.0.0
```

태그를 푸시하면 GitHub Actions 가 두 플랫폼을 병렬 빌드한 뒤 Release 에
setup.exe 와 dmg 를 첨부한다. 수동 확인용 빌드는 Actions 탭에서 `build` 를
workflow_dispatch 로 실행하면 아티팩트로 받을 수 있다.

## 로컬 빌드

### Windows

```powershell
pip install -r requirements.txt pyinstaller
pyinstaller packaging/work-widget.spec --noconfirm
# Inno Setup 6 설치 후 (https://jrsoftware.org/isinfo.php)
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging\installer.iss
# → packaging/Output/work-widget-setup-0.0.0.exe
```

### macOS

```bash
./venv/bin/pip install pyinstaller
./venv/bin/pyinstaller packaging/work-widget.spec --noconfirm
mkdir -p dmg_root && cp -R dist/work-widget.app dmg_root/
ln -s /Applications dmg_root/Applications
hdiutil create -volname "work-widget" -srcfolder dmg_root -ov -format UDZO \
  work-widget-dev.dmg
```

## 알려진 제약

- 코드 서명·공증이 없다.
  - Windows: 다운로드 시 SmartScreen 경고 — "추가 정보 → 실행".
  - macOS: 첫 실행 시 Gatekeeper 가 차단 — 앱을 우클릭 → "열기"로 1회
    승인하거나 `xattr -d com.apple.quarantine /Applications/work-widget.app`.
- macOS 빌드는 러너/빌드 머신 아키텍처(Apple Silicon = arm64) 전용이다.
  Intel Mac 은 지원하지 않는다.
- 데이터는 두 플랫폼 모두 홈 디렉터리의 `.work-widget/` 에 저장된다.
  macOS 에서 run.sh(개발 실행)와 설치 앱은 같은 데이터를 공유한다.
- 위젯 모드의 `Qt.Tool` 플래그는 Windows 에서 작업 표시줄에 표시되지 않는
  등 동작 차이가 있을 수 있어 실기기 확인이 필요하다.
