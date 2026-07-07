"""로컬 AI CLI(Claude Code·Codex) 연동 — 명령·프롬프트 구성 (Qt 비의존)."""
from __future__ import annotations

import json
import os
import shutil
import sys

PROVIDER_CLAUDE = "claude"
PROVIDER_CODEX = "codex"

PROVIDER_LABELS = {
    PROVIDER_CLAUDE: "Claude (Claude Code)",
    PROVIDER_CODEX: "ChatGPT (Codex CLI)",
}

# 미설치 시 사용자에게 안내할 설치·로그인 방법
INSTALL_GUIDES = {
    PROVIDER_CLAUDE: (
        "npm install -g @anthropic-ai/claude-code 설치 후 "
        "터미널에서 'claude' 실행 → /login 으로 로그인"
    ),
    PROVIDER_CODEX: (
        "npm install -g @openai/codex 설치 후 "
        "터미널에서 'codex login' 으로 로그인"
    ),
}

_BINARIES = {PROVIDER_CLAUDE: "claude", PROVIDER_CODEX: "codex"}

# 제공자별 모델 선택지: (표시 문구, CLI 인자값). None 은 CLI 기본 설정.
MODEL_CHOICES: dict[str, list[tuple[str, str | None]]] = {
    PROVIDER_CLAUDE: [
        ("기본 설정", None),
        ("Haiku (빠름·경제적)", "haiku"),
        ("Sonnet (균형)", "sonnet"),
        ("Opus (고성능)", "opus"),
    ],
    PROVIDER_CODEX: [
        # ChatGPT 계정에서는 -codex·-pro 계열이 막혀(API 과금 전용) 범용
        # 모델만 노출한다. 확실치 않으면 '기본 설정'(계정 기본 모델)을 쓴다.
        ("기본 설정", None),
        ("GPT-5.4 Mini (빠름·경제적)", "gpt-5.4-mini"),
        ("GPT-5.4 (균형)", "gpt-5.4"),
        ("GPT-5.5 (고성능)", "gpt-5.5"),
    ],
}


def version_command(provider: str) -> list[str]:
    """설치 여부 확인용 명령."""
    return [_BINARIES[provider], "--version"]


# 로그인(인증) 상태 판정 결과
AUTH_READY = "ready"        # 로그인 완료 — 실행 가능
AUTH_LOGGED_OUT = "logged_out"  # CLI 는 있으나 로그인 필요
AUTH_UNKNOWN = "unknown"    # 판정 불가(구버전·미지원 등) — 설치 여부로 대체


def auth_status_command(provider: str) -> list[str]:
    """로그인 상태 조회 명령. 브라우저·TTY 없이 결과만 반환한다."""
    if provider == PROVIDER_CLAUDE:
        return ["claude", "auth", "status"]
    if provider == PROVIDER_CODEX:
        return ["codex", "login", "status"]
    raise ValueError(f"알 수 없는 AI 제공자: {provider!r}")


def login_command(provider: str) -> list[str]:
    """대화형 로그인 명령(브라우저 OAuth). 새 터미널에서 실행해야 한다."""
    if provider == PROVIDER_CLAUDE:
        return ["claude", "auth", "login"]
    if provider == PROVIDER_CODEX:
        return ["codex", "login"]
    raise ValueError(f"알 수 없는 AI 제공자: {provider!r}")


def parse_auth_status(provider: str, exit_code: int, output: str) -> str:
    """auth 상태 명령의 출력으로 로그인 여부를 판정한다.

    claude 는 JSON(loggedIn) 을, codex 는 텍스트 문구를 해석한다.
    해석 불가 시 AUTH_UNKNOWN 을 돌려 설치 여부 검사로 대체하게 한다.
    """
    if provider == PROVIDER_CLAUDE:
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return AUTH_UNKNOWN
        if isinstance(data, dict) and "loggedIn" in data:
            return AUTH_READY if data["loggedIn"] else AUTH_LOGGED_OUT
        return AUTH_UNKNOWN
    if provider == PROVIDER_CODEX:
        low = (output or "").lower()
        if "not logged in" in low or "not signed in" in low:
            return AUTH_LOGGED_OUT
        if exit_code == 0 and ("logged in" in low or "signed in" in low):
            return AUTH_READY
        return AUTH_UNKNOWN
    return AUTH_UNKNOWN


