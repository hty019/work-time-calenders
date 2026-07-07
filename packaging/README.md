# Windows 패키징

Windows 용 설치 프로그램(`work-widget-setup-<버전>.exe`)을 만드는 구성이다.
사용자는 setup.exe 하나만 받아 설치하면 되고, Python 설치가 필요 없다.

## 구성 요소

| 파일 | 역할 |
|------|------|
| `work-widget.spec` | PyInstaller 스펙 — Python 런타임+PySide6 를 `dist/work-widget/` 에 번들 |
| `installer.iss` | Inno Setup 스크립트 — 시작 메뉴·바탕화면 바로가기, 로그인 자동 시작(선택), 언인스톨러 |
| `../.github/workflows/windows-build.yml` | CI 빌드 — 수동 실행 또는 `v*` 태그 푸시 시 동작 |

## 배포 절차 (CI)

```bash
git tag v1.0.0 && git push origin v1.0.0
```

태그를 푸시하면 GitHub Actions 가 빌드 후 Release 에 setup.exe 를 첨부한다.
수동 확인용 빌드는 Actions 탭에서 `windows-build` 를 workflow_dispatch 로
실행하면 아티팩트로 받을 수 있다.

## 로컬 빌드 (Windows PC 에서)

```powershell
pip install -r requirements.txt pyinstaller
pyinstaller packaging/work-widget.spec --noconfirm
# Inno Setup 6 설치 후 (https://jrsoftware.org/isinfo.php)
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging\installer.iss
# → packaging/Output/work-widget-setup-0.0.0.exe
```

## 알려진 제약

- 코드 서명이 없어 다운로드 시 SmartScreen 경고가 뜬다 — "추가 정보 → 실행".
- 데이터는 `%USERPROFILE%\.work-widget` 에 저장된다 (macOS 와 동일한 구조).
- 위젯 모드의 `Qt.Tool` 플래그는 Windows 에서 작업 표시줄에 표시되지 않는
  등 동작 차이가 있을 수 있어 실기기 확인이 필요하다.
