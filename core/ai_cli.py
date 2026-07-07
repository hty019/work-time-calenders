"""로컬 AI CLI(Claude Code·Codex) 연동 — 명령·프롬프트 구성 (Qt 비의존)."""
from __future__ import annotations

import json

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


def version_command(provider: str) -> list[str]:
    """설치 여부 확인용 명령."""
    return [_BINARIES[provider], "--version"]


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


def build_run_command(
    provider: str, prompt: str, workctl_cmd: str
) -> list[str]:
    """제공자별 헤드리스 실행 명령을 구성한다."""
    if provider == PROVIDER_CLAUDE:
        # workctl 호출만 자동 허용 — 그 외 도구는 헤드리스에서 거부됨.
        # stream-json 으로 진행 상황(도구 실행 등)을 실시간 수신한다.
        return [
            "claude", "-p", prompt,
            "--allowedTools", f"Bash({workctl_cmd}:*)",
            "--output-format", "stream-json", "--verbose",
        ]
    if provider == PROVIDER_CODEX:
        # DB 가 홈 디렉터리(작업 폴더 밖)에 있어 샌드박스 완화가 필요
        return [
            "codex", "exec", "--sandbox", "danger-full-access", prompt,
        ]
    raise ValueError(f"알 수 없는 AI 제공자: {provider!r}")


RESULT_HEADER = "=== AI 응답 ==="


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
        return f"\n{RESULT_HEADER}\n{result}"
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
