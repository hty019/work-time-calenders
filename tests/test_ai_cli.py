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


def test_allowed_tool_patterns_relative_includes_variants():
    from core.ai_cli import allowed_tool_patterns

    pats = allowed_tool_patterns("venv/Scripts/python.exe workctl.py")
    # 표준형·'./' 변형·bare python/python3 을 모두 허용
    assert "Bash(venv/Scripts/python.exe workctl.py:*)" in pats
    assert "Bash(./venv/Scripts/python.exe workctl.py:*)" in pats
    assert "Bash(python workctl.py:*)" in pats
    assert "Bash(python3 workctl.py:*)" in pats


def test_allowed_tool_patterns_absolute_has_no_dotslash():
    from core.ai_cli import allowed_tool_patterns

    pats = allowed_tool_patterns("C:/proj/venv/Scripts/python.exe workctl.py")
    assert not any(p.startswith("Bash(./") for p in pats)


def test_build_run_command_claude_has_multiple_allowlist_flags():
    cmd = build_run_command(PROVIDER_CLAUDE, "venv/Scripts/python.exe workctl.py")
    # --allowedTools 가 여러 번(변형별로) 붙는다
    assert cmd.count("--allowedTools") >= 2


def test_permission_warning_detects_approval_request():
    from core.ai_cli import permission_warning

    assert permission_warning("승인해주시면 변경사항을 적용하겠습니다") is not None
    assert permission_warning("Requires approval to proceed") is not None
    # 정상 완료 응답에는 경고가 없다
    assert permission_warning("실 계획 3건을 480분으로 설정했습니다.") is None
    assert permission_warning("") is None


def test_describe_permission_denials():
    from core.ai_cli import describe_permission_denials

    assert describe_permission_denials([]) is None
    assert describe_permission_denials(None) is None
    msg = describe_permission_denials(
        [{"tool_name": "Bash", "tool_input": {"command": "git status"}}]
    )
    assert "git status" in msg


def test_format_stream_event_result_appends_denial_warning():
    import json

    from core.ai_cli import format_stream_event

    line = json.dumps({
        "type": "result", "subtype": "success",
        "result": "승인해주시면 적용하겠습니다",
        "permission_denials": [],
    })
    out = format_stream_event(PROVIDER_CLAUDE, line)
    assert "AI 응답" in out
    assert "승인" in out and "실행되지 않았을" in out


def test_build_run_command_codex_exec():
    cmd = build_run_command(PROVIDER_CODEX, "python workctl.py")
    assert cmd[0] == "codex"
    assert cmd[1] == "exec"
    # '-' 로 프롬프트를 stdin 에서 읽는다
    assert cmd[-1] == "-"


def test_workctl_command_prefix_console_python_and_slashes():
    import os

    from core.ai_cli import workctl_command_prefix

    workdir = os.path.join("C:" + os.sep, "proj") if os.name == "nt" \
        else os.path.join(os.sep, "proj")
    exe = os.path.join(workdir, "venv", "Scripts", "pythonw.exe")
    got = workctl_command_prefix(exe, workdir)
    # pythonw -> python(콘솔), 경로는 정슬래시, 작업폴더 상대경로
    assert got == "venv/Scripts/python.exe workctl.py"
    assert "pythonw" not in got
    assert "\\" not in got


def test_workctl_command_prefix_outside_workdir_uses_absolute():
    import os

    from core.ai_cli import workctl_command_prefix

    workdir = os.path.join(os.sep, "proj")
    exe = os.path.join(os.sep, "other", "python")  # 작업폴더 밖
    got = workctl_command_prefix(exe, workdir)
    assert got.endswith("workctl.py")
    assert "\\" not in got


def test_workctl_command_prefix_frozen_uses_exe_subcommand():
    from core.ai_cli import workctl_command_prefix

    got = workctl_command_prefix(
        "/Applications/work-widget.app/Contents/MacOS/work-widget",
        "/Users/u",
        frozen=True,
    )
    # 패키징 앱은 workctl.py 대신 실행 파일의 workctl 서브커맨드를 쓴다
    assert got == (
        "/Applications/work-widget.app/Contents/MacOS/work-widget workctl"
    )