def login_terminal_command(
    provider: str, platform: str | None = None
) -> list[str]:
    """로그인 명령을 새 터미널 창에서 실행하기 위한 OS별 명령.

    로그인은 브라우저 OAuth 를 띄우고 콜백을 기다리므로, 창을 유지한 채
    사용자가 완료할 수 있도록 별도 터미널에서 실행한다.
    """
    plat = platform if platform is not None else sys.platform
    login = " ".join(login_command(provider))
    if plat == "darwin":
        return [
            "osascript",
            "-e", f'tell application "Terminal" to do script "{login}"',
            "-e", 'tell application "Terminal" to activate',
        ]
    if plat.startswith("win"):
        # 새 콘솔 창에서 실행하고 완료 후에도 창을 유지(/k)
        return ["cmd", "/c", "start", "", "cmd", "/k", login]
    # linux 등: 표준 터미널 에뮬레이터로 시도
    return ["x-terminal-emulator", "-e", login]


def workctl_command_prefix(executable: str, workdir: str) -> str:
    """workctl.py 호출용 명령 접두사를 만든다.

    두 가지를 보정한다:
    - GUI 런처(pythonw)로 앱이 떠도 workctl 은 콘솔 python 으로 실행해야
      stdout(조회 결과·오류)을 받는다. pythonw → python 으로 바꾼다.
    - AI(claude)는 Bash 에서 경로를 정슬래시로 바꿔 실행하므로, 자동 승인
      되도록 --allowedTools 패턴과 정확히 일치시키려면 경로 구분자를 '/'
      로 통일해야 한다.
    """
    exe = executable
    for suffix, replacement in (("pythonw.exe", "python.exe"), ("pythonw", "python")):
        if exe.endswith(suffix):
            exe = exe[: -len(suffix)] + replacement
            break
    rel = os.path.relpath(exe, workdir)
    if rel.startswith(".."):
        rel = exe  # 작업 폴더 밖(venv 밖 실행 등)이면 절대 경로 사용
    return f"{rel.replace(os.sep, '/')} workctl.py"


def build_prompt(instruction: str, today: str, workctl_cmd: str) -> str:
    """AI 에게 전달할 지시문. workctl 사용법과 안전 규칙을 포함한다."""
    return f"""당신은 macOS 근무시간 트래커의 데이터 편집 도우미입니다.
오늘 날짜: {today}

날짜별 기록의 조회·수정은 반드시 아래 명령만 사용하세요:
  {workctl_cmd} show DATE [--to DATE]        # 기록 JSON 조회
  {workctl_cmd} set-plan DATE MINUTES        # 실 계획(분) 설정
  {workctl_cmd} clear-plan DATE              # 실 계획 해제(기본값)
  {workctl_cmd} set-recog DATE HH:MM HH:MM   # (가)계획 범위 설정
  {workctl_cmd} clear-recog DATE
  {workctl_cmd} set-vacation DATE MINUTES [--start HH:MM]  # 120/240/360/480
  {workctl_cmd} clear-vacation DATE
  {workctl_cmd} set-memo DATE "TEXT"
  {workctl_cmd} clear-memo DATE

모든 편집 명령은 단일 DATE 대신 범위 옵션을 지원합니다:
  --from DATE --to DATE [--weekday 월|화|수|목|금|토|일]
  [--skip-holidays | --only-holidays]
공휴일 여부는 show 출력의 holiday 필드(공휴일 이름 또는 null)로 확인할
수 있고, 공휴일 대상/제외 작업은 위 필터 옵션으로 처리하세요.
예) 올해 모든 월요일(공휴일 제외) 실 계획 12시간:
  {workctl_cmd} set-plan --from 2026-01-01 --to 2026-12-31 --weekday 월 --skip-holidays 720

규칙:
- 여러 날짜에 같은 값을 적용할 때는 반드시 범위 옵션 한 번으로
  처리하세요. 날짜별로 반복 호출하지 마세요.
- 명령은 현재 작업 폴더에서 위 형식 그대로 실행하세요. cd·파이프·
  리다이렉션·셸 스크립트 조합이나 다른 프로그램 사용은 허용되지 않아
  거부됩니다.
- 출퇴근 시각(실적)은 절대 수정하지 마세요. 위 명령 외 다른 방법으로
  데이터 파일(DB)에 접근하지 마세요.
- 수정 전 show 로 현재 값을 확인하고, 명령이 오류를 반환하면 지시를
  임의로 우회하지 말고 오류 내용을 보고하세요.
- 완료 후 변경 내역을 한국어로 간단히 요약해 출력하세요.

사용자 지시: {instruction}"""


