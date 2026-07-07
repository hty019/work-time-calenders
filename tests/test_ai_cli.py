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