def test_workctl_command_prefix_frozen_quotes_spaced_windows_path():
    from core.ai_cli import workctl_command_prefix

    got = workctl_command_prefix(
        "C:\\Program Files\\work-widget\\work-widget.exe",
        "C:\\Users\\u",
        frozen=True,
    )
    # 공백 경로는 인용하고, Bash 실행에 맞춰 정슬래시로 통일
    assert got == '"C:/Program Files/work-widget/work-widget.exe" workctl'


def test_allowed_tool_patterns_quoted_absolute_skips_dot_variant():
    from core.ai_cli import allowed_tool_patterns

    pats = allowed_tool_patterns(
        '"C:/Program Files/work-widget/work-widget.exe" workctl'
    )
    assert (
        'Bash("C:/Program Files/work-widget/work-widget.exe" workctl:*)'
        in pats
    )
    # 인용된 절대 경로에는 './' 변형을 만들지 않는다
    assert not any('./"' in p for p in pats)


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


# --- GUI 런처(최소 PATH)에서 CLI 를 찾기 위한 PATH 보강 ---


def _no_versions(_path):
    raise FileNotFoundError


def test_cli_search_dirs_macos_common_locations():
    from core.ai_cli import cli_search_dirs

    dirs = cli_search_dirs(
        "darwin", "/Users/u", environ={}, listdir=_no_versions
    )
    assert "/opt/homebrew/bin" in dirs
    assert "/usr/local/bin" in dirs
    assert "/Users/u/.local/bin" in dirs
    assert "/Users/u/.npm-global/bin" in dirs


def test_cli_search_dirs_picks_latest_nvm_version():
    from core.ai_cli import cli_search_dirs

    nvm_base = "/Users/u/.nvm/versions/node"

    def listdir(path):
        assert path == nvm_base
        return ["v18.20.3", "v20.11.1", "not-a-version"]

    dirs = cli_search_dirs("darwin", "/Users/u", environ={}, listdir=listdir)
    assert f"{nvm_base}/v20.11.1/bin" in dirs
    assert f"{nvm_base}/v18.20.3/bin" not in dirs


def test_cli_search_dirs_windows_npm_appdata():
    from core.ai_cli import cli_search_dirs

    dirs = cli_search_dirs(
        "win32", "C:\\Users\\u",
        environ={"APPDATA": "C:\\Users\\u\\AppData\\Roaming"},
        listdir=_no_versions,
    )
    assert "C:\\Users\\u\\AppData\\Roaming\\npm" in dirs


def test_augmented_path_appends_only_missing_existing_dirs():
    from core.ai_cli import augmented_path

    result = augmented_path(
        "/usr/bin:/bin",
        ["/opt/homebrew/bin", "/no/such/dir", "/usr/bin"],
        pathsep=":",
        isdir=lambda d: d != "/no/such/dir",
    )
    # 존재하는 미포함 디렉토리만 뒤에 덧붙이고, 기존 순서는 유지
    assert result == "/usr/bin:/bin:/opt/homebrew/bin"


def test_augmented_path_empty_current():
    from core.ai_cli import augmented_path

    result = augmented_path(
        "", ["/opt/homebrew/bin"], pathsep=":", isdir=lambda _d: True
    )
    assert result == "/opt/homebrew/bin"


def test_extend_lookup_path_updates_environ(monkeypatch, tmp_path):
    import os

    from core import ai_cli

    extra = tmp_path / "bin"
    extra.mkdir()
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(
        ai_cli, "cli_search_dirs", lambda *a, **k: [str(extra)]
    )
    ai_cli.extend_lookup_path()
    assert os.environ["PATH"] == "/usr/bin" + os.pathsep + str(extra)
