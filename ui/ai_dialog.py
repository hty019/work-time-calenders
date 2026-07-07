"""로컬 AI CLI(Claude Code·Codex) 연동 다이얼로그.

제공자 선택 → 연동 확인(설치·로그인) → 자연어 지시 실행의 흐름.
실행은 QProcess 비동기로 진행하고 출력 로그를 실시간 표시한다.
"""
from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QStyleFactory, QTextEdit, QVBoxLayout,
)

import config
from core import timeutil
from core.ai_cli import (
    INSTALL_GUIDES,
    PROVIDER_LABELS,
    build_prompt,
    build_run_command,
    version_command,
)
from ui import theme

_PROVIDER_KEYS = list(PROVIDER_LABELS.keys())


def open_ai_dialog(
    parent, workdir: str, on_applied: Callable[[], None]
) -> None:
    """AI 연동 다이얼로그를 연다. 실행 완료 시 on_applied 로 갱신 통지."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("AI 연동")
    dlg.setMinimumSize(theme.AI_DIALOG_MIN_WIDTH, theme.AI_DIALOG_MIN_HEIGHT)
    layout = QVBoxLayout(dlg)

    workctl_cmd = f"{sys.executable} {workdir}/workctl.py"

    provider_row = QHBoxLayout()
    provider_combo = QComboBox()
    provider_combo.setStyle(QStyleFactory.create("Fusion"))
    for key in _PROVIDER_KEYS:
        provider_combo.addItem(PROVIDER_LABELS[key])
    provider_combo.setCurrentIndex(
        _PROVIDER_KEYS.index(config.get_ai_provider())
    )
    check_btn = QPushButton("연동 확인")
    status_label = QLabel("")
    status_label.setWordWrap(True)
    provider_row.addWidget(QLabel("AI"))
    provider_row.addWidget(provider_combo, stretch=1)
    provider_row.addWidget(check_btn)
    layout.addLayout(provider_row)
    layout.addWidget(status_label)

    instruction_edit = QTextEdit()
    instruction_edit.setPlaceholderText(
        "예) 다음 주 월~수 실 계획을 6시간으로 바꾸고 금요일에 반차 넣어줘"
    )
    instruction_edit.setFixedHeight(theme.AI_INSTRUCTION_HEIGHT)
    layout.addWidget(instruction_edit)

    log_view = QTextEdit()
    log_view.setReadOnly(True)
    log_view.setPlaceholderText("실행 로그가 여기에 표시됩니다.")
    layout.addWidget(log_view, stretch=1)

    buttons = QHBoxLayout()
    close_btn = QPushButton("닫기")
    close_btn.clicked.connect(dlg.reject)
    run_btn = QPushButton("실행")
    buttons.addWidget(close_btn)
    buttons.addWidget(run_btn)
    layout.addLayout(buttons)

    def _provider() -> str:
        return _PROVIDER_KEYS[provider_combo.currentIndex()]

    def _remember_provider() -> None:
        config.set_ai_provider(_provider())

    provider_combo.currentIndexChanged.connect(
        lambda _i: _remember_provider()
    )

    def _set_status(text: str, ok: bool) -> None:
        color = theme.FG_ACTUAL_DONE if ok else theme.FG_RANGE_WARN
        status_label.setStyleSheet(f"color:{color};")
        status_label.setText(text)

    def handle_check() -> None:
        """CLI 설치 여부 확인. 미설치면 설치·로그인 방법 안내."""
        provider = _provider()
        proc = QProcess(dlg)
        proc.start(version_command(provider)[0], version_command(provider)[1:])

        def _done(_code, _status) -> None:
            out = bytes(proc.readAllStandardOutput()).decode(errors="replace")
            if proc.exitCode() == 0 and out.strip():
                _set_status(f"연동 가능: {out.strip()}", ok=True)
            else:
                _set_status(
                    f"CLI 를 찾지 못했습니다. {INSTALL_GUIDES[provider]}",
                    ok=False,
                )

        proc.finished.connect(_done)
        proc.errorOccurred.connect(
            lambda _e: _set_status(
                f"CLI 를 찾지 못했습니다. {INSTALL_GUIDES[provider]}",
                ok=False,
            )
        )

    def handle_run() -> None:
        instruction = instruction_edit.toPlainText().strip()
        if not instruction:
            QMessageBox.warning(dlg, "입력 오류", "지시할 내용을 입력하세요.")
            return
        prompt = build_prompt(
            instruction, timeutil.today_str(timeutil.now()), workctl_cmd
        )
        cmd = build_run_command(_provider(), prompt, workctl_cmd)
        run_btn.setEnabled(False)
        log_view.setPlainText(f"{PROVIDER_LABELS[_provider()]} 실행 중…\n")

        proc = QProcess(dlg)
        proc.setWorkingDirectory(workdir)
        proc.setProcessChannelMode(QProcess.MergedChannels)

        def _append_output() -> None:
            text = bytes(proc.readAllStandardOutput()).decode(errors="replace")
            log_view.insertPlainText(text)

        def _finished(_code, _status) -> None:
            _append_output()
            done = "완료" if proc.exitCode() == 0 else f"실패 (exit {proc.exitCode()})"
            log_view.insertPlainText(f"\n--- {done} ---\n")
            run_btn.setEnabled(True)
            on_applied()  # 변경사항을 캘린더에 반영

        proc.readyReadStandardOutput.connect(_append_output)
        proc.finished.connect(_finished)
        proc.errorOccurred.connect(
            lambda _e: (
                log_view.insertPlainText(
                    "\nCLI 실행 실패 — [연동 확인] 으로 설치 상태를 점검하세요.\n"
                ),
                run_btn.setEnabled(True),
            )
        )
        proc.start(cmd[0], cmd[1:])

    check_btn.clicked.connect(handle_check)
    run_btn.clicked.connect(handle_run)
    handle_check()  # 열릴 때 연동 상태 자동 확인
    dlg.exec()
