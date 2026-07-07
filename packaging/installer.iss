; work-widget Windows 설치 프로그램 (Inno Setup 6)
;
; 사용법 (저장소 루트에서, PyInstaller 빌드 후):
;   ISCC.exe /DAppVersion=1.2.3 packaging\installer.iss
;
; 버전은 CI 가 /DAppVersion= 으로 주입한다. 미지정 시 개발 빌드(0.0.0).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "work-widget"
#define AppExe "work-widget.exe"

[Setup]
AppId={{7F3C2A9E-4B6D-4E1A-9C0D-2E8F5A1B7C3D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=taeyeon
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
; 관리자 권한 불필요 — 사용자 프로필(%LocalAppData%\Programs)에 설치
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename={#AppName}-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}

[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 생성"; Flags: unchecked
Name: "autostart"; Description: "Windows 로그인 시 자동 시작"

[Files]
Source: "..\dist\work-widget\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; macOS launchd 자동 시작에 대응하는 HKCU Run 키 — 제거 시 함께 삭제
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "설치 후 바로 실행"; Flags: nowait postinstall skipifsilent