def allowed_tool_patterns(workctl_cmd: str) -> list[str]:
    """claude --allowedTools 로 자동 허용할 Bash 패턴 목록.

    workctl 을 표준형뿐 아니라 흔한 변형(선행 './', bare python/python3)으로
    호출해도 승인 없이 실행되도록 여러 접두사를 허용한다. 모두 workctl.py
    호출이라 도메인 안전 범위(오직 workctl) 안이다.
    """
    prefixes = [workctl_cmd]
    looks_absolute = workctl_cmd.startswith("/") or (
        len(workctl_cmd) > 1 and workctl_cmd[1] == ":"
    )
    if not workctl_cmd.startswith("./") and not looks_absolute:
        prefixes.append(f"./{workctl_cmd}")
    prefixes.append("python workctl.py")
    prefixes.append("python3 workctl.py")
    seen: set[str] = set()
    uniq = [p for p in prefixes if not (p in seen or seen.add(p))]
    return [f"Bash({p}:*)" for p in uniq]


def build_run_command(
    provider: str,
    workctl_cmd: str,
    model: str | None = None,
) -> list[str]:
    """제공자별 헤드리스 실행 명령을 구성한다.

    프롬프트는 명령 인자가 아니라 stdin 으로 전달한다. 프롬프트에 줄바꿈·
    특수문자가 있어, Windows 에서 cmd /c 로 감싸 실행할 때 인용이 깨지는
    문제를 피하기 위함이다(claude·codex 모두 stdin 프롬프트를 지원).
    model 이 None 이면 각 CLI 의 기본 설정 모델을 사용한다.
    """
    if provider == PROVIDER_CLAUDE:
        # workctl 호출(표준형·흔한 변형)만 자동 허용 — 그 외 도구는
        # 헤드리스에서 거부된다. stream-json 으로 진행 상황을 실시간 수신.
        cmd = ["claude", "-p"]
        for pattern in allowed_tool_patterns(workctl_cmd):
            cmd += ["--allowedTools", pattern]
        cmd += ["--output-format", "stream-json", "--verbose"]
        if model is not None:
            cmd += ["--model", model]
        return cmd
    if provider == PROVIDER_CODEX:
        # DB 가 홈 디렉터리(작업 폴더 밖)에 있어 샌드박스 완화가 필요
        cmd = ["codex", "exec", "--sandbox", "danger-full-access"]
        if model is not None:
            cmd += ["-m", model]
        return cmd + ["-"]  # '-' = 프롬프트를 stdin 에서 읽음
    raise ValueError(f"알 수 없는 AI 제공자: {provider!r}")


