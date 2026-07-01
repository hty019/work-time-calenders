#!/usr/bin/env bash
#
# work-widget 실행 스크립트
#
# 사용법:
#   ./run.sh                 위젯 백그라운드 실행 (필요 시 venv 생성·의존성 설치)
#   ./run.sh stop            백그라운드 위젯 종료
#   ./run.sh setup           venv 생성 및 의존성 설치만 수행
#   ./run.sh test            테스트 실행
#   ./run.sh install-startup macOS 로그인 시 자동 시작 등록
#   ./run.sh uninstall-startup  자동 시작 해제
#
set -euo pipefail

# 스크립트가 위치한 디렉터리를 기준으로 동작 (어디서 실행해도 안전)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
STAMP="$VENV_DIR/.deps-installed"
PLIST="$HOME/Library/LaunchAgents/com.taeyeon.workwidget.plist"

# 백그라운드 실행 상태 파일 (저장소가 아닌 데이터 홈에 보관)
DATA_HOME="${WORK_WIDGET_HOME:-$HOME/.work-widget}"
PID_FILE="$DATA_HOME/widget.pid"
LOG_FILE="$DATA_HOME/widget.log"

# 위젯이 현재 백그라운드로 실행 중인지 확인
is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

# python3 존재 확인
require_python3() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "오류: python3 를 찾을 수 없습니다. 먼저 Python 3 를 설치하세요." >&2
        exit 1
    fi
}

# venv 생성 + 의존성 설치 (멱등: 이미 있으면 건너뜀)
ensure_venv() {
    require_python3
    if [ ! -x "$PY" ]; then
        echo "==> 가상환경 생성: $VENV_DIR"
        python3 -m venv "$VENV_DIR"
    fi
    # requirements.txt 가 stamp 보다 최신이면 재설치
    if [ ! -f "$STAMP" ] || [ "$REQUIREMENTS" -nt "$STAMP" ]; then
        echo "==> 의존성 설치"
        "$PIP" install -q --upgrade pip
        "$PIP" install -q -r "$REQUIREMENTS"
        touch "$STAMP"
    fi
}

cmd_run() {
    ensure_venv
    mkdir -p "$DATA_HOME"
    if is_running; then
        echo "==> 이미 실행 중입니다 (PID $(cat "$PID_FILE"))."
        return 0
    fi
    echo "==> 위젯 백그라운드 실행"
    nohup "$PY" "$SCRIPT_DIR/main.py" >>"$LOG_FILE" 2>&1 &
    echo "$!" >"$PID_FILE"
    echo "==> 실행됨 (PID $!). 종료: './run.sh stop', 로그: $LOG_FILE"
}

cmd_stop() {
    if is_running; then
        local pid
        pid="$(cat "$PID_FILE")"
        kill "$pid" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "==> 위젯 종료 (PID $pid)."
    else
        rm -f "$PID_FILE"
        echo "==> 실행 중인 위젯이 없습니다."
    fi
}

cmd_setup() {
    ensure_venv
    echo "==> 준비 완료. './run.sh' 로 실행하세요."
}

cmd_test() {
    ensure_venv
    exec "$VENV_DIR/bin/pytest" -q
}

cmd_install_startup() {
    ensure_venv
    "$PY" "$SCRIPT_DIR/install_autostart.py" install
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    echo "==> 자동 시작 등록 완료. 다음 로그인부터 위젯이 자동 실행됩니다."
}

cmd_uninstall_startup() {
    launchctl unload "$PLIST" 2>/dev/null || true
    ensure_venv
    "$PY" "$SCRIPT_DIR/install_autostart.py" uninstall
    echo "==> 자동 시작 해제 완료."
}

case "${1:-run}" in
    run)               cmd_run ;;
    stop)              cmd_stop ;;
    setup)             cmd_setup ;;
    test)              cmd_test ;;
    install-startup)   cmd_install_startup ;;
    uninstall-startup) cmd_uninstall_startup ;;
    *)
        echo "사용법: $0 [run|stop|setup|test|install-startup|uninstall-startup]" >&2
        exit 2
        ;;
esac
