from core.ai_cli import (
    PROVIDER_CLAUDE,
    PROVIDER_CODEX,
    build_prompt,
    build_run_command,
    version_command,
)


def test_version_command_per_provider():
    assert version_command(PROVIDER_CLAUDE) == ["claude", "--version"]
    assert version_command(PROVIDER_CODEX) == ["codex", "--version"]


def test_build_run_command_claude_headless_with_tool_allowlist():
    cmd = build_run_command(PROVIDER_CLAUDE, "PROMPT", "python workctl.py")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "PROMPT" in cmd
    # workctl 만 허용하는 Bash 패턴이 포함되어야 한다
    allow = cmd[cmd.index("--allowedTools") + 1]
    assert "python workctl.py" in allow


def test_build_run_command_codex_exec():
    cmd = build_run_command(PROVIDER_CODEX, "PROMPT", "python workctl.py")
    assert cmd[0] == "codex"
    assert cmd[1] == "exec"
    assert "PROMPT" in cmd


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
    cmd = build_run_command(
        PROVIDER_CLAUDE, "PROMPT", "python workctl.py", model="haiku"
    )
    assert cmd[cmd.index("--model") + 1] == "haiku"
    cmd = build_run_command(
        PROVIDER_CODEX, "PROMPT", "python workctl.py", model="gpt-5.1-codex"
    )
    assert cmd[cmd.index("-m") + 1] == "gpt-5.1-codex"


def test_build_run_command_default_model_omits_flag():
    cmd = build_run_command(PROVIDER_CLAUDE, "PROMPT", "python workctl.py")
    assert "--model" not in cmd
    cmd = build_run_command(PROVIDER_CODEX, "PROMPT", "python workctl.py")
    assert "-m" not in cmd