def to_shell_command(
    cmd: list[str], platform: str | None = None, which=None
) -> list[str]:
    """Windows 에서 npm 셸 스크립트(.cmd) CLI 를 QProcess 로 실행 가능하게 한다.

    QProcess(CreateProcess)는 .cmd/.bat 를 직접 실행하지 못하므로 cmd /c 로
    감싼다. 네이티브 exe(예: claude.exe)는 그대로 두고, 그 외(codex.cmd 등)는
    감싼다. 비-Windows 에서는 원본을 그대로 반환한다.
    """
    plat = platform if platform is not None else sys.platform
    if not cmd or not plat.startswith("win"):
        return cmd
    resolver = which if which is not None else shutil.which
    resolved = resolver(cmd[0])
    if resolved and resolved.lower().endswith(".exe"):
        return cmd
    return ["cmd", "/c", *cmd]


RESULT_HEADER = "=== AI 응답 ==="

# 승인 요청/권한 거부로 보이는 문구. 헤드리스(단일 실행)라 승인 창을 띄울 수
# 없어, 이런 정황이 보이면 해당 작업이 실행되지 않았을 수 있음을 안내한다.
_APPROVAL_HINTS = (
    "승인해주", "승인해 주", "승인이 필요", "승인 필요", "승인을 요청",
    "승인 부탁", "권한 승인이 필요", "권한이 필요",
    "permission denied", "need approval", "needs approval",
    "requires approval", "requires permission", "approval to proceed",
)

_DENIAL_NOTE = (
    "⚠ 승인이 필요한 명령이 감지되었습니다. 이 앱은 단일 실행이라 승인 창을 "
    "띄울 수 없어, 해당 작업은 실행되지 않았을 수 있습니다. workctl 표준 "
    "명령은 자동 허용되니 지시를 더 명확히 하여 다시 시도하세요."
)


def permission_warning(text: str) -> str | None:
    """AI 응답 문구에 승인 요청 정황이 보이면 안내 문구를 돌려준다."""
    if not text:
        return None
    low = text.lower()
    for hint in _APPROVAL_HINTS:
        if hint.lower() in low:
            return _DENIAL_NOTE
    return None


def describe_permission_denials(denials: list | None) -> str | None:
    """result 이벤트의 permission_denials 배열을 사람이 읽을 안내로 변환."""
    if not denials:
        return None
    cmds = []
    for d in denials:
        inp = (d.get("tool_input") or d.get("input") or {}) if isinstance(d, dict) else {}
        cmds.append(inp.get("command") or (d.get("tool_name") if isinstance(d, dict) else None) or "(알 수 없음)")
    listed = "\n".join(f"  - {c}" for c in cmds)
    return (
        "⚠ 자동승인 대상이 아니어서 실행되지 않은 명령이 있습니다"
        f"(단일 실행이라 승인 불가):\n{listed}\n"
        "workctl 표준 형식인지 확인하세요."
    )


def _format_claude_event(event: dict) -> str | None:
    """stream-json 이벤트를 사용자용 진행 로그 한 줄로 변환."""
    kind = event.get("type")
    if kind == "assistant":
        lines = []
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                lines.append(block["text"].strip())
            elif block.get("type") == "tool_use":
                command = block.get("input", {}).get("command")
                lines.append(
                    f"$ {command}" if command else f"[{block.get('name')}]"
                )
        return "\n".join(lines) or None
    if kind == "result":
        result = event.get("result", "")
        parts = [f"\n{RESULT_HEADER}\n{result}"]
        # 승인 필요로 실행되지 못한 정황을 명확히 알린다
        note = describe_permission_denials(event.get("permission_denials"))
        if note is None:
            note = permission_warning(result)
        if note is not None:
            parts.append(note)
        return "\n".join(parts)
    # system(init)·user(tool_result) 등은 진행 로그로 노출하지 않음
    return None


def format_stream_event(provider: str, line: str) -> str | None:
    """CLI 출력 한 줄을 진행 로그 문자열로 변환. 숨길 라인은 None.

    claude 는 stream-json 라인을 해석하고, JSON 이 아닌 라인(경고 등)과
    codex 출력은 그대로 통과시킨다.
    """
    line = line.rstrip()
    if not line:
        return None
    if provider != PROVIDER_CLAUDE:
        return line
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return line
    return _format_claude_event(event)
