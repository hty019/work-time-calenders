from core.ai_cli import (
    AUTH_LOGGED_OUT,
    AUTH_READY,
    AUTH_UNKNOWN,
    PROVIDER_CLAUDE,
    PROVIDER_CODEX,
    auth_status_command,
    build_prompt,
    build_run_command,
    login_command,
    login_terminal_command,
    parse_auth_status,
    to_shell_command,
    version_command,
)


def test_version_command_per_provider():
    assert version_command(PROVIDER_CLAUDE) == ["claude", "--version"]
    assert version_command(PROVIDER_CODEX) == ["codex", "--version"]


def test_build_run_command_claude_headless_with_tool_allowlist():
    cmd = build_run_command(PROVIDER_CLAUDE, "python workctl.py")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    # 프롬프트는 stdin 으로 전달하므로 명령 인자에 없어야 한다
    assert not any("PROMPT" in part for part in cmd)
    # workctl 만 허용하는 Bash 패턴이 포함되어야 한다
    allow = cmd[cmd.index("--allowedTools") + 1]
    assert "python workctl.py" in allow


def test_build_run_command_codex_exec():
    cmd = build_run_command(PROVIDER_CODEX, "python workctl.py")
    assert cmd[0] == "codex"
    assert cmd[1] == "exec"
    # '-' 로 프롬프트를 stdin 에서 읽는다
    assert cmd[-1] == "-"


def test_build_prompt_contains_context_and_rules():
    prompt = build_prompt("수요일 계획 6시간으로", "2026-07-07", "python workctl.py")
    assert "2026-07-07" in prompt
    assert "수요일 계획 6시간으로" in prompt
    assert "python workctl.py" in prompt
    assert "출퇴근" in prompt  # 출퇴근 수정 금지 규칙 명시


def test_format_stream_event_claude_tool_use():
    import json
    from core.ai_cli import format_stream_event

    line = json.dumps({
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use", "name": "Bash",
            "input": {"command": "python workctl.py show 2026-01-01"},
        }]},
    })
    out = format_stream_event(PROVIDER_CLAUDE, line)
    assert out.startswith("$ ")
    assert "python workctl.py show" in out


def test_format_stream_event_claude_text_and_result():
    import json
    from core.ai_cli import format_stream_event

    text_line = json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "확인 중"}]},
    })
    assert "확인 중" in format_stream_event(PROVIDER_CLAUDE, text_line)
    result_line = json.dumps(
        {"type": "result", "subtype": "success", "result": "3일 정리 완료"}
    )
    out = format_stream_event(PROVIDER_CLAUDE, result_line)
    assert "AI 응답" in out
    assert "3일 정리 완료" in out


def test_format_stream_event_skips_tool_results_and_empty():
    import json
    from core.ai_cli import format_stream_event

    tool_result = json.dumps({
        "type": "user",
        "message": {"content": [{"type": "tool_result", "content": "ok"}]},
    })
    assert format_stream_event(PROVIDER_CLAUDE, tool_result) is None
    assert format_stream_event(PROVIDER_CLAUDE, "") is None


def test_format_stream_event_passthrough():
    from core.ai_cli import format_stream_event

    # codex 는 사람이 읽는 로그를 그대로 출력
    assert format_stream_event(PROVIDER_CODEX, "working...") == "working..."
    # claude 라도 JSON 이 아닌 라인(경고 등)은 그대로 노출
    assert format_stream_event(PROVIDER_CLAUDE, "Warning: x") == "Warning: x"


def test_build_run_command_with_model_override():
    cmd = build_run_command(PROVIDER_CLAUDE, "python workctl.py", model="haiku")
    assert cmd[cmd.index("--model") + 1] == "haiku"
    cmd = build_run_command(
        PROVIDER_CODEX, "python workctl.py", model="gpt-5.1-codex"
    )
    assert cmd[cmd.index("-m") + 1] == "gpt-5.1-codex"


def test_build_run_command_default_model_omits_flag():
    cmd = build_run_command(PROVIDER_CLAUDE, "python workctl.py")
    assert "--model" not in cmd
    cmd = build_run_command(PROVIDER_CODEX, "python workctl.py")
    assert "-m" not in cmd


def test_to_shell_command_wraps_npm_shim_on_windows():
    which = lambda p: {  # noqa: E731
        "codex": r"C:\Users\x\AppData\Roaming\npm\codex.CMD",
        "claude": r"C:\Users\x\.local\bin\claude.EXE",
    }.get(p)
    # 네이티브 exe 는 그대로 실행
    assert to_shell_command(
        ["claude", "-p"], platform="win32", which=which
    ) == ["claude", "-p"]
    # .cmd shim 은 cmd /c 로 감싼다
    assert to_shell_command(
        ["codex", "exec"], platform="win32", which=which
    ) == ["cmd", "/c", "codex", "exec"]


def test_to_shell_command_passthrough_on_posix():
    # 비-Windows 에서는 감싸지 않는다
    assert to_shell_command(
        ["codex", "exec"], platform="darwin", which=lambda p: None
    ) == ["codex", "exec"]


def test_to_shell_command_unresolved_wraps_on_windows():
    # 미설치(해결 실패) 시에도 cmd /c 로 감싸 실행을 시도한다
    assert to_shell_command(
        ["codex"], platform="win32", which=lambda p: None
    ) == ["cmd", "/c", "codex"]


def test_auth_status_command_per_provider():
    assert auth_status_command(PROVIDER_CLAUDE) == ["claude", "auth", "status"]
    assert auth_status_command(PROVIDER_CODEX) == ["codex", "login", "status"]


def test_login_command_per_provider():
    assert login_command(PROVIDER_CLAUDE) == ["claude", "auth", "login"]
    assert login_command(PROVIDER_CODEX) == ["codex", "login"]


def test_parse_auth_status_claude():
    import json

    logged_in = json.dumps({"loggedIn": True, "email": "a@b.c"})
    assert parse_auth_status(PROVIDER_CLAUDE, 0, logged_in) == AUTH_READY
    logged_out = json.dumps({"loggedIn": False})
    assert parse_auth_status(PROVIDER_CLAUDE, 0, logged_out) == AUTH_LOGGED_OUT
    # auth 서브커맨드가 없는 구버전 등 — JSON 이 아니면 판정 불가
    assert parse_auth_status(PROVIDER_CLAUDE, 1, "error") == AUTH_UNKNOWN


def test_parse_auth_status_codex():
    assert parse_auth_status(
        PROVIDER_CODEX, 0, "Logged in using ChatGPT"
    ) == AUTH_READY
    assert parse_auth_status(
        PROVIDER_CODEX, 1, "Not logged in"
    ) == AUTH_LOGGED_OUT
    assert parse_auth_status(PROVIDER_CODEX, 0, "???") == AUTH_UNKNOWN


def test_login_terminal_command_macos():
    cmd = login_terminal_command(PROVIDER_CLAUDE, platform="darwin")
    assert cmd[0] == "osascript"
    assert any("claude auth login" in part for part in cmd)


def test_login_terminal_command_windows():
    cmd = login_terminal_command(PROVIDER_CODEX, platform="win32")
    assert cmd[0] == "cmd"
    assert any("codex login" in part for part in cmd)
