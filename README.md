# work-widget — 근무시간 데스크탑 위젯

macOS·Windows 로그인 시 자동 실행되어 출근 시간을 기록하고, 한국 공휴일과
월간 누적 근무시간을 바탕화면 달력 위젯으로 보여준다.

> 일반 사용자는 [Releases](../../releases) 의 설치 파일(Windows `setup.exe`,
> macOS `dmg`)을 쓰면 Python 설치가 필요 없다. 빌드 방법은
> [packaging/README.md](packaging/README.md) 참고. 아래는 소스 개발 실행 방법이다.

## 설치

macOS:

```bash
cd ~/work-widget
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Windows (Python 3 설치 후, 저장소 폴더에서):

```bat
run.bat setup
```

의존성: PySide6, requests, holidays

## 공휴일 API 키 설정 (선택)

공공데이터포털(data.go.kr) "특일정보" 서비스 키를 발급받아 설정:

```bash
mkdir -p ~/.work-widget
echo '{"service_key": "발급받은_키"}' > ~/.work-widget/config.json
```
앱 툴바의 `공휴일 API 키` 버튼으로 등록할 수도 있다(두 OS 공통). 또는 환경변수 `DATA_GO_KR_SERVICE_KEY` 사용. 키가 없으면 공휴일 없이 동작.

> **주의**: data.go.kr 마이페이지에서 서비스 키를 확인할 때 반드시 **디코딩(Decoding) 키**를 사용하세요.
> `requests` 라이브러리가 파라미터를 자동으로 URL 인코딩하므로, 인코딩(Encoding) 키를 사용하면
> 이미 인코딩된 문자열이 다시 인코딩되어 이중 인코딩(double-encoding)이 발생하고 인증에 실패합니다.

## 실행

| | macOS | Windows |
|---|---|---|
| 실행 | `./run.sh` (백그라운드) 또는 `./venv/bin/python main.py` | `run.bat` (더블클릭 가능, 콘솔 없이 실행) |
| 종료 | `./run.sh stop` | 위젯/창의 닫기 버튼 |
| 테스트 | `./run.sh test` | `run.bat test` |

`run.sh`·`run.bat` 은 venv 가 없으면 생성하고 의존성을 설치한다.

## 자동 시작 등록

| | macOS (LaunchAgent) | Windows (HKCU Run 레지스트리) |
|---|---|---|
| 등록 | `./run.sh install-startup` | `run.bat install-startup` |
| 해제 | `./run.sh uninstall-startup` | `run.bat uninstall-startup` |

Windows 설치본의 "로그인 시 자동 시작" 옵션과 같은 레지스트리 값을 쓰므로,
둘 중 나중에 등록한 쪽 하나만 자동 실행된다.

## 사용

- 부팅(실행) 시 그날 첫 실행 시각이 출근으로 기록됨(이미 있으면 유지).
- '퇴근' 버튼으로 근무시간 확정. 점심 차감: 9시간 미만 -30분, 9시간 이상 -1시간.
- 날짜 클릭 → 출근/퇴근 시각 수동 수정. 퇴근 비우면 미퇴근 처리.
- 전체화면 상단 툴바의 `위젯 모드` 버튼으로 위젯 모드로 전환하고, 위젯의 `전체` 버튼으로 되돌아온다.

## 데이터 위치

홈 디렉터리의 `.work-widget/` (macOS `~/.work-widget`, Windows
`%USERPROFILE%\.work-widget`). `WORK_WIDGET_HOME` 환경변수로 바꿀 수 있다.

- `attendance.db` (근무 기록), `holidays_cache.json` (공휴일 캐시), `config.json` (설정)

## 종료 시 자동 퇴근

정상 종료(창 닫기, macOS 로그아웃·종료, Windows 로그오프·종료) 시 근무 중이면
현재 시각으로 퇴근을 자동 저장하고, 같은 날 다시 실행하면 취소해 근무를 이어간다.
작업 관리자 강제 종료·전원 차단은 대상이 아니다.
