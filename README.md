# work-widget — 근무시간 데스크탑 위젯

macOS 부팅 시 자동 실행되어 출근 시간을 기록하고, 한국 공휴일과
월간 누적 근무시간을 바탕화면 달력 위젯으로 보여준다.

## 설치

```bash
cd ~/work-widget
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

의존성: PySide6, requests, holidays

## 공휴일 API 키 설정 (선택)

공공데이터포털(data.go.kr) "특일정보" 서비스 키를 발급받아 설정:

```bash
mkdir -p ~/.work-widget
echo '{"service_key": "발급받은_키"}' > ~/.work-widget/config.json
```
또는 환경변수 `DATA_GO_KR_SERVICE_KEY` 사용. 키가 없으면 공휴일 없이 동작.

> **주의**: data.go.kr 마이페이지에서 서비스 키를 확인할 때 반드시 **디코딩(Decoding) 키**를 사용하세요.
> `requests` 라이브러리가 파라미터를 자동으로 URL 인코딩하므로, 인코딩(Encoding) 키를 사용하면
> 이미 인코딩된 문자열이 다시 인코딩되어 이중 인코딩(double-encoding)이 발생하고 인증에 실패합니다.

## 실행

PySide6가 설치된 가상환경에서 실행한다:

```bash
./venv/bin/python main.py
```

- 전체화면 모드와 위젯 모드는 `F` 키로 전환할 수 있다.

## 자동 시작 등록

```bash
./venv/bin/python install_autostart.py install
launchctl load ~/Library/LaunchAgents/com.taeyeon.workwidget.plist
```

해제: `launchctl unload ...` 후 `python install_autostart.py uninstall`.

## 사용

- 부팅(실행) 시 그날 첫 실행 시각이 출근으로 기록됨(이미 있으면 유지).
- '퇴근' 버튼으로 근무시간 확정. 점심 차감: 9시간 미만 -30분, 9시간 이상 -1시간.
- 날짜 클릭 → 출근/퇴근 시각 수동 수정. 퇴근 비우면 미퇴근 처리.
- `F` 키로 전체화면 ↔ 위젯 모드 전환.

## 데이터 위치

`~/.work-widget/attendance.db` (근무 기록), `holidays_cache.json` (공휴일 캐시).
